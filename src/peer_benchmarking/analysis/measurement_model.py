"""회계모형(GMM/VFA/PAA)별 보험계약부채 분해.

Standard IFRS17 axis split: PAA vs Non-PAA.
GMM/VFA는 entity 확장 member로 표현 → 라벨 키워드로 자동 매핑.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from peer_benchmarking.analysis.queries import (
    QuerySpec,
    _ciks_in_clause,
    collapse_to_one_per_cik,
    fetch_element_values,
)
from peer_benchmarking.domain import liability_mapping, peer_groups


def by_standard_model(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    period_instant: str | None = "2025-12-31",
) -> pd.DataFrame:
    """PAA vs Non-PAA 분해 (표준 axis).

    Returns long DataFrame:
        cik | name_ko | sector | model | amount_krw | period_instant
        where model ∈ {'PAA', 'NonPAA'}.
    """
    d = liability_mapping.load()
    total = d.liability_balance["total_liability_for_decomposition"].element_id
    parts = []
    for model_key in ("PAA", "NonPAA"):
        member = d.measurement_model_axis.members[model_key].element_id
        df = fetch_element_values(
            con,
            spec,
            element_id=total,
            extra_member_filter=member,
            require_period_instant=period_instant,
        )
        df = collapse_to_one_per_cik(df, how="max_abs")
        df["model"] = model_key
        df["ko_label"] = d.measurement_model_axis.members[model_key].ko_label
        parts.append(df[["cik", "name_ko", "sector", "model", "ko_label", "amount_krw", "period_instant"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def discover_extension_model_members(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
) -> pd.DataFrame:
    """Scan cntxt + lab for entity-extension members that name GMM/VFA.

    Returns DataFrame: cik | member_element_id | model | ko_label.
    Includes all 11 peers' entity-specific GMM/VFA member declarations.
    """
    ciks = peer_groups.members_of(spec.peer_group)
    cik_in = _ciks_in_clause(ciks)
    sql = f"""
    SELECT DISTINCT
      c.CIK,
      c.MEMBER_ELEMENT_ID AS member_element_id,
      l.LABEL AS ko_label
    FROM cntxt_insurers c
    JOIN lab_insurers l
      ON l.ELMT_ID = c.MEMBER_ELEMENT_ID
     AND l.LANG = 'ko'
     AND l.LABEL_ROLE_URI = 'http://www.xbrl.org/2003/role/label'
     AND l.CIK = c.CIK
    WHERE c.CIK IN ({cik_in})
      AND c.REPORT_DATE = ?
      AND c.MEMBER_ELEMENT_ID LIKE 'entity%'
      AND (l.LABEL LIKE '%일반모형%' OR l.LABEL LIKE '%변동수수료%'
           OR l.LABEL LIKE '%General Model%' OR l.LABEL LIKE '%Variable Fee%'
           OR l.LABEL LIKE '%직접참여%')
    """
    df = con.execute(sql, [spec.report_date]).df()
    if df.empty:
        return pd.DataFrame(columns=["cik", "member_element_id", "ko_label", "model"])
    df["model"] = df["ko_label"].map(liability_mapping.detect_measurement_model)
    return df.dropna(subset=["model"])


def by_extended_model(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    period_instant: str | None = "2025-12-31",
) -> pd.DataFrame:
    """Per-company GMM/VFA decomposition using entity-extension members.

    For each peer that declares entity-extension GMM/VFA members, sum the
    boiler-plate `InsuranceContractsThatAreLiabilities` filtered to those
    member contexts. Companies without extension members are returned with
    NaN amounts (use `by_standard_model` instead for those).

    Returns long DataFrame:
        cik | name_ko | sector | model | amount_krw | period_instant
        where model ∈ {'GMM', 'VFA'}.
    """
    members = discover_extension_model_members(con, spec)
    if members.empty:
        return pd.DataFrame(
            columns=["cik", "name_ko", "sector", "model", "amount_krw", "period_instant"]
        )

    d = liability_mapping.load()
    total = d.liability_balance["total_liability_for_decomposition"].element_id
    rows: list[dict] = []
    for _, m in members.iterrows():
        # Run a single-CIK fetch reusing fetch_element_values with peer_group hack:
        # we just join through the existing helper but filter to one CIK afterward.
        df = fetch_element_values(
            con,
            spec,
            element_id=total,
            extra_member_filter=m["member_element_id"],
            require_period_instant=period_instant,
        )
        df = df[df["cik"] == m["cik"]]
        df = collapse_to_one_per_cik(df, how="max_abs")
        if df.empty:
            continue
        row = df.iloc[0]
        rows.append({
            "cik": m["cik"],
            "name_ko": row["name_ko"],
            "sector": row["sector"],
            "model": m["model"],
            "amount_krw": float(row["amount_krw"]),
            "period_instant": row["period_instant"],
        })
    return pd.DataFrame(rows)


def model_share(
    con: duckdb.DuckDBPyConnection,
    spec: QuerySpec,
    period_instant: str | None = "2025-12-31",
) -> pd.DataFrame:
    """Convenience: PAA vs Non-PAA + share% across peers.

    Returns: cik | name_ko | sector | paa_amount | nonpaa_amount | total |
             paa_share | nonpaa_share
    """
    df = by_standard_model(con, spec, period_instant=period_instant)
    if df.empty:
        return df
    pivot = df.pivot_table(
        index=["cik", "name_ko", "sector"],
        columns="model",
        values="amount_krw",
        aggfunc="first",
    ).reset_index()
    pivot.columns.name = None
    pivot = pivot.rename(columns={"PAA": "paa_amount", "NonPAA": "nonpaa_amount"})
    pivot["paa_amount"] = pivot.get("paa_amount", pd.Series(dtype=float)).fillna(0.0)
    pivot["nonpaa_amount"] = pivot.get("nonpaa_amount", pd.Series(dtype=float)).fillna(0.0)
    pivot["total"] = pivot["paa_amount"] + pivot["nonpaa_amount"]
    pivot["paa_share"] = pivot["paa_amount"] / pivot["total"].where(pivot["total"] != 0)
    pivot["nonpaa_share"] = pivot["nonpaa_amount"] / pivot["total"].where(pivot["total"] != 0)
    return pivot.sort_values("total", ascending=False).reset_index(drop=True)
