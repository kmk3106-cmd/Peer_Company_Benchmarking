"""Cross-sectional peer comparison: same item, same period, all peers.

All functions return long-format pandas DataFrames suitable for both
analysis and JSON serialization (for the future 계리포탈 REST endpoint).
"""

from __future__ import annotations

import duckdb
import pandas as pd

from peer_benchmarking.analysis.queries import (
    QuerySpec,
    collapse_to_one_per_cik,
    fetch_element_values,
)
from peer_benchmarking.domain import liability_mapping


def liability_balance(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    item_name: str = "total_liability",
    period_instant: str | None = "2025-12-31",
) -> pd.DataFrame:
    """Cross-section of one balance-sheet item across peers.

    Args:
        item_name: key in liability_items.yml `liability_balance` (e.g.
            'total_liability', 'total_asset').
        period_instant: YYYY-MM-DD instant date filter.

    Returns long DataFrame:
        cik | name_ko | sector | item | amount_krw | period_instant
    """
    d = liability_mapping.load()
    spec_item = d.liability_balance[item_name]
    df = fetch_element_values(
        con,
        spec,
        element_id=spec_item.element_id,
        require_period_instant=period_instant,
    )
    df = collapse_to_one_per_cik(df, how="max_abs")
    df["item"] = item_name
    df["ko_label"] = spec_item.ko_label
    return df[["cik", "name_ko", "sector", "item", "ko_label", "amount_krw", "period_instant"]]


def component_decomposition(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    period_instant: str | None = "2025-12-31",
) -> pd.DataFrame:
    """BEL/RA/CSM 분해 across peers.

    For each peer, returns three rows (one per component) showing how
    insurance contract liability is split into the IFRS17 building blocks.

    Returns long DataFrame:
        cik | name_ko | sector | component | amount_krw | period_instant
    """
    d = liability_mapping.load()
    parts = []
    for component_key, member in d.components_axis.members.items():
        df = fetch_element_values(
            con,
            spec,
            element_id=d.liability_balance["total_liability"].element_id,
            extra_member_filter=member.element_id,
            require_period_instant=period_instant,
        )
        df = collapse_to_one_per_cik(df, how="max_abs")
        df["component"] = component_key
        df["ko_label"] = member.ko_label
        parts.append(df[["cik", "name_ko", "sector", "component", "ko_label", "amount_krw", "period_instant"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def pl_item(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    item_name: str = "insurance_revenue",
    period_start: str = "2025-01-01",
    period_end: str = "2025-12-31",
) -> pd.DataFrame:
    """Cross-section of one P&L item (duration period) across peers.

    Args:
        item_name: key in liability_items.yml `pl_items`.
        period_start / period_end: duration filter (YYYY-MM-DD).

    Returns long DataFrame:
        cik | name_ko | sector | item | amount_krw | period_start | period_end
    """
    d = liability_mapping.load()
    item = d.pl_items[item_name]

    df = fetch_element_values(con, spec, element_id=item.element_id)
    # Filter by duration period
    if not df.empty:
        df = df[
            (df["period_start"] == period_start) & (df["period_end"] == period_end)
        ].copy()
    df = collapse_to_one_per_cik(df, how="max_abs")
    df["item"] = item_name
    df["ko_label"] = item.ko_label
    df["period_start"] = period_start
    df["period_end"] = period_end
    return df[
        ["cik", "name_ko", "sector", "item", "ko_label", "amount_krw", "period_start", "period_end"]
    ]
