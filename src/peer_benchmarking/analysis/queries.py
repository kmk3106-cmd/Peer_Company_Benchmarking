"""Low-level XBRL value extraction helpers.

All functions here are pure: take a DuckDB connection + parameters,
return a pandas DataFrame. No I/O side effects.

The DB schema is the one built by `peer_benchmarking.ingest.loader`:
    val_norm, val_insurers, cntxt_insurers, role_insurers, lab_insurers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import duckdb
import pandas as pd

from peer_benchmarking.domain import peer_groups

Consolidation = Literal["consolidated", "separate", "both"]

CONSOLIDATED_MEMBER = "ifrs-full_ConsolidatedMember"
SEPARATE_MEMBER = "ifrs-full_SeparateMember"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"


@dataclass(frozen=True)
class QuerySpec:
    """Common filters for a cross-sectional or time-series query.

    Attributes:
        report_date: YYYYMMDD string (e.g. '20251231').
        consolidation: 'consolidated' | 'separate' | 'both'.
        peer_group: peer_groups.yml group name (e.g. 'life', 'all_insurers').
    """

    report_date: str
    consolidation: Consolidation = "consolidated"
    peer_group: str = "all_insurers"

    @property
    def cons_members(self) -> tuple[str, ...]:
        if self.consolidation == "consolidated":
            return (CONSOLIDATED_MEMBER,)
        if self.consolidation == "separate":
            return (SEPARATE_MEMBER,)
        return (CONSOLIDATED_MEMBER, SEPARATE_MEMBER)


def _ciks_in_clause(ciks: Sequence[str]) -> str:
    """SQL VALUES list for a CIK filter."""
    return ", ".join(f"'{c}'" for c in ciks)


def fetch_element_values(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    element_id: str,
    extra_member_filter: str | None = None,
    require_period_instant: str | None = None,
    top_level_only: bool = False,
) -> pd.DataFrame:
    """Fetch all rows for one element across the peer group.

    Joins val_insurers ⋈ cntxt_insurers to allow filtering by consolidation
    axis (and an optional extra axis member, e.g. a component member like CSM).

    Args:
        con: read-only DuckDB connection.
        spec: QuerySpec with peer_group / consolidation / report_date.
        element_id: the XBRL ELEMENT_ID to extract.
        extra_member_filter: if given, only contexts that also include this
            MEMBER_ELEMENT_ID are returned (used to slice by CSM/BEL/RA/PAA/...).
        require_period_instant: if given (YYYY-MM-DD), only contexts whose
            PERIOD_INSTANT matches are returned. Use for instant-period
            (balance-sheet) items.
        top_level_only: if True, restrict to contexts whose ONLY axis is the
            cons/sep one (no extra dimensions). Use for BS top-line items
            ("보험계약부채", 자산총계, 부채총계). Mutually exclusive with
            extra_member_filter — set one or the other.

    Returns:
        DataFrame with columns: cik, name_ko, sector, context_id, amount_krw,
        decimals, period_start, period_end, period_instant.
    """
    if top_level_only and extra_member_filter:
        raise ValueError("top_level_only and extra_member_filter are mutually exclusive")

    ciks = peer_groups.members_of(spec.peer_group)
    cik_in = _ciks_in_clause(ciks)
    cons_in = ", ".join(f"'{m}'" for m in spec.cons_members)

    if top_level_only:
        # Contexts where the ONLY axis present is the cons/sep one — this matches
        # the BS top-line (no other dimension applied). Critical for direct
        # comparison with 사업보고서 values like 27.00조 보험계약부채.
        cons_cte = f"""
        WITH cons_ctx AS (
          SELECT CIK, REPORT_DATE, CONTEXT_ID,
                 ANY_VALUE(PERIOD_START_DATE) AS PERIOD_START_DATE,
                 ANY_VALUE(PERIOD_END_DATE)   AS PERIOD_END_DATE,
                 ANY_VALUE(PERIOD_INSTANT)    AS PERIOD_INSTANT,
                 ANY_VALUE(MEMBER_ELEMENT_ID) AS cons_member
          FROM cntxt_insurers
          WHERE CIK IN ({cik_in})
            AND REPORT_DATE = ?
          GROUP BY CIK, REPORT_DATE, CONTEXT_ID
          HAVING COUNT(*) = 1
             AND ANY_VALUE(AXIS_ELEMENT_ID) = '{CONS_AXIS}'
             AND ANY_VALUE(MEMBER_ELEMENT_ID) IN ({cons_in})
        )
        """
    else:
        cons_cte = f"""
        WITH cons_ctx AS (
          SELECT DISTINCT CIK, REPORT_DATE, CONTEXT_ID,
                 PERIOD_START_DATE, PERIOD_END_DATE, PERIOD_INSTANT
          FROM cntxt_insurers
          WHERE CIK IN ({cik_in})
            AND REPORT_DATE = ?
            AND AXIS_ELEMENT_ID = '{CONS_AXIS}'
            AND MEMBER_ELEMENT_ID IN ({cons_in})
        )
        """

    sql = cons_cte
    if extra_member_filter:
        sql += f"""
    , extra_ctx AS (
      SELECT DISTINCT CIK, REPORT_DATE, CONTEXT_ID
      FROM cntxt_insurers
      WHERE CIK IN ({cik_in})
        AND REPORT_DATE = ?
        AND MEMBER_ELEMENT_ID = ?
    )
    """

    sql += """
    SELECT
      v.CIK AS cik,
      v.CONTEXT_ID AS context_id,
      v.amount_krw,
      v.DECIMALS AS decimals,
      cc.PERIOD_START_DATE AS period_start,
      cc.PERIOD_END_DATE AS period_end,
      cc.PERIOD_INSTANT AS period_instant
    FROM val_insurers v
    JOIN cons_ctx cc USING (CIK, REPORT_DATE, CONTEXT_ID)
    """
    if extra_member_filter:
        sql += "JOIN extra_ctx ec USING (CIK, REPORT_DATE, CONTEXT_ID)\n"

    sql += "WHERE v.ELEMENT_ID = ?\n  AND v.REPORT_DATE = ?\n  AND v.amount_krw IS NOT NULL\n"
    if require_period_instant:
        sql += "  AND cc.PERIOD_INSTANT = ?\n"

    params: list[str] = [spec.report_date]
    if extra_member_filter:
        params += [spec.report_date, extra_member_filter]
    params += [element_id, spec.report_date]
    if require_period_instant:
        params.append(require_period_instant)

    df = con.execute(sql, params).df()

    # Attach company metadata via in-memory join (small N)
    companies = peer_groups.load_companies()
    if not df.empty:
        df["name_ko"] = df["cik"].map(lambda c: companies[c].name_ko if c in companies else c)
        df["sector"] = df["cik"].map(lambda c: companies[c].sector if c in companies else "?")
    else:
        df["name_ko"] = pd.Series(dtype=str)
        df["sector"] = pd.Series(dtype=str)
    return df


def collapse_to_one_per_cik(
    df: pd.DataFrame,
    how: Literal["max_abs", "sum", "max"] = "max_abs",
) -> pd.DataFrame:
    """Reduce multi-context rows per CIK to one row.

    A single (element, peer, period) tuple often resolves to multiple
    CONTEXT_IDs because of secondary axes (e.g. portfolio classifications)
    that we did not filter on. Pick a deterministic single value:

    - "max_abs" (default): pick the row whose |amount_krw| is largest. This
      tends to pick the TOTAL (un-disaggregated) row.
    - "sum": sum all rows. Use when you've already filtered to disjoint
      member buckets.
    - "max": pick the largest signed value.
    """
    if df.empty:
        return df.copy()
    work = df.copy()
    if how == "max_abs":
        work["_abs"] = work["amount_krw"].abs()
        idx = work.groupby("cik")["_abs"].idxmax()
        out = work.loc[idx].drop(columns=["_abs"])
    elif how == "sum":
        out = work.groupby(["cik", "name_ko", "sector"], as_index=False)["amount_krw"].sum()
    elif how == "max":
        idx = work.groupby("cik")["amount_krw"].idxmax()
        out = work.loc[idx]
    else:
        raise ValueError(f"unknown how={how!r}")
    return out.reset_index(drop=True)
