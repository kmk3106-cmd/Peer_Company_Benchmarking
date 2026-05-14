"""미래에셋생명 21-1 보험계약부채 변동분 — LRC/LIC × 상품군 HTML 채우기.

값 단위: 조원. 값이 없거나 미공시면 빈 칸 ('—').
"""
from __future__ import annotations
import duckdb
from pathlib import Path

CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"
SEP = "ifrs-full_SeparateMember"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"

LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"

# LRC/LIC members → bucket
LRC_EXCL = "ifrs-full_NetLiabilitiesOrAssetsForRemainingCoverageExcludingLossComponentMember"
LC = "ifrs-full_LossComponentMember"
LIC = "ifrs-full_LiabilitiesForIncurredClaimsMember"

# 상품군 매핑 (TypesOfContractsAxis 멤버 → 5분류)
PRODUCT_GROUPS = {
    "death":   {"label": "사망",    "members": ["dart_LifeInsuranceMember"]},
    "health":  {"label": "건강",    "members": ["dart_HealthInsuranceMember"]},
    "pension": {"label": "연금",    "members": ["entity00112332_PensionInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember"]},
    "savings": {"label": "저축",    "members": ["entity00112332_SavingsInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember"]},
    "other":   {"label": "기타",    "members": ["dart_OtherInsuranceMember"]},
}
# 기타 = dart_OtherInsurance − (health + pension + savings)
OTHER_MEMBER = "dart_OtherInsuranceMember"

# ─── 표 라인 정의 ────────────────────────────────────────────────
# (line_key, label, element_id_or_None, period_type, indent_level, css_class)
#   period_type: 'instant_open' | 'instant_close' | 'duration'
#   element_id_or_None: None → 합계 행 (소계는 계산)

# 잔액: 미래에셋은 LRC/LIC × Life/Other 분해를 자산 측에 보고
#   net = ThatAreAssets + ThatAreLiabilities (XBRL sign 그대로 합산)
BALANCE_NET_ELEMENTS = [
    "ifrs-full_InsuranceContractsThatAreAssets",
    "ifrs-full_InsuranceContractsThatAreLiabilities",
]

LINES = [
    ("open",       "기초 잔액 (2024-12-31)",
     "__balance_net__", "instant_open", 0, "balance"),

    ("svc_header", "Ⅰ. 보험서비스결과 (P&L 반영)", None, "duration", 0, "section"),

    ("svc_exp_header", "1. 보험서비스비용", None, "duration", 1, ""),

    ("claims_incurred", "&nbsp;&nbsp;1-1. 발생사고비용 (당기 발생분)",
     "ifrs-full_IncreaseDecreaseThroughIncurredClaimsAndOtherIncurredInsuranceServiceExpensesInsuranceContractsLiabilityAsset",
     "duration", 1, ""),

    ("lic_adjust", "&nbsp;&nbsp;1-2. 과거 발생사고부채 추정 변동",
     "dart_OtherAdjustmentsOfLiabilitiesForIncurredClaimsThatAriseFromContractsWithinScopeOfIFRS17",
     "duration", 1, ""),

    ("acq_amort", "&nbsp;&nbsp;1-3. 보험취득현금흐름 상각",
     "ifrs-full_IncreaseDecreaseThroughAmortisationOfInsuranceAcquisitionCashFlowsInsuranceContractsLiabilityAsset",
     "duration", 1, ""),

    ("loss_comp", "&nbsp;&nbsp;1-4. 손실요소 인식·환입 (LRC 內 합산)",
     "ifrs-full_IncreaseDecreaseThroughEffectsOfGroupsOfOnerousContractsInitiallyRecognisedInPeriodInsuranceContractsLiabilityAsset",
     "duration", 1, ""),

    ("svc_subtotal", "보험서비스결과 소계", None, "subtotal", 0, "subtotal"),

    ("fin_header", "Ⅱ. 보험금융손익", None, "duration", 0, "section"),

    ("fin_pl",  "2. 당기손익 인식분",
     "ifrs-full_InsuranceFinanceIncomeExpensesFromInsuranceContractsIssuedRecognisedInProfitOrLoss",
     "duration", 1, ""),

    ("fin_oci", "3. 기타포괄손익 인식분 (OCI)",
     "entity00112332_InsuranceFinanceIncomeExpensesFromInsuranceContractsIssuedRecognisedInOtherComperhensiveIncomeOfIncreaseDecreaseThroughInsuranceFinanceIncomeOrExpensesInsuranceContractsLiabilityAssetOfDisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByRemainingCoverageAndIncurredClaimsTableOfItems",
     "duration", 1, ""),

    ("comp_subtotal", "총포괄손익 영향 (Ⅰ+Ⅱ)", None, "subtotal", 0, "subtotal"),

    ("cf_header", "Ⅲ. 현금흐름", None, "duration", 0, "section"),

    ("premium",   "4. 수취 보험료",
     "ifrs-full_IncreaseDecreaseThroughPremiumsReceivedForInsuranceContractsIssuedInsuranceContractsLiabilityAsset",
     "duration", 1, ""),

    ("acq_cf",   "5. 보험취득 현금흐름 (지급)",
     "ifrs-full_IncreaseDecreaseThroughInsuranceAcquisitionCashFlowsInsuranceContractsLiabilityAsset",
     "duration", 1, ""),

    ("cf_total", "6. 총 보험계약 현금흐름",
     "ifrs-full_CashFlowsFromUsedInInsuranceContracts",
     "duration", 1, ""),

    ("fin_inc_dec", "&nbsp;참고: 보험금융손익 (총변동, LRC/LIC 분배)",
     "ifrs-full_IncreaseDecreaseThroughInsuranceFinanceIncomeOrExpensesInsuranceContractsLiabilityAsset",
     "duration", 0, ""),

    ("close",    "기말 잔액 (2025-12-31)",
     "__balance_net__", "instant_close", 0, "balance"),
]


def fetch_one(con, element_id, lrclic_mem, types_member, period_type):
    """Fetch SUM(amount_krw) for the slice. Returns None if no fact."""
    if element_id is None:
        return None
    if period_type == "instant_open":
        period_filter = "AND p.PERIOD_INSTANT = '2024-12-31'"
    elif period_type == "instant_close":
        period_filter = "AND p.PERIOD_INSTANT = '2025-12-31'"
    elif period_type == "duration":
        period_filter = "AND p.PERIOD_START_DATE = '2025-01-01' AND p.PERIOD_END_DATE = '2025-12-31'"
    else:
        return None

    types_clause = ""
    types_params = []
    if types_member is not None:
        types_clause = f"""
          AND EXISTS (SELECT 1 FROM cntxt_insurers t
            WHERE t.CIK=v.CIK AND t.REPORT_DATE=v.REPORT_DATE AND t.CONTEXT_ID=v.CONTEXT_ID
              AND t.AXIS_ELEMENT_ID='{TYPES_AXIS}' AND t.MEMBER_ELEMENT_ID=?)"""
        types_params = [types_member]
    else:
        # 합계 열: TypesOfContractsAxis 가 없는 context만 (전체)
        types_clause = f"""
          AND NOT EXISTS (SELECT 1 FROM cntxt_insurers t
            WHERE t.CIK=v.CIK AND t.REPORT_DATE=v.REPORT_DATE AND t.CONTEXT_ID=v.CONTEXT_ID
              AND t.AXIS_ELEMENT_ID='{TYPES_AXIS}')"""

    sql = f"""
    SELECT SUM(v.amount_krw)
    FROM val_insurers v
    WHERE v.CIK = ?
      AND v.ELEMENT_ID = ?
      AND v.amount_krw IS NOT NULL
      AND EXISTS (SELECT 1 FROM cntxt_insurers c
        WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
          AND c.AXIS_ELEMENT_ID='{LRC_LIC_AXIS}' AND c.MEMBER_ELEMENT_ID=?)
      AND EXISTS (SELECT 1 FROM cntxt_insurers cs
        WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
          AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
      AND EXISTS (SELECT 1 FROM cntxt_insurers d
        WHERE d.CIK=v.CIK AND d.REPORT_DATE=v.REPORT_DATE AND d.CONTEXT_ID=v.CONTEXT_ID
          AND d.AXIS_ELEMENT_ID='{DISAGG_AXIS}' AND d.MEMBER_ELEMENT_ID='{ISSUED}')
      AND EXISTS (SELECT 1 FROM cntxt_insurers p
        WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
          {period_filter})
      {types_clause}
    """
    params = [CIK, element_id, lrclic_mem] + types_params
    val = con.execute(sql, params).fetchone()[0]
    return float(val) if val is not None else None


def fetch_lrc_combined(con, element_id, types_member, period_type):
    """LRC = LRC_excl + LossComponent 합산."""
    excl = fetch_one(con, element_id, LRC_EXCL, types_member, period_type)
    lc = fetch_one(con, element_id, LC, types_member, period_type)
    if excl is None and lc is None:
        return None
    return (excl or 0.0) + (lc or 0.0)


def fmt(v: float | None) -> str:
    """Format value in 억원 with sign. Empty for None."""
    if v is None:
        return "&mdash;"
    in_억 = v / 1e8
    if abs(in_억) < 0.5:  # < 0.5억 (5천만) → blank
        return "&nbsp;"
    s = f"{in_억:+,.0f}"
    return s.replace("-", "&minus;")


def fetch_other_residual(con, element_id, period_type):
    """기타 = OtherInsurance − (Health + Pension + Savings)."""
    other = lambda m: fetch_lrc_combined(con, element_id, m, period_type)
    other_total = fetch_lrc_combined(con, element_id, OTHER_MEMBER, period_type)
    health = fetch_lrc_combined(con, element_id, "dart_HealthInsuranceMember", period_type)
    pension = fetch_lrc_combined(con, element_id, "entity00112332_PensionInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember", period_type)
    savings = fetch_lrc_combined(con, element_id, "entity00112332_SavingsInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember", period_type)
    if other_total is None:
        return None
    deduct = sum(v for v in (health, pension, savings) if v is not None)
    return other_total - deduct


def fetch_other_residual_lic(con, element_id, period_type):
    other_total = fetch_one(con, element_id, LIC, OTHER_MEMBER, period_type)
    health = fetch_one(con, element_id, LIC, "dart_HealthInsuranceMember", period_type)
    pension = fetch_one(con, element_id, LIC, "entity00112332_PensionInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember", period_type)
    savings = fetch_one(con, element_id, LIC, "entity00112332_SavingsInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember", period_type)
    if other_total is None:
        return None
    deduct = sum(v for v in (health, pension, savings) if v is not None)
    return other_total - deduct


def _multi_element_sum(con, elements, side, types_member, period_type):
    """Sum across multiple element_ids on one side ('LRC' = LRC_excl+LC, or 'LIC').

    For balance lines that combine ThatAreAssets + ThatAreLiabilities (signed).
    """
    members = [LRC_EXCL, LC] if side == "LRC" else [LIC]
    total = None
    for e in elements:
        for m in members:
            v = fetch_one(con, e, m, types_member, period_type)
            if v is not None:
                total = (total or 0) + v
    return total


def compute_row(con, element_id, period_type):
    """Return dict {column_key: value} for one row."""
    if element_id is None:
        return {}

    is_balance = element_id == "__balance_net__"
    elements = BALANCE_NET_ELEMENTS if is_balance else [element_id]

    def _lrc(member):
        if is_balance:
            return _multi_element_sum(con, elements, "LRC", member, period_type)
        return fetch_lrc_combined(con, element_id, member, period_type)

    def _lic(member):
        if is_balance:
            return _multi_element_sum(con, elements, "LIC", member, period_type)
        return fetch_one(con, element_id, LIC, member, period_type)

    cells = {}
    def _sum_mems(fn, members):
        if not members:
            return None
        total = None
        for m in members:
            v = fn(m)
            if v is not None:
                total = (total or 0) + v
        return total
    for key, info in PRODUCT_GROUPS.items():
        cells[f"{key}_LRC"] = _sum_mems(_lrc, info["members"])
        cells[f"{key}_LIC"] = _sum_mems(_lic, info["members"])
    # 합계 = 5개 상품군 단순 산술합 (사망 + 건강 + 연금 + 저축 + 기타)
    def _col_sum(suffix):
        vals = [cells.get(f"{k}_{suffix}") for k in PRODUCT_GROUPS.keys()]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None
    cells["total_LRC"] = _col_sum("LRC")
    cells["total_LIC"] = _col_sum("LIC")

    def _sum(a, b):
        if a is None and b is None: return None
        return (a or 0) + (b or 0)
    cells["grand"] = _sum(cells["total_LRC"], cells["total_LIC"])
    return cells


COLS = []  # 사망 → 건강 → 연금 → 저축 → 기타 → 합계
for key in ["death", "health", "pension", "savings", "other"]:
    COLS.extend([f"{key}_LRC", f"{key}_LIC"])
COLS.extend(["total_LRC", "total_LIC", "grand"])


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

    # 1) compute each fact row
    row_values: dict[str, dict] = {}
    for line_key, label, eid, ptype, indent, css in LINES:
        if eid is None:
            row_values[line_key] = {}
        else:
            row_values[line_key] = compute_row(con, eid, ptype)

    # 2) compute subtotals
    def _sum_rows(keys: list[str]) -> dict[str, float | None]:
        out = {}
        for col in COLS:
            vals = [row_values[k].get(col) for k in keys if k in row_values]
            vals = [v for v in vals if v is not None]
            out[col] = sum(vals) if vals else None
        return out

    row_values["svc_subtotal"] = _sum_rows([
        "claims_incurred", "lic_adjust", "acq_amort", "loss_comp",
    ])
    row_values["comp_subtotal"] = _sum_rows([
        "claims_incurred", "lic_adjust", "acq_amort", "loss_comp",
        "fin_pl", "fin_oci",
    ])

    # 3) build HTML
    rows_html = []
    for line_key, label, eid, ptype, indent, css in LINES:
        cells = row_values.get(line_key, {})
        td_class = "label"
        if css == "section":
            td_class = "label section"
        elif indent:
            td_class = "label indent"
        tr_class = ""
        if css == "balance":
            tr_class = "balance"
        elif css == "subtotal":
            tr_class = "subtotal"

        tds = [f'<td class="{td_class}">{label}</td>']
        for col in COLS:
            val = cells.get(col)
            tot_class = " total-col" if col.startswith("total_") or col == "grand" else ""
            tds.append(f'<td class="num{tot_class}">{fmt(val)}</td>')
        rows_html.append(f'<tr{" class=" + chr(34) + tr_class + chr(34) if tr_class else ""}>{"".join(tds)}</tr>')

    # subtotal rows insertion already in LINES via key

    template = Path("report/21-1_보험계약부채변동_LRC_LIC_template.html").read_text(encoding="utf-8")

    # Build new tbody
    new_tbody = "\n".join(rows_html)

    # Replace tbody content
    import re
    out = re.sub(r"<tbody>.*?</tbody>",
                 f"<tbody>\n{new_tbody}\n</tbody>",
                 template, count=1, flags=re.DOTALL)

    # Replace title/H1 to mark as filled
    out = out.replace("미래에셋생명 표준 양식)", "값 채움)")
    out = out.replace("— LRC/LIC × 상품군</h1>", "— LRC/LIC × 상품군 (미래에셋생명 2025)</h1>")

    # Add a unit note that values are in 조원
    out = out.replace("(단위: 원)", "(단위: 억원 — 5천만원 미만은 빈칸, 부호: 부채 증가 +, 감소 −)")

    Path("report/21-1_보험계약부채변동_LRC_LIC_미래에셋_2025.html").write_text(out, encoding="utf-8")
    print("wrote report/21-1_보험계약부채변동_LRC_LIC_미래에셋_2025.html")

    # Console snapshot
    print()
    print("=== 합계 열 (전체 발행보험) ===")
    for line_key, label, eid, ptype, indent, css in LINES:
        c = row_values.get(line_key, {})
        lab = label.replace("&nbsp;", " ")[:38]
        lrc = c.get("total_LRC")
        lic = c.get("total_LIC")
        tot = c.get("grand")
        def f(v): return f"{v/1e8:+10,.0f}억" if v is not None else "          —"
        print(f"  {lab:38s} LRC={f(lrc)}  LIC={f(lic)}  합={f(tot)}")


if __name__ == "__main__":
    main()
