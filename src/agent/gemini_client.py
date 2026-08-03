"""LLM backend for Gemini — two interchangeable transports, SAME model (gemini-2.5-pro):

1. HTTP API (cloud / server): if GEMINI_API_KEY (or GOOGLE_API_KEY) is set, call the Gemini REST API
   directly. This is the path used when the app is DEPLOYED (a server can't hold an interactive OAuth
   login). The key is minted from the user's own Google account; free-tier and paid keys hit the exact
   same gemini-2.5-pro model — "free" only caps requests/min, not reasoning quality.
2. CLI subprocess (local dev): otherwise fall back to the `gemini` CLI on the user's OAuth login ($0).

Both expose call_gemini() with the same signature, so the rest of the app doesn't care which is used.
`yolo=True` = allow Google-Search grounding (web search) in either transport.

Windows-safe CLI details that matter (learned the hard way):
- prompt piped on STDIN, not argv (Windows ~32k cmdline cap);
- no role/JSON mode -> roles faked as [SYSTEM]/[USER] text blocks;
- env GEMINI_CLI_TRUST_WORKSPACE=true; GOOGLE_CLOUD_PROJECT passed through (Workspace accounts);
- launched via `cmd /c` on Windows so the npm shim (gemini.cmd) resolves;
- communicate(timeout=...) + `taskkill /F /T` tree-kill on timeout (the npm shim spawns a node child
  that survives a normal kill and holds the pipes open).
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request

_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


class GeminiError(Exception):
    """gemini call failed (non-zero exit, timeout, or missing CLI)."""


class GeminiAuthError(GeminiError):
    """OAuth token expired/absent — user must run `gemini` once to re-login."""


def _tree_kill(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, check=False)
        else:  # pragma: no cover (dev machine is Windows)
            os.kill(pid, 9)
    except Exception:
        pass


def gemini_available() -> bool:
    """True if EITHER transport is usable: an API key is set (cloud) or the `gemini` CLI is on PATH."""
    if _api_key():
        return True
    import shutil
    return shutil.which("gemini") is not None or shutil.which("gemini.cmd") is not None


def _call_gemini_api(user_prompt: str, system: str | None, model: str, timeout: int,
                     web_search: bool, api_key: str) -> str:
    """Call the Gemini REST API (the deployed/server path). Same model as the CLI; web_search adds the
    Google-Search grounding tool so the deep AI-exposure search still works in the cloud."""
    body: dict = {"contents": [{"role": "user", "parts": [{"text": user_prompt.strip()}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system.strip()}]}
    if web_search:
        body["tools"] = [{"google_search": {}}]
    url = _API_ENDPOINT.format(model=model) + f"?key={api_key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        if e.code in (401, 403):
            raise GeminiAuthError(f"Gemini API key rejected ({e.code}). Check GEMINI_API_KEY. {detail}")
        raise GeminiError(f"Gemini API HTTP {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise GeminiError(f"Gemini API request failed: {e}")

    cands = data.get("candidates") or []
    if not cands:
        fb = (data.get("promptFeedback") or {}).get("blockReason")
        raise GeminiError(f"Gemini API returned no candidates{f' (blocked: {fb})' if fb else ''}.")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise GeminiError("Gemini API returned an empty response.")
    return text


def call_gemini(user_prompt: str, system: str | None = None,
                model: str = "gemini-2.5-pro", timeout: int = 180, cwd: str | None = None,
                yolo: bool = False) -> str:
    """Send a prompt to the gemini CLI and return its stdout text.

    Roles are rendered as [SYSTEM]/[USER] blocks (the CLI has no role separation). `yolo=True` adds
    `-y` so the CLI auto-approves its tools (needed for web search in headless mode) — pair it with a
    throwaway `cwd` so auto-approved file tools can't touch anything you care about. Raises
    GeminiAuthError on an expired login, GeminiError on any other failure.

    Transport: if an API key is set (deployed/cloud), use the REST API (same model). Otherwise use the
    local `gemini` CLI subprocess.
    """
    key = _api_key()
    if key:
        return _call_gemini_api(user_prompt, system=system, model=model, timeout=timeout,
                                web_search=yolo, api_key=key)

    if not gemini_available():
        raise GeminiError("`gemini` CLI not found on PATH. Install: npm i -g @google/gemini-cli")

    blocks = []
    if system:
        blocks.append("[SYSTEM]\n" + system.strip())
    blocks.append("[USER]\n" + user_prompt.strip())
    prompt = "\n\n".join(blocks)

    env = dict(os.environ)
    env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"  # headless trusted-workspace gate

    base = ["gemini", "-m", model] + (["-y"] if yolo else [])
    cmd = (["cmd", "/c"] + base) if os.name == "nt" else base

    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, cwd=cwd, text=True, encoding="utf-8", errors="replace",
    )
    try:
        out, err = proc.communicate(input=prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        _tree_kill(proc.pid)
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        raise GeminiError(f"gemini timed out after {timeout}s (tree-killed)")

    if proc.returncode != 0:
        low = (err or "").lower()
        if any(k in low for k in ("login", "auth", "oauth", "credential", "expired")):
            raise GeminiAuthError(
                "Gemini login appears expired. Run `gemini` once in a terminal to re-authenticate."
            )
        raise GeminiError((err or "").strip() or f"gemini exited with code {proc.returncode}")

    return (out or "").strip()
