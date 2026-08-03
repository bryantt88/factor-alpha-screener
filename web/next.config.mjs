/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export: the app is fully client-rendered and talks to the API at runtime, so we ship it as
  // static files that the FastAPI backend serves itself (one origin, one URL — deploy-friendly).
  output: 'export',
  images: { unoptimized: true },
  // The API base is set at build time via NEXT_PUBLIC_API_BASE:
  //   - local dev:  http://127.0.0.1:8000  (two servers)
  //   - production: '' (same origin — FastAPI serves this build AND /api)
};
export default nextConfig;
