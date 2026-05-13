"""IFRS17 보험계약부채 변동분 차이조정 공시 (DI817100).

§103/§104 표준 차이조정 — 시작잔액에서 종료잔액으로 가는 변동을 다음 두 축으로 분해:
  1. 구성요소(components) axis: BEL / RA / CSM
  2. 잔여보장·발생사고(LRC/LIC) axis: LRC excl LossComponent / LossComponent / LIC

Pure functions: DuckDB con + CIK + report_date in, DataFrame out.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from peer_benchmarking.domain import liability_mapping

DI817100_ROLE = "dart_2024-06-30_role-DI817100"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
CONS_MEMBER = "ifrs-full_ConsolidatedMember"
SEP_MEMBER = "ifrs-full_SeparateMember"

COMPONENTS_AXIS = "ifrs-full_InsuranceContractsByComponentsAxis"
COMP_BEL = "ifrs-full_EstimatesOfPresentValueOfFutureCashFlowsMember"
COMP_RA = "ifrs-full_RiskAdjustmentForNonfinancialRiskMember"
COMP_CSM = "ifrs-full_ContractualServiceMarginMember"
COMPONENT_LABEL = {COMP_BEL: "BEL", COMP_RA: "RA", COMP_CSM: "CSM"}

# DART filers carry the 발행보험/보유재보험 distinction on the *Disaggregation*
# axis, not the TypesOfContracts axis. TypesOfContracts is usually loaded with
# company-specific entity-extension members (저축성/유배당/보장성/etc.).
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"
ISSUED_MEMBER = "ifrs-full_InsuranceContractsIssuedMember"

# IFRS17 §103 표준 차이조정 라인 아이템.
# (line_key, element_id, ko_label, period_type)
# period_type: "instant_prior" = 시작잔액 (전기말),
#              "instant_curr"  = 종료잔액 (당기말),
#              "duration"      = 당기 변동.
RECONCILIATION_LINES: list[tuple[str, str, str, str]] = [
    ("open_balance",
     "ifrs-full_InsuranceContractsThatAreLiabilities",
     "시작 잔액 (전기말)", "instant_prior"),

    # 미래 서비스 변동
    ("initial_recognition",
     "ifrs-full_IncreaseDecreaseThroughEffectsOfContractsInitiallyRecognisedInsuranceContractAssetLiability",
     "신계약 인식 효과", "duration"),
    ("estimate_change_adjusting_csm",
     "ifrs-full_IncreaseDecreaseThroughChangesInEstimatesThatAdjustContractualServiceMarginInsuranceContractAssetLiability",
     "추정치 변동, CSM 조정", "duration"),
    ("estimate_change_not_adjusting_csm",
     "ifrs-full_IncreaseDecreaseThroughChangesInEstimatesThatDoNotAdjustContractualServiceMarginInsuranceContractAssetLiability",
     "추정치 변동, CSM 미조정", "duration"),

    # 현행 서비스 변동
    ("csm_recognised_in_revenue",
     "ifrs-full_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossForServicesProvided",
     "CSM 당기손익 인식 (보험수익)", "duration"),
    ("ra_release",
     "ifrs-full_IncreaseDecreaseThroughChangeInRiskAdjustmentForNonfinancialRiskNotRelatedToFutureOrPastServiceInsuranceContractAssetLiability",
     "위험조정 변동 (비금융위험)", "duration"),
    ("experience_adjustment",
     "ifrs-full_IncreaseDecreaseThroughExperienceAdjustmentsInsuranceContractAssetLiability",
     "경험조정", "duration"),

    # 과거 서비스 변동
    ("past_service_change",
     "ifrs-full_IncreaseDecreaseThroughChangesThatRelateToPastServiceInsuranceContractAssetLiability",
     "과거 서비스 변동", "duration"),

    # 보험계약 현금흐름
    ("premium_received",
     "ifrs-full_IncreaseDecreaseThroughPremiumsReceivedForInsuranceContractAssetLiability",
     "수취 보험료", "duration"),
    ("claims_paid",
     "ifrs-full_IncreaseDecreaseThroughIncurredClaimsPaidAndOtherInsuranceServiceExpensesPaidInsuranceContractAssetLiability",
     "지급 보험금·서비스비용", "duration"),
    ("acquisition_cashflows",
     "ifrs-full_IncreaseDecreaseThroughInsuranceAcquisitionCashFlowsInsuranceContractAssetLiability",
     "보험취득 현금흐름", "duration"),

    # 보험금융손익
    ("finance_pl",
     "ifrs-full_InsuranceFinanceIncomeExpensesFromInsuranceContractsIssuedRecognisedInProfitOrLoss",
     "보험금융손익 (당기손익)", "duration"),

    # 기타
    ("other_changes",
     "ifrs-full_IncreaseDecreaseThroughOtherChangesLiabilitiesUnderInsuranceContractsAndReinsuranceContractsIssued",
     "기타 변동", "duration"),

    ("close_balance",
     "ifrs-full_InsuranceContractsThatAreLiabilities",
     "종료 잔액 (당기말)", "instant_curr"),
]


def _line_period_filter(line_type: str, spec: MovementSpec):
    """Return (use_instant_only, instant_date, duration_start, duration_end)."""
    if line_type == "instant_prior":
        return True, spec.prior_year_end, None, None
    if line_type == "instant_curr":
        return True, spec.period_end, None, None
    return False, None, spec.period_start, spec.period_end


def _is_real(value) -> bool:
    """True if value is a non-empty, non-NaN string."""
    if value is None:
        return False
    if isinstance(value, float):  # NaN check
        return False
    s = str(value).strip()
    return s not in ("", "nan", "None", "NaT")


def _period_bucket(row) -> str:
    """Classify a context as 시작/종료 잔액 (instant) vs 변동 (duration)."""
    if _is_real(row.get("period_instant")):
        return f"잔액@{row['period_instant']}"
    if _is_real(row.get("period_start")) and _is_real(row.get("period_end")):
        return f"변동 {row['period_start']}~{row['period_end']}"
    return "기타"


@dataclass(frozen=True)
class MovementSpec:
    cik: str
    report_date: str = "20251231"
    consolidation: str = "separate"
    period_start: str = "2025-01-01"
    period_end: str = "2025-12-31"
    prior_year_end: str = "2024-12-31"
    role_id: str = DI817100_ROLE


def _cons_member(spec: MovementSpec) -> str:
    return SEP_MEMBER if spec.consolidation == "separate" else CONS_MEMBER


def fetch_movement_raw(con: duckdb.DuckDBPyConnection, spec: MovementSpec) -> pd.DataFrame:
    """Return all (element, context) rows attached to the DI817100 role for one CIK.

    Each row carries:
        element_id, ko_label,
        axis_members (concatenated 'AXIS=MEMBER' tokens),
        period_start, period_end, period_instant,
        amount_krw, raw_value, decimals.
    """
    sql = """
    WITH role_elems AS (
      SELECT DISTINCT ELEMENT_ID
      FROM pre_insurers
      WHERE CIK = ? AND ROLE_ID = ?
    ),
    dims AS (
      SELECT CIK, CONTEXT_ID,
             STRING_AGG(MEMBER_ELEMENT_ID, ' | ' ORDER BY AXIS_ELEMENT_ID) AS members,
             STRING_AGG(AXIS_ELEMENT_ID || '=' || MEMBER_ELEMENT_ID, ' | '
                        ORDER BY AXIS_ELEMENT_ID) AS axis_members,
             ANY_VALUE(PERIOD_START_DATE) AS period_start,
             ANY_VALUE(PERIOD_END_DATE) AS period_end,
             ANY_VALUE(PERIOD_INSTANT) AS period_instant
      FROM cntxt_insurers
      WHERE CIK = ?
      GROUP BY CIK, CONTEXT_ID
    ),
    labels AS (
      SELECT ELMT_ID, MAX(CASE WHEN LANG='ko' THEN LABEL END) AS ko_label
      FROM lab_insurers
      WHERE CIK = ?
        AND LABEL_ROLE_URI = 'http://www.xbrl.org/2003/role/label'
      GROUP BY ELMT_ID
    )
    SELECT
      v.ELEMENT_ID AS element_id,
      COALESCE(l.ko_label, '') AS ko_label,
      v.CONTEXT_ID AS context_id,
      d.members,
      d.axis_members,
      d.period_start,
      d.period_end,
      d.period_instant,
      v.amount_krw,
      v.raw_value,
      v.DECIMALS AS decimals
    FROM val_insurers v
    JOIN role_elems re ON re.ELEMENT_ID = v.ELEMENT_ID
    JOIN dims d ON d.CIK = v.CIK AND d.CONTEXT_ID = v.CONTEXT_ID
    LEFT JOIN labels l ON l.ELMT_ID = v.ELEMENT_ID
    WHERE v.CIK = ?
      AND v.amount_krw IS NOT NULL
    """
    df = con.execute(sql, [spec.cik, spec.role_id, spec.cik, spec.cik, spec.cik]).df()
    return df


def filter_consolidation(df: pd.DataFrame, spec: MovementSpec) -> pd.DataFrame:
    """Keep only rows whose context contains the desired cons/sep member."""
    if df.empty:
        return df
    want = _cons_member(spec)
    mask = df["members"].fillna("").str.contains(want, regex=False)
    return df[mask].copy()


def pivot_by_components(con: duckdb.DuckDBPyConnection, spec: MovementSpec) -> pd.DataFrame:
    """§103 BEL/RA/CSM 분해 표.

    한 행 = 라인아이템 (예: 신계약 인식 효과, 추정치 변동 등)
    열 = BEL / RA / CSM / 합계
    값 = 해당 기간(또는 시점)의 amount_krw
    """
    d = liability_mapping.load()
    bel = d.components_axis.members["BEL"].element_id
    ra = d.components_axis.members["RA"].element_id
    csm = d.components_axis.members["CSM"].element_id
    component_member_map = {bel: "BEL", ra: "RA", csm: "CSM"}

    raw = fetch_movement_raw(con, spec)
    raw = filter_consolidation(raw, spec)
    if raw.empty:
        return pd.DataFrame()

    # Extract which component (if any) each row belongs to
    def _which_component(members: str | None) -> str | None:
        if not members:
            return None
        for eid, lbl in component_member_map.items():
            if eid in members:
                return lbl
        return None

    raw["component"] = raw["members"].map(_which_component)

    # Drop rows with no component dimension (those are total or other-axis rows)
    comp_df = raw.dropna(subset=["component"]).copy()
    if comp_df.empty:
        return pd.DataFrame()

    comp_df["bucket"] = comp_df.apply(_period_bucket, axis=1)

    # For each (element, period bucket), get one value per component.
    # Use max_abs to pick the most prominent context if multiple match.
    comp_df["_abs"] = comp_df["amount_krw"].abs()
    idx = comp_df.groupby(["element_id", "bucket", "component"])["_abs"].idxmax()
    one_per = comp_df.loc[idx].drop(columns=["_abs"])

    pivot = one_per.pivot_table(
        index=["element_id", "ko_label", "bucket"],
        columns="component",
        values="amount_krw",
        aggfunc="first",
    ).reset_index()
    pivot.columns.name = None
    for col in ("BEL", "RA", "CSM"):
        if col not in pivot.columns:
            pivot[col] = pd.NA
    pivot["합계"] = pivot[["BEL", "RA", "CSM"]].sum(axis=1, min_count=1)
    return pivot[["ko_label", "element_id", "bucket", "BEL", "RA", "CSM", "합계"]]


def reconciliation_103(con: duckdb.DuckDBPyConnection, spec: MovementSpec) -> pd.DataFrame:
    """IFRS17 §103 형식의 발행보험 BEL/RA/CSM 차이조정 표.

    각 라인 아이템(element_id) × 구성요소(BEL/RA/CSM) 별로:
      - 잔액(instant) lines  → InsuranceContractsIssuedThatAreLiabilities 사용
      - 변동(duration) lines → element 그대로
      - 모든 ComponentsAxis 분해 row의 amount_krw를 component member별 **SUM**
        (회사가 type axis 등으로 더 세분해 보고하면 합산해야 component 총량).

    Verified: 미래에셋 2025-12-31 component sum 26.58조 ≈ BS 27.00조 (1.6% 차이).

    Returns 14-row DataFrame:
        line_key | ko_label | period_type | BEL | RA | CSM | 합계
    """
    cons_member = _cons_member(spec)
    rows: list[dict] = []

    for line_key, element_id, ko_label, period_type in RECONCILIATION_LINES:
        use_instant, instant_date, p_start, p_end = _line_period_filter(period_type, spec)

        # 9개사 일관성: `InsuranceContractsThatAreLiabilities` (Issued 없음) 사용.
        # 미래에셋만 Issued 버전을 함께 보고하나 다른 8개사는 Non-Issued만 사용.
        # 미래에셋 분해 합산: 26.58조 (vs BS 27.00조, 1.6% 차이 - entity 확장 미보고분)
        actual_element = element_id

        if use_instant:
            period_filter_sql = "p.PERIOD_INSTANT = ?"
            period_params = [instant_date]
        else:
            period_filter_sql = "p.PERIOD_START_DATE = ? AND p.PERIOD_END_DATE = ?"
            period_params = [p_start, p_end]

        # For each component, sum amount_krw across only the minimum-n_axes
        # row family. Higher-n_axes rows are sub-breakdowns of the same fact
        # (double-counting if included). Verified: 한화 n=4 sum = 96.93조 = BS 96.94조.
        sql = f"""
        WITH ax_cnt AS (
          SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
          FROM cntxt_insurers
          WHERE CIK = ? AND REPORT_DATE = ?
          GROUP BY CIK, REPORT_DATE, CONTEXT_ID
        ),
        candidate AS (
          SELECT
            v.CIK, v.CONTEXT_ID, v.amount_krw,
            comp.MEMBER_ELEMENT_ID AS component,
            ax.n_axes
          FROM val_insurers v
          JOIN cntxt_insurers comp
            ON comp.CIK = v.CIK AND comp.REPORT_DATE = v.REPORT_DATE
           AND comp.CONTEXT_ID = v.CONTEXT_ID
           AND comp.AXIS_ELEMENT_ID = '{COMPONENTS_AXIS}'
           AND comp.MEMBER_ELEMENT_ID IN ('{COMP_BEL}', '{COMP_RA}', '{COMP_CSM}')
          JOIN ax_cnt ax
            ON ax.CIK = v.CIK AND ax.REPORT_DATE = v.REPORT_DATE
           AND ax.CONTEXT_ID = v.CONTEXT_ID
          WHERE v.CIK = ?
            AND v.ELEMENT_ID = ?
            AND v.amount_krw IS NOT NULL
            AND EXISTS (
              SELECT 1 FROM cntxt_insurers cs
              WHERE cs.CIK = v.CIK AND cs.REPORT_DATE = v.REPORT_DATE
                AND cs.CONTEXT_ID = v.CONTEXT_ID
                AND cs.AXIS_ELEMENT_ID = '{CONS_AXIS}'
                AND cs.MEMBER_ELEMENT_ID = ?
            )
            AND EXISTS (
              SELECT 1 FROM cntxt_insurers p
              WHERE p.CIK = v.CIK AND p.REPORT_DATE = v.REPORT_DATE
                AND p.CONTEXT_ID = v.CONTEXT_ID
                AND {period_filter_sql}
            )
            -- 발행보험만 (보유재보험은 DI817200에서 별도) — DisaggregationAxis
            AND EXISTS (
              SELECT 1 FROM cntxt_insurers t
              WHERE t.CIK = v.CIK AND t.REPORT_DATE = v.REPORT_DATE
                AND t.CONTEXT_ID = v.CONTEXT_ID
                AND t.AXIS_ELEMENT_ID = '{DISAGG_AXIS}'
                AND t.MEMBER_ELEMENT_ID = '{ISSUED_MEMBER}'
            )
        ),
        min_axes_per_comp AS (
          SELECT component, MIN(n_axes) AS min_n FROM candidate GROUP BY component
        )
        SELECT c.component, SUM(c.amount_krw) AS sum_amt
        FROM candidate c
        JOIN min_axes_per_comp m
          ON m.component = c.component AND c.n_axes = m.min_n
        GROUP BY c.component
        """
        params = [
            spec.cik, spec.report_date,           # ax_cnt CTE
            spec.cik, actual_element, cons_member,  # candidate filters
            *period_params,
        ]
        result = con.execute(sql, params).fetchall()

        comp_vals: dict[str, float | None] = {"BEL": None, "RA": None, "CSM": None}
        for comp_member, amt in result:
            label = COMPONENT_LABEL.get(comp_member)
            if label and amt is not None:
                comp_vals[label] = float(amt)

        bel, ra, csm = comp_vals["BEL"], comp_vals["RA"], comp_vals["CSM"]
        any_non_null = any(v is not None for v in (bel, ra, csm))
        total = sum(v for v in (bel, ra, csm) if v is not None) if any_non_null else None
        rows.append({
            "line_key": line_key,
            "ko_label": ko_label,
            "period_type": period_type,
            "BEL": bel,
            "RA": ra,
            "CSM": csm,
            "합계": total,
        })

    return pd.DataFrame(rows)


def reconciliation_103_all_peers(
    con: duckdb.DuckDBPyConnection,
    peer_group: str = "ifrs17_detailed",
    report_date: str = "20251231",
) -> dict[str, pd.DataFrame]:
    """Run reconciliation_103 for every member of a peer group.

    Returns dict[cik -> DataFrame].
    """
    from peer_benchmarking.domain import peer_groups

    ciks = peer_groups.members_of(peer_group)
    out: dict[str, pd.DataFrame] = {}
    for cik in ciks:
        spec = MovementSpec(cik=cik, report_date=report_date)
        out[cik] = reconciliation_103(con, spec)
    return out


def pivot_by_lrc_lic(con: duckdb.DuckDBPyConnection, spec: MovementSpec) -> pd.DataFrame:
    """§104 LRC/LIC 분해 표.

    LRC = LRC excl Loss Component + Loss Component
    LIC = Liabilities for Incurred Claims
    """
    d = liability_mapping.load()
    lrc_excl = d.lrc_lic_axis.members["LRC_excl_LossComponent"].element_id
    loss = d.lrc_lic_axis.members["LossComponent"].element_id
    lic = d.lrc_lic_axis.members["LIC"].element_id
    lrc_alt = d.lrc_lic_axis.members["LRC_alt"].element_id

    member_map = {
        lrc_excl: "LRC_excl_Loss",
        loss: "LossComponent",
        lic: "LIC",
        lrc_alt: "LRC_alt",
    }

    raw = fetch_movement_raw(con, spec)
    raw = filter_consolidation(raw, spec)
    if raw.empty:
        return pd.DataFrame()

    def _which_bucket(members: str | None) -> str | None:
        if not members:
            return None
        for eid, lbl in member_map.items():
            if eid in members:
                return lbl
        return None

    raw["bucket_axis"] = raw["members"].map(_which_bucket)
    lrc_df = raw.dropna(subset=["bucket_axis"]).copy()
    if lrc_df.empty:
        return pd.DataFrame()

    lrc_df["bucket"] = lrc_df.apply(_period_bucket, axis=1)

    lrc_df["_abs"] = lrc_df["amount_krw"].abs()
    idx = lrc_df.groupby(["element_id", "bucket", "bucket_axis"])["_abs"].idxmax()
    one_per = lrc_df.loc[idx].drop(columns=["_abs"])

    pivot = one_per.pivot_table(
        index=["element_id", "ko_label", "bucket"],
        columns="bucket_axis",
        values="amount_krw",
        aggfunc="first",
    ).reset_index()
    pivot.columns.name = None
    return pivot
