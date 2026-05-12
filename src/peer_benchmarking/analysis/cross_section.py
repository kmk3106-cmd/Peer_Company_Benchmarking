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
    fallback_to_other_basis: bool = True,
) -> pd.DataFrame:
    """Cross-section of one balance-sheet top-line item across peers.

    Project rule: 별도(separate) 기준만 사용 (CLAUDE.md §7). `QuerySpec.consolidation`
    default is "separate". Use `top_level_only=True` to match 사업보고서 BS exactly
    (verified: 미래에셋 별도 보험계약부채 27.00조 = 사업보고서 제39기 BS).

    Args:
        item_name: key in liability_items.yml `liability_balance`.
        period_instant: YYYY-MM-DD instant date filter.
        fallback_to_other_basis: if a peer has no submission for the primary
            basis (e.g. some firms only file consolidated), fall back to the
            other basis. Marked in the `basis` column so it's visible.

    Returns long DataFrame:
        cik | name_ko | sector | item | amount_krw | period_instant | basis
        where basis ∈ {'separate', 'consolidated'} indicates which was used.
    """
    d = liability_mapping.load()
    spec_item = d.liability_balance[item_name]
    df = fetch_element_values(
        con,
        spec,
        element_id=spec_item.element_id,
        require_period_instant=period_instant,
        top_level_only=True,
    )
    df = collapse_to_one_per_cik(df, how="max_abs")
    df["basis"] = spec.consolidation

    if fallback_to_other_basis and spec.consolidation in ("separate", "consolidated"):
        from peer_benchmarking.domain import peer_groups

        peer_ciks = set(peer_groups.members_of(spec.peer_group))
        present = set(df["cik"]) if not df.empty else set()
        missing = peer_ciks - present
        if missing:
            other = "consolidated" if spec.consolidation == "separate" else "separate"
            other_spec = QuerySpec(
                report_date=spec.report_date,
                consolidation=other,
                peer_group=spec.peer_group,
            )
            other_df = fetch_element_values(
                con,
                other_spec,
                element_id=spec_item.element_id,
                require_period_instant=period_instant,
                top_level_only=True,
            )
            other_df = collapse_to_one_per_cik(other_df, how="max_abs")
            other_df = other_df[other_df["cik"].isin(missing)]
            other_df["basis"] = other
            df = pd.concat([df, other_df], ignore_index=True)

    df["item"] = item_name
    df["ko_label"] = spec_item.ko_label
    return df[
        ["cik", "name_ko", "sector", "item", "ko_label", "amount_krw", "period_instant", "basis"]
    ]


def component_decomposition(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    period_instant: str | None = "2025-12-31",
) -> pd.DataFrame:
    """BEL/RA/CSM 분해 across peers.

    Uses the *decomposition* element (Issued 없는 변형) because that is what
    DART filers attach the components axis member to. The BS top-line uses
    a different element (Issued 포함).

    Returns long DataFrame:
        cik | name_ko | sector | component | amount_krw | period_instant
    """
    d = liability_mapping.load()
    parts = []
    for component_key, member in d.components_axis.members.items():
        df = fetch_element_values(
            con,
            spec,
            element_id=d.liability_balance["total_liability_for_decomposition"].element_id,
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
