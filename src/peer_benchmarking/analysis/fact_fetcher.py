"""표준 fact fetcher — n_axes redundancy 회피.

DART XBRL은 같은 fact를 여러 axis 조합 (n_axes 다른 레벨)으로 중복 보고함.
같은 (CIK, ELEMENT_ID, period, target axis members) 슬라이스에서 fact를 합산할 때
n_axes 다른 row들을 모두 더하면 6x 등으로 부풀려진다.

이 모듈의 모든 함수는 MIN(n_axes) row family만 합산하여 중복을 회피한다.

사용 패턴:
    from peer_benchmarking.analysis.fact_fetcher import fetch_fact_sum, FactQuery

    val = fetch_fact_sum(con, FactQuery(
        cik="00112332", report_date="20251231",
        element_id="ifrs-full_InsuranceContractsIssuedThatAreLiabilities",
        required_members={
            CONS_AXIS: SEP_MEMBER,
        },
        period_instant="2025-12-31",
    ))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import duckdb

CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
SEP_MEMBER = "ifrs-full_SeparateMember"
CONS_MEMBER = "ifrs-full_ConsolidatedMember"

DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"
ISSUED_MEMBER = "ifrs-full_InsuranceContractsIssuedMember"
HELD_MEMBER = "ifrs-full_ReinsuranceContractsHeldMember"

TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
COMPONENTS_AXIS = "ifrs-full_InsuranceContractsByComponentsAxis"

LRC_EXCL = "ifrs-full_NetLiabilitiesOrAssetsForRemainingCoverageExcludingLossComponentMember"
LC = "ifrs-full_LossComponentMember"
LIC = "ifrs-full_LiabilitiesForIncurredClaimsMember"

COMP_BEL = "ifrs-full_EstimatesOfPresentValueOfFutureCashFlowsMember"
COMP_RA = "ifrs-full_RiskAdjustmentForNonfinancialRiskMember"
COMP_CSM = "ifrs-full_ContractualServiceMarginMember"

# CSM 표준 멤버 + transition 분해 멤버 (회사 따라 둘 중 하나 또는 둘 다 사용)
COMP_CSM_ALL = (
    "ifrs-full_ContractualServiceMarginMember",
    "ifrs-full_ContractualServiceMarginNotRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachOrFairValueApproachHasBeenAppliedMember",
    "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachHasBeenAppliedMember",
    "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichFairValueApproachHasBeenAppliedMember",
)


@dataclass(frozen=True)
class FactQuery:
    """n_axes-safe fact 슬라이스 정의.

    필드:
        cik, report_date: 회사·보고일 키
        element_id: 대상 XBRL element
        required_members: {axis_id: member_id} — 컨텍스트가 반드시 포함해야 할 axis-member 조합
        forbidden_axes: tuple[str, ...] — 컨텍스트가 절대 포함하면 안 되는 axis (예: lrclic 차원 없는 broad fact를 잡고 싶을 때)
        period_instant: 'YYYY-MM-DD' — 시점 (instant) period
        period_range: ('start','end') — 기간 (duration) period
    """
    cik: str
    report_date: str
    element_id: str
    required_members: dict[str, str] = field(default_factory=dict)
    forbidden_axes: tuple[str, ...] = field(default_factory=tuple)
    period_instant: Optional[str] = None
    period_range: Optional[tuple[str, str]] = None


def fetch_fact_sum(con: duckdb.DuckDBPyConnection, q: FactQuery) -> Optional[float]:
    """슬라이스에 매칭되는 fact의 SUM(amount_krw) — MIN(n_axes) row family만 합산.

    None 반환: 매칭 fact 없음.
    """
    # WHERE 절 구성
    where = ["v.CIK = ?", "v.REPORT_DATE = ?", "v.ELEMENT_ID = ?", "v.amount_krw IS NOT NULL"]
    params = [q.cik, q.report_date, q.element_id]

    for axis, member in q.required_members.items():
        where.append(f"""EXISTS (SELECT 1 FROM cntxt_insurers c
            WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
              AND c.AXIS_ELEMENT_ID='{axis}' AND c.MEMBER_ELEMENT_ID='{member}')""")

    for axis in q.forbidden_axes:
        where.append(f"""NOT EXISTS (SELECT 1 FROM cntxt_insurers c
            WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
              AND c.AXIS_ELEMENT_ID='{axis}')""")

    if q.period_instant:
        where.append("""EXISTS (SELECT 1 FROM cntxt_insurers p
            WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
              AND p.PERIOD_INSTANT = ?)""")
        params.append(q.period_instant)
    if q.period_range:
        where.append("""EXISTS (SELECT 1 FROM cntxt_insurers p
            WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
              AND p.PERIOD_START_DATE = ? AND p.PERIOD_END_DATE = ?)""")
        params.extend(q.period_range)

    where_sql = "\n  AND ".join(where)

    # n_axes-safe SUM:
    #   1) MIN(n_axes) row family만 사용 (sub-breakdown redundancy 회피)
    #   2) 그 중 distinct context fingerprint 단위로 dedup
    #      → 같은 axis-member 조합 context 가 여러 sub-table 에서 인용되어 중복 보고된 경우
    #         같은 값이 중복 카운트되지 않게.
    # context fingerprint = STRING_AGG(axis_id || '=' || member_id) — context의 차원 시그니처
    sql = f"""
    WITH ax_cnt AS (
      SELECT cx.CIK, cx.REPORT_DATE, cx.CONTEXT_ID,
             COUNT(*) AS n_axes,
             STRING_AGG(cx.AXIS_ELEMENT_ID || '=' || cx.MEMBER_ELEMENT_ID, '|'
                        ORDER BY cx.AXIS_ELEMENT_ID, cx.MEMBER_ELEMENT_ID) AS fingerprint
      FROM cntxt_insurers cx
      WHERE cx.CIK = ? AND cx.REPORT_DATE = ?
      GROUP BY cx.CIK, cx.REPORT_DATE, cx.CONTEXT_ID
    ),
    candidate AS (
      SELECT v.amount_krw, ax.n_axes, ax.fingerprint
      FROM val_insurers v
      JOIN ax_cnt ax USING (CIK, REPORT_DATE, CONTEXT_ID)
      WHERE {where_sql}
    ),
    min_n AS (SELECT MIN(n_axes) AS m FROM candidate),
    dedup AS (
      -- 같은 fingerprint(차원 시그니처) + 같은 amount → 1개로
      SELECT DISTINCT c.fingerprint, c.amount_krw
      FROM candidate c, min_n
      WHERE c.n_axes = min_n.m
    )
    SELECT SUM(amount_krw) FROM dedup
    """
    all_params = [q.cik, q.report_date] + params
    val = con.execute(sql, all_params).fetchone()[0]
    return float(val) if val is not None else None


def fetch_balance_separate_issued(con, cik: str, report_date: str, period_instant: str) -> Optional[float]:
    """별도·발행 기준 보험계약부채 잔액 — BS 검증용 표준 쿼리.

    `InsuranceContractsIssuedThatAreLiabilities` 단일 element, 최소 axis (별도 only)에서 SUM.
    """
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date=report_date,
        element_id="ifrs-full_InsuranceContractsIssuedThatAreLiabilities",
        required_members={CONS_AXIS: SEP_MEMBER},
        period_instant=period_instant,
    ))


def fetch_balance_net_by_types(
    con, cik: str, report_date: str,
    types_member: str, period_instant: str,
) -> Optional[float]:
    """상품군별 잔액 — ThatAreAssets + ThatAreLiabilities 부호합 (LRC/LIC 차원 포함).

    회사가 LRC/LIC axis 로만 잔액 보고하는 경우 사용.
    """
    total: Optional[float] = None
    for elem in (
        "ifrs-full_InsuranceContractsThatAreAssets",
        "ifrs-full_InsuranceContractsThatAreLiabilities",
    ):
        for lrclic in (LRC_EXCL, LC, LIC):
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date=report_date, element_id=elem,
                required_members={
                    CONS_AXIS: SEP_MEMBER,
                    DISAGG_AXIS: ISSUED_MEMBER,
                    TYPES_AXIS: types_member,
                    LRC_LIC_AXIS: lrclic,
                },
                period_instant=period_instant,
            ))
            if v is not None:
                total = (total or 0) + v
    return total


def fetch_csm_total_all_variants(
    con, cik: str, report_date: str, period_instant: str,
) -> Optional[float]:
    """CSM 잔액 — priority resolution (표준 vs transition).

    Transition 3 멤버는 standard CSMMember 의 sub-decomposition.
    따라서 합산 시 2x 중복. Priority:
      1차: standard `ContractualServiceMarginMember` (있으면 그것만)
      2차: transition 3 멤버 합 (1차 없으면)
    """
    # 1차: standard CSM
    standard = fetch_components_total(con, cik, report_date, COMP_CSM, period_instant)
    if standard is not None and abs(standard) > 1e9:  # > 10억 → 의미있는 값
        return standard

    # 2차: transition 3 멤버 합
    total: Optional[float] = None
    for member in COMP_CSM_ALL[1:]:  # standard 제외
        v = fetch_components_total(con, cik, report_date, member, period_instant)
        if v is not None:
            total = (total or 0) + v
    return total


def fetch_components_total(
    con, cik: str, report_date: str,
    component_member: str, period_instant: str,
) -> Optional[float]:
    """BEL/RA/CSM 기말 잔액 — 별도·발행 + components_axis.

    회사가 같은 잔액을 두 element 셋으로 보고할 수 있음:
      A) `InsuranceContractsIssued{ThatAreLiabilities|ThatAreAssets}` (Issued 포함, n_axes 작음)
      B) `InsuranceContracts{ThatAreLiabilities|ThatAreAssets}` (Issued 없음, LRC/LIC × types 추가 분해, n_axes 큼)

    A 가 broader (= sub-decomposition 적음). A 시도 → 없으면 B fallback.
    A와 B를 합산하면 중복 카운트 (같은 fact 의 두 view).
    """
    # 1차: Issued 접미사 element (broader view)
    total: Optional[float] = None
    for elem in (
        "ifrs-full_InsuranceContractsIssuedThatAreLiabilities",
        "ifrs-full_InsuranceContractsIssuedThatAreAssets",
    ):
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date=report_date, element_id=elem,
            required_members={
                CONS_AXIS: SEP_MEMBER,
                COMPONENTS_AXIS: component_member,
            },
            period_instant=period_instant,
        ))
        if v is not None:
            total = (total or 0) + v
    if total is not None and abs(total) > 1e9:  # > 10억 → 의미있는 값
        return total

    # 2차 fallback: Issued 없는 element (LRC/LIC × types 추가 분해 — 미래에셋 외 일부 회사)
    total = None
    for elem in (
        "ifrs-full_InsuranceContractsThatAreLiabilities",
        "ifrs-full_InsuranceContractsThatAreAssets",
    ):
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date=report_date, element_id=elem,
            required_members={
                CONS_AXIS: SEP_MEMBER,
                DISAGG_AXIS: ISSUED_MEMBER,
                COMPONENTS_AXIS: component_member,
            },
            period_instant=period_instant,
        ))
        if v is not None:
            total = (total or 0) + v
    return total
