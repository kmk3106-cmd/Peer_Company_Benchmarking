"""CSM 상각률 + 계리적 가정 변동내역 추출.

CSM 상각률 = 당기 CSM 상각액 / 평균 CSM × 100%
  평균 CSM = (기시 + 기말) / 2

CSM 상각 element 후보:
  - ifrs-full_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices
  - dart_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices
  - ifrs-full_IncreaseDecreaseThroughRecognitionOfContractualServiceMarginInsuranceContracts
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, fetch_csm_total_all_variants,
    CONS_AXIS, SEP_MEMBER, COMPONENTS_AXIS, COMP_CSM_ALL,
    DISAGG_AXIS, ISSUED_MEMBER,
)

PEERS = [
    ("00112332", "미래에셋"),
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손보"),
    ("00135917", "한화손보"),
]

CSM_AMORT_PATTERNS = [
    "ifrs-full_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices",
    "dart_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices",
    "ifrs-full_IncreaseDecreaseThroughRecognitionOfContractualServiceMarginInsuranceContractsLiabilityAsset",
    "ifrs-full_IncreaseDecreaseThroughRecognitionOfContractualServiceMargin",
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def fetch_csm_amortization(cik: str) -> float | None:
    """CSM 상각액 — 여러 element 후보 + CSM transition 멤버 합산. 절대값 큰 것."""
    total = 0; found = False
    for elem in CSM_AMORT_PATTERNS:
        # CSM axis 멤버별로 합산
        for csm_member in COMP_CSM_ALL:
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=elem,
                required_members={
                    CONS_AXIS: SEP_MEMBER,
                    COMPONENTS_AXIS: csm_member,
                },
                period_range=("2025-01-01", "2025-12-31"),
            ))
            if v is not None:
                total += v; found = True
        # without components axis (broader)
        v2 = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=elem,
            required_members={CONS_AXIS: SEP_MEMBER},
            forbidden_axes=(COMPONENTS_AXIS,),
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v2 is not None:
            # broader 값이 더 크면 그것을 사용 (중복 회피)
            if abs(v2) > abs(total):
                total = v2
    return total if found or total else None


print("="*100)
print("CSM 상각률 — 당기 상각 / 평균 CSM × 100%")
print("="*100)
print(f"\n  {'회사':<10s}  {'기시 CSM':>12s}  {'기말 CSM':>12s}  {'평균 CSM':>12s}  {'당기 상각':>12s}  {'상각률':>9s}  비고")
print("─"*100)

results = {}
for cik, name in PEERS:
    beg = fetch_csm_total_all_variants(con, cik, "20251231", "2024-12-31")
    end = fetch_csm_total_all_variants(con, cik, "20251231", "2025-12-31")
    amort = fetch_csm_amortization(cik)
    avg = ((beg or 0) + (end or 0)) / 2 if (beg and end) else None

    rate = None
    if amort and avg and abs(avg) > 1e8:
        rate = abs(amort) / abs(avg) * 100

    def f(v): return f"{v/1e8:>+9,.0f}억" if v else "        —"
    rate_s = f"{rate:>7.1f}%" if rate else "      —"

    note = ""
    if rate is not None:
        if rate < 5: note = "상각률 매우 낮음 (장기·VFA 위주)"
        elif rate < 15: note = "정상 범위 (장기)"
        elif rate < 30: note = "중기"
        else: note = "단기 위주 또는 element 한계"

    print(f"  {name:<8s}  {f(beg)}  {f(end)}  {f(avg)}  {f(amort)}  {rate_s}  {note}")
    results[cik] = {"beg": beg, "end": end, "avg": avg, "amort": amort, "rate": rate}

Path("report/csm_amortization.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/csm_amortization.json")


# ─── 가정 변동내역 (자사 미래에셋 위주) ───
print("\n\n" + "="*100)
print("계리적 가정 변동내역 — 8개사 (FY2025 별도·발행, 억원)")
print("="*100)

ASSUMPTION_LINES = [
    ("신계약 효과", ["%EffectsOfContractsInitiallyRecognised%"]),
    ("CSM 조정 추정변동", ["%ChangesInEstimatesThatAdjustContractualServiceMargin%"]),
    ("CSM 미조정 추정변동", ["%ChangesInEstimatesThatDoNotAdjustContractualServiceMargin%"]),
    ("위험조정 변동", ["%ChangeInRiskAdjustmentForNonfinancialRisk%"]),
    ("경험조정", ["%ExperienceAdjustments%InsuranceContracts%"]),
    ("손실부담계약 손실(환입)", ["%EffectsOfGroupsOfOnerousContracts%"]),
    ("할인률·금융가정 변경", ["%ChangeEffectOfDiscountRateAndFinancialAssumption%", "%할인%금융%"]),
    ("위험율 가정변경", ["%ChangeInRiskRateAssumption%"]),
    ("해지율 가정변경", ["%ChangeInCancellationRateAssumption%"]),
    ("환율변동 효과", ["%ChangesInForeignExchangeRates%"]),
]


def find_elements(cik, patterns):
    or_parts = " OR ".join("v.ELEMENT_ID LIKE ?" for _ in patterns)
    sql = f"""
    SELECT DISTINCT v.ELEMENT_ID FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817100' AND v.amount_krw IS NOT NULL
      AND ({or_parts})
    """
    return [r[0] for r in con.execute(sql, [cik] + patterns).fetchall()]


def fetch_assumption_line(cik, patterns):
    eids = find_elements(cik, patterns)
    if not eids: return None
    total = 0; found = False
    for eid in eids:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v is not None:
            total += v; found = True
    return total if found else None


print(f"\n  {'가정 항목':<22s}  " + "  ".join(f"{n:>9s}" for _, n in PEERS))
print("─"*120)

assumption_data = {}
for label, patterns in ASSUMPTION_LINES:
    row = {}
    for cik, name in PEERS:
        v = fetch_assumption_line(cik, patterns)
        row[cik] = v
    assumption_data[label] = row
    cells = []
    for cik, _ in PEERS:
        v = row[cik]
        cells.append(f"{v/1e8:>+7,.0f}억" if v else "       —")
    print(f"  {label:<22s}  " + "  ".join(cells))

Path("report/assumption_changes.json").write_text(
    json.dumps(assumption_data, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/assumption_changes.json")
