"""변동표 17 PASS 라인 — 8개사 실수치 횡단비교.

각 라인 (예: 수취보험료, 발생사고비용 등) × 8개사 별도·발행 FY2025 duration 합계.
n_axes-safe + element 패턴 매칭.
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
)

PEERS = [
    ("00112332", "미래에셋", "life"),
    ("00126256", "삼성생명", "life"),
    ("00113058", "한화생명", "life"),
    ("00117267", "동양생명", "life"),
    ("00139214", "삼성화재", "non_life"),
    ("00164973", "현대해상", "non_life"),
    ("00159102", "DB손보", "non_life"),
    ("00135917", "한화손보", "non_life"),
]

# 17 PASS 라인 — element_id LIKE 패턴
LINES = [
    ("보험수익",           ["ifrs-full_InsuranceRevenue"]),
    ("신계약인식",          ["%EffectsOfContractsInitiallyRecognised%"]),
    ("CSM조정추정변동",     ["%ChangesInEstimatesThatAdjustContractualServiceMargin%"]),
    ("CSM미조정추정변동",   ["%ChangesInEstimatesThatDoNotAdjustContractualServiceMargin%"]),
    ("위험조정변동",        ["%ChangeInRiskAdjustmentForNonfinancialRisk%"]),
    ("경험조정",            ["%ExperienceAdjustments%InsuranceContracts%"]),
    ("과거서비스변동",      ["%RelateToPastServiceInsuranceContracts%"]),
    ("손실부담계약손실",    ["%EffectsOfGroupsOfOnerousContracts%"]),
    ("발생사고비용",        ["%IncurredClaimsAndOtherIncurredInsuranceServiceExpenses%InsuranceContracts%"]),
    ("수취보험료",          ["%PremiumsReceivedForInsuranceContractsIssued%"]),
    ("지급보험금",          ["%IncurredClaimsPaidAndOtherInsuranceServiceExpensesPaid%InsuranceContracts%"]),
    ("보험취득CF지급",      ["%InsuranceAcquisitionCashFlowsInsuranceContracts%"]),
    ("보험취득CF상각",      ["%AmortisationOfInsuranceAcquisitionCashFlows%"]),
    ("투자요소",            ["%InvestmentComponentsExcluded%"]),
    ("금융손익_PL",         ["%InsuranceFinanceIncomeExpensesFromInsuranceContractsIssued%RecognisedInProfitOrLoss%"]),
    ("금융손익_OCI",        ["%InsuranceFinanceIncomeExpenses%RecognisedInOther%"]),
    ("기타증감",            ["%OtherChangesLiabilitiesUnderInsuranceContracts%"]),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

ROLE = "dart_2024-06-30_role-DI817100"


def find_elements_for_line(cik: str, patterns: list[str]) -> list[str]:
    """DI817100 에서 해당 라인 element 후보."""
    or_parts = " OR ".join("v.ELEMENT_ID LIKE ?" for _ in patterns)
    sql = f"""
    SELECT DISTINCT v.ELEMENT_ID FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      AND ({or_parts})
    """
    return [r[0] for r in con.execute(sql, [cik, ROLE] + patterns).fetchall()]


def fetch_line_value(cik: str, patterns: list[str]) -> float | None:
    """별도·발행·duration 합계 — n_axes-safe."""
    eids = find_elements_for_line(cik, patterns)
    if not eids: return None
    total = 0; found = False
    for eid in eids:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231",
            element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v is not None:
            total += v; found = True
    return total if found else None


# 실행: 라인 × 회사 매트릭스
print("="*120)
print("17 라인 × 8개사 실수치 횡단비교 (FY2025 별도·발행, 단위 억원)")
print("="*120)
print(f"\n  {'라인':<22s}  " + "  ".join(f"{n:>9s}" for _, n, _ in PEERS))
print("─"*120)

matrix = {}
for line_name, patterns in LINES:
    row = {}
    for cik, name, _ in PEERS:
        row[cik] = fetch_line_value(cik, patterns)
    matrix[line_name] = row

    def f(v): return f"{v/1e8:>7,.0f}억" if v is not None and abs(v) > 1e8 else "       —"
    cells = [f(row[c]) for c, _, _ in PEERS]
    print(f"  {line_name:<22s}  " + "  ".join(cells))

# 미래에셋 percentile 분석
print("\n\n" + "="*100)
print("미래에셋 자사 vs 동업사 percentile")
print("="*100)
print(f"\n  {'라인':<22s}  {'미래에셋':>11s}  {'median':>11s}  {'min':>11s}  {'max':>11s}  {'percentile':>10s}")
print("─"*100)
for line_name, _ in LINES:
    row = matrix[line_name]
    self_v = row["00112332"]
    if self_v is None: continue
    others = sorted([v for c, v in row.items() if c != "00112332" and v is not None])
    if not others: continue
    median = others[len(others)//2]
    pct = sum(1 for v in others if v < self_v) / len(others) * 100
    def f(v): return f"{v/1e8:>+8,.0f}억" if v is not None else "       —"
    print(f"  {line_name:<22s}  {f(self_v)}  {f(median)}  {f(others[0])}  {f(others[-1])}  {pct:>7.0f}%")

# JSON 저장
Path("report/line_values_matrix.json").write_text(
    json.dumps({line: {c: v for c, v in row.items()} for line, row in matrix.items()},
               ensure_ascii=False, indent=2),
    encoding="utf-8")
print("\nwrote report/line_values_matrix.json")
