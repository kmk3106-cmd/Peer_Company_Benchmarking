"""Peer-relative ratios and percentile placement.

Computes the "where does self stand vs peers" answer that the actuarial team
ultimately needs. All functions are pure (DataFrame in / DataFrame|dict out).
"""

from __future__ import annotations

import pandas as pd

from peer_benchmarking.domain import peer_groups


def compute_ratio(
    numerator: pd.DataFrame,
    denominator: pd.DataFrame,
    ratio_name: str,
    on: str = "cik",
    value_col: str = "amount_krw",
) -> pd.DataFrame:
    """Element-wise ratio between two cross-section DataFrames.

    Both inputs must have one row per peer (collapsed). The returned frame
    keeps name_ko/sector from the numerator side.

    Returns: cik | name_ko | sector | ratio_name | numerator | denominator | ratio
    """
    num = numerator[[on, "name_ko", "sector", value_col]].rename(columns={value_col: "numerator"})
    den = denominator[[on, value_col]].rename(columns={value_col: "denominator"})
    merged = num.merge(den, on=on, how="inner")
    merged["ratio_name"] = ratio_name
    merged["ratio"] = merged["numerator"] / merged["denominator"].where(merged["denominator"] != 0)
    return merged[[on, "name_ko", "sector", "ratio_name", "numerator", "denominator", "ratio"]]


def distribution_stats(
    df: pd.DataFrame,
    value_col: str = "amount_krw",
    by: str | None = None,
) -> pd.DataFrame:
    """Summary stats (count/mean/median/p25/p75/min/max) across peers.

    Args:
        by: if given, group by this column (e.g. 'sector') and return one
            row per group. If None, returns one row labelled 'all'.
    """
    if df.empty:
        return pd.DataFrame()

    def _stats(s: pd.Series) -> dict:
        return {
            "count": int(s.count()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "p25": float(s.quantile(0.25)),
            "p75": float(s.quantile(0.75)),
            "min": float(s.min()),
            "max": float(s.max()),
            "std": float(s.std()) if s.count() > 1 else float("nan"),
        }

    if by:
        out = (
            df.groupby(by)[value_col]
            .apply(lambda s: pd.Series(_stats(s)))
            .unstack()
            .reset_index()
        )
        return out
    stats = _stats(df[value_col])
    return pd.DataFrame([{"group": "all", **stats}])


def self_percentile(
    df: pd.DataFrame,
    value_col: str = "amount_krw",
    self_cik: str | None = None,
) -> dict:
    """Where does the self CIK sit in the peer distribution?

    Returns a dict with:
        cik, name_ko, value, percentile (0-100), rank (1=smallest),
        n_peers, distance_to_median (value - median), median, mean.

    Designed for direct JSON serialization in the future REST endpoint.
    """
    if df.empty:
        return {"error": "empty dataframe"}
    self_cik = self_cik or peer_groups.self_cik()
    if self_cik not in df["cik"].values:
        return {"error": f"self_cik={self_cik} not in dataframe"}

    sub = df.dropna(subset=[value_col]).sort_values(value_col).reset_index(drop=True)
    n = len(sub)
    self_row = sub[sub["cik"] == self_cik].iloc[0]
    self_value = float(self_row[value_col])
    rank = int(sub.index[sub["cik"] == self_cik][0]) + 1  # 1-based, smallest first
    percentile = (rank - 1) / (n - 1) * 100 if n > 1 else 50.0

    return {
        "cik": self_cik,
        "name_ko": str(self_row["name_ko"]),
        "value": self_value,
        "percentile": round(percentile, 1),
        "rank": rank,
        "n_peers": n,
        "median": float(sub[value_col].median()),
        "mean": float(sub[value_col].mean()),
        "distance_to_median": self_value - float(sub[value_col].median()),
    }


def add_peer_relative_columns(
    df: pd.DataFrame,
    value_col: str = "amount_krw",
    self_cik: str | None = None,
) -> pd.DataFrame:
    """Annotate each row with rank, percentile, and self-relative ratio.

    Adds columns:
        rank, percentile, vs_median, vs_self, is_self.
    """
    if df.empty:
        return df.copy()
    self_cik = self_cik or peer_groups.self_cik()
    out = df.sort_values(value_col).reset_index(drop=True).copy()
    out["rank"] = out.index + 1
    n = len(out)
    out["percentile"] = (out["rank"] - 1) / (n - 1) * 100 if n > 1 else 50.0
    median = out[value_col].median()
    out["vs_median"] = out[value_col] / median if median else float("nan")
    self_val_series = out.loc[out["cik"] == self_cik, value_col]
    if not self_val_series.empty:
        self_val = float(self_val_series.iloc[0])
        out["vs_self"] = out[value_col] / self_val if self_val else float("nan")
    else:
        out["vs_self"] = float("nan")
    out["is_self"] = out["cik"] == self_cik
    return out


def summarize_panel(
    df: pd.DataFrame,
    *,
    value_col: str = "amount_krw",
    label: str = "metric",
    self_cik: str | None = None,
    by_sector: bool = True,
) -> dict:
    """Bundle distribution stats + self-percentile + per-peer ranks.

    Returns a JSON-serializable dict structured for direct rendering in
    Excel/plotly or a future REST endpoint:
        {
          "label": ...,
          "stats_all": {...},
          "stats_by_sector": [{...}, ...] | None,
          "self": {...},  # self_percentile result
          "rows": [{...peer rows with rank/percentile...}],
        }
    """
    bundle: dict = {"label": label}
    bundle["stats_all"] = distribution_stats(df, value_col=value_col).to_dict("records")[0] if not df.empty else {}
    bundle["stats_by_sector"] = (
        distribution_stats(df, value_col=value_col, by="sector").to_dict("records")
        if by_sector and not df.empty
        else None
    )
    bundle["self"] = self_percentile(df, value_col=value_col, self_cik=self_cik)
    annotated = add_peer_relative_columns(df, value_col=value_col, self_cik=self_cik)
    bundle["rows"] = annotated.to_dict("records")
    return bundle
