"""Common display formatters shared by Excel and plotly renderers."""

from __future__ import annotations

import pandas as pd

SECTOR_KO = {"life": "생명보험", "non_life": "손해보험", "reinsurance": "재보험"}


def to_trillion(values: pd.Series, decimals: int = 2) -> pd.Series:
    """원 단위 → 조원, 반올림."""
    return (values / 1e12).round(decimals)


def to_billion(values: pd.Series, decimals: int = 1) -> pd.Series:
    """원 단위 → 십억원."""
    return (values / 1e9).round(decimals)


def sector_label(sector: str) -> str:
    return SECTOR_KO.get(sector, sector)


def humanize_peer_table(
    df: pd.DataFrame,
    value_col: str = "amount_krw",
    rename: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Apply Korean column names + trillion-won values for human-facing tables.

    Expects columns: cik, name_ko, sector, [value_col], rank, percentile,
    vs_median, vs_self, is_self (those present are kept).
    """
    if df.empty:
        return df.copy()
    out = df.copy()
    if value_col in out.columns:
        out["금액(조원)"] = to_trillion(out[value_col])
    if "sector" in out.columns:
        out["섹터"] = out["sector"].map(sector_label)
    base = {
        "name_ko": "회사",
        "rank": "순위",
        "percentile": "백분위(%)",
        "vs_median": "중위대비(배)",
        "vs_self": "자사대비(배)",
        "is_self": "자사여부",
    }
    if rename:
        base.update(rename)
    out = out.rename(columns=base)

    # pick & order columns that exist
    preferred = ["회사", "섹터", "금액(조원)", "순위", "백분위(%)", "중위대비(배)", "자사대비(배)", "자사여부"]
    cols = [c for c in preferred if c in out.columns]
    extras = [c for c in out.columns if c not in cols and c not in {"cik", "sector", value_col,
                                                                     "rank", "percentile", "vs_median",
                                                                     "vs_self", "is_self"}]
    return out[cols + extras]
