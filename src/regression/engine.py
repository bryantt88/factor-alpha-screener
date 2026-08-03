"""OLS regression engine (docs/REGRESSION.md §1-§5) — the analytical heart.

    R_stock,t = alpha + sum_i(beta_i * R_i,t) + epsilon_t          (statsmodels OLS)

THE key convention (CLAUDE.md rule 3, REGRESSION §2):
    idiosyncratic return = alpha + epsilon        # NEVER bare epsilon: sum(epsilon)=0 erases the trend
Cumulative lines & attribution are ADDITIVE (cumsum) so the identity holds exactly:
    cum_raw_additive == cum_explained + cum_idio   # the shaded gap == "explained by factors"
The headline 6m/12m raw return is COMPOUNDED:  prod(1 + R) - 1.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

TRADING_DAYS_PER_YEAR = 252


def _newey_west_maxlags(n: int) -> int:
    """Newey-West (1994) automatic bandwidth: floor(4 * (n/100)^(2/9)) — ~4 lags for a 252-day year.
    The HAC window over which residual autocorrelation is accounted for when widening the SEs."""
    return max(1, int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


@dataclass
class RegressionResult:
    alpha: float                     # daily intercept
    betas: dict[str, float]          # factor -> partial beta
    pvalues: dict[str, float]        # includes 'alpha' + each factor
    tstats: dict[str, float]         # includes 'alpha' + each factor (coef / std err)
    r2: float
    n_obs: int
    resid: pd.Series                 # epsilon_t
    idio: pd.Series                  # alpha + epsilon_t  <- the quantity we plot
    explained: pd.Series             # stock - idio == sum_i(beta_i * factor_i)
    stock_returns: pd.Series
    factor_returns: pd.DataFrame
    cov_type: str = "HAC"            # 'HAC' (Newey-West robust SEs) — how tstats/pvalues were computed
    hac_maxlags: int | None = None   # HAC bandwidth actually used (None if cov_type != 'HAC')
    r2_adjusted: float = 0.0         # degrees-of-freedom-adjusted R² (corrects many-factor inflation)

    # --- additive cumulatives (the identity cum_raw == cum_explained + cum_idio holds exactly) ---
    @property
    def cum_idio(self) -> pd.Series:
        return self.idio.cumsum()

    @property
    def cum_raw_additive(self) -> pd.Series:
        return self.stock_returns.cumsum()

    @property
    def cum_explained(self) -> pd.Series:
        return self.explained.cumsum()

    # --- compounded cumulatives (the user-facing convention: real "money" return path) ---
    @property
    def cum_raw_compounded(self) -> pd.Series:
        return (1.0 + self.stock_returns).cumprod() - 1.0

    @property
    def cum_idio_compounded(self) -> pd.Series:
        """Compounded path of the idiosyncratic (alpha+epsilon) daily returns."""
        return (1.0 + self.idio).cumprod() - 1.0

    def idio_return_compounded(self) -> float:
        return float((1.0 + self.idio).prod() - 1.0)

    @property
    def predicted(self) -> pd.Series:
        """Model-fitted daily return: alpha + sum(beta_i * factor_i) = actual - residual."""
        return (self.stock_returns - self.resid).rename("predicted")

    @property
    def alpha_annualized(self) -> float:
        """Additive annualisation of the daily drift (alpha * 252)."""
        return self.alpha * TRADING_DAYS_PER_YEAR

    # --- alpha SIGNIFICANCE & QUALITY (is the unexplained drift real, or noise?) --------------------
    # alpha = the persistent daily drift the factors don't explain; epsilon = the day-by-day leftover
    # (mean ~0). A big cumulative idio (alpha+eps) can come from ONE large epsilon day (a jump) while
    # alpha itself is tiny/insignificant. These read whether the OWN-MERIT drift is statistically real.
    @property
    def alpha_tstat(self) -> float:
        return float(self.tstats.get("alpha", float("nan")))

    @property
    def alpha_pvalue(self) -> float:
        return float(self.pvalues.get("alpha", float("nan")))

    @property
    def resid_vol_annualized(self) -> float:
        """Annualised idiosyncratic volatility (std of epsilon * sqrt(252))."""
        return float(self.resid.std(ddof=1) * (TRADING_DAYS_PER_YEAR ** 0.5))

    @property
    def annualized_volatility(self) -> float:
        """Annualised volatility of the stock's OWN total daily returns (std * sqrt(252)) — the
        'how bumpy is it' risk read, distinct from resid_vol (which is only the idiosyncratic part)."""
        return float(self.stock_returns.std(ddof=1) * (TRADING_DAYS_PER_YEAR ** 0.5))

    @property
    def max_drawdown(self) -> float:
        """Worst peak-to-trough decline of the compounded price path over the sample (<= 0).
        Computed from the same daily returns the regression uses, so it covers the horizon window."""
        wealth = (1.0 + self.stock_returns).cumprod()
        dd = wealth / wealth.cummax() - 1.0
        return float(dd.min()) if len(dd) else float("nan")

    @property
    def information_ratio(self) -> float:
        """Annualised alpha per unit of idiosyncratic risk = alpha_ann / resid_vol_ann.
        The quality of the alpha: steady drift scores high, a jumpy/noisy residual scores low."""
        rv = self.resid_vol_annualized
        return float(self.alpha_annualized / rv) if rv > 0 else float("nan")

    def alpha_significant(self, p_threshold: float = 0.05) -> bool:
        """True only when alpha is POSITIVE and statistically distinguishable from zero."""
        p = self.alpha_pvalue
        return bool(self.alpha > 0 and p == p and p < p_threshold)

    @property
    def simple_market_beta(self) -> float | None:
        """Univariate (TradingView-style) beta of the stock on the market factor alone: cov/var.
        Differs from the multivariate partial beta when the stock also loads on oil/gas/rates.
        None when 'market' isn't in the active factor set (e.g. commodity mode)."""
        if "market" not in self.factor_returns.columns:
            return None
        m = self.factor_returns["market"]
        v = float(m.var(ddof=1))
        if v <= 0:
            return None
        return float(self.stock_returns.cov(m) / v)

    @property
    def cum_alpha_drift(self) -> pd.Series:
        """The pure persistent-drift path: alpha compounded on its own (no epsilon). Plotting this
        against cum_idio shows signal (straight-ish drift) vs noise (the wiggle around it)."""
        base = pd.Series(self.alpha, index=self.idio.index)
        return (1.0 + base).cumprod() - 1.0

    def raw_return_compounded(self, window: int | None = None) -> float:
        """Compounded raw return prod(1+R)-1 over the last `window` days (default: full sample)."""
        r = self.stock_returns if window is None else self.stock_returns.tail(window)
        return float((1.0 + r).prod() - 1.0)


def run_regression(stock_returns: pd.Series, factor_returns: pd.DataFrame,
                   maxlags: int | None = None) -> RegressionResult:
    """Fit OLS of stock returns on factor returns; return a RegressionResult.

    `stock_returns` and `factor_returns` must already be aligned on the same dates (see
    data.prices.build_return_panel). Follows the sm.add_constant / sm.OLS(...).fit() recipe in
    REGRESSION §4, with Newey-West (HAC) robust standard errors.

    Inference uses HAC standard errors because daily equity returns show volatility clustering + mild
    autocorrelation, which makes classical OLS SEs too small → alpha looks more statistically real
    than it is. HAC widens the SEs to the honest level. The point estimates (alpha, betas, R²) are
    IDENTICAL to classical OLS — only the tstats/pvalues (the alpha-significance test we rank on)
    change. `maxlags` overrides the auto Newey-West bandwidth.
    """
    stock_returns = stock_returns.astype(float)
    factor_returns = factor_returns.astype(float)
    if len(stock_returns) != len(factor_returns):
        raise ValueError("stock_returns and factor_returns must be aligned (equal length)")

    X = sm.add_constant(factor_returns, has_constant="add")   # adds the alpha (intercept) column
    lags = maxlags if maxlags is not None else _newey_west_maxlags(len(stock_returns))
    model = sm.OLS(stock_returns, X).fit(cov_type="HAC",
                                         cov_kwds={"maxlags": lags, "use_correction": True})

    alpha = float(model.params["const"])
    betas = {k: float(v) for k, v in model.params.drop("const").items()}
    pvalues = {("alpha" if k == "const" else k): float(v) for k, v in model.pvalues.items()}
    tstats = {("alpha" if k == "const" else k): float(v) for k, v in model.tvalues.items()}

    resid = model.resid.rename("resid")
    idio = (alpha + resid).rename("idio")                     # alpha + epsilon
    explained = (stock_returns - idio).rename("explained")    # == sum_i beta_i * factor_i

    return RegressionResult(
        alpha=alpha,
        betas=betas,
        pvalues=pvalues,
        tstats=tstats,
        r2=float(model.rsquared),
        n_obs=int(model.nobs),
        resid=resid,
        idio=idio,
        explained=explained,
        stock_returns=stock_returns,
        factor_returns=factor_returns,
        cov_type="HAC",
        hac_maxlags=lags,
        r2_adjusted=float(model.rsquared_adj),
    )
