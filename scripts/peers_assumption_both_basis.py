"""8개사 가정변경 element — 별도/연결 양쪽 모두 추출."""
from __future__ import annotations
import json
import duckdb

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

COMPANY_ELEMENTS = {
    "00112332": ("미래에셋", [
        ("해지율 가정변경", "%ChangeInCancellationRateAssumption%"),
        ("위험율 가정변경", "%ChangeInRiskRateAssumption%"),
        ("예정율 가정변경", "%ChangeInProjectRatioAssumption%"),
        ("기타 가정변경", "%OtherAssumptionChangesOf%"),
        ("(추가) 손실요소 변동", "%FluctuationsDueToLossFactorsOfChangesInFutureServices%"),
        ("(추가) 보유물량·투자요소", "%FluctuationsDueToVolumeDifferencesAndDifferencesInInvestmentFactors%"),
    ]),
    "00126256": ("삼성생명", [
        ("가정변경 효과 (단일)", "%EffectOfChangeInEstimateOfIncreaseDecreaseThroughChanges%"),
    ]),
    "00113058": ("한화생명", [
        ("해지율 가정변경", "%EffectsOfChangesInSurrenderRates%"),
        ("위험률 가정변경", "%EffectsOfChangesInRiskRates%"),
        ("사업비율 가정변경", "%EffectsOfChangesInExpenseRatio%"),
        ("기타 가정변경", "%EffectsOfChangesInOtherAssumption%"),
        ("가정변경 총합", "%EffectsOfChangesInAssumptionsInsuranceContracts%"),
    ]),
    "00117267": ("동양생명", [
        # 동양은 별도 가정변경 element 없음 (추정변경 통합)
    ]),
    "00139214": ("삼성화재", [
        # 미공시
    ]),
    "00164973": ("현대해상", [
        ("해지율 가정변경", "%EffectsOfChangesOfSurrenderRatioAssumption%"),
        ("위험률 가정변경", "%EffectsOfChangesOfRiskRatioAssumption%"),
        ("사업비율 가정변경", "%EffectsOfChangesOfOperatingExpenseRateAssumption%"),
        ("기타 가정변경", "%EffectsOfChangesOfOtherAssumption%"),
        ("가정변경 총합", "%EffectsOfChangesOfActuarialAssumption%"),
    ]),
    "00159102": ("DB손보", [
        ("해지율 가정변경", "%EffectsOfChangesOfSurrenderRatioAssumption%"),
        ("위험률 가정변경", "%EffectsOfChangesOfRiskRatioAssumption%"),
        ("사업비율 가정변경", "%EffectsOfChangesOfOperatingExpenseRateAssumption%"),
        ("기타 가정변경", "%EffectsOfChangesOfOtherAssumption%"),
        ("가정변경 총합", "%EffectsOfChangesOfActuarialAssumption%"),
    ]),
    "00135917": ("한화손보", [
        ("해지율 가정변경 (CSM 조정)", "%ChangesInSurrenderRatioAssumptionsThatAdjust%"),
        ("위험률 가정변경 (CSM 조정)", "%ChangesInRiskRatioAssumptionsThatAdjust%"),
        ("사업비율 가정변경 (CSM 조정)", "%ChangesInOperatingExpenseRatioAssumptionsThatAdjust%"),
        ("기타 가정변경 (CSM 조정)", "%ChangesInOtherAssumptionsThatAdjust%"),
        ("가정변경 총합 (CSM 조정)", "%ChangesInAssumptionsThatAdjustContractualServiceMargin%"),
    ]),
}


def fetch_basis(cik, element_pattern, basis_member):
    """별도 또는 연결 기준 합산 — fingerprint dedup 적용."""
    sql = """
    WITH ax AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes,
             STRING_AGG(AXIS_ELEMENT_ID || '=' || MEMBER_ELEMENT_ID, '|' ORDER BY AXIS_ELEMENT_ID, MEMBER_ELEMENT_ID) AS fp
      FROM cntxt_insurers WHERE CIK=? GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    ),
    cand AS (
      SELECT v.amount_krw, ax.n_axes, ax.fp
      FROM val_insurers v
      JOIN ax USING (CIK, REPORT_DATE, CONTEXT_ID)
      WHERE v.CIK=? AND v.ELEMENT_ID LIKE ? AND v.amount_krw IS NOT NULL
        AND EXISTS (SELECT 1 FROM cntxt_insurers c
          WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
            AND c.AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
            AND c.MEMBER_ELEMENT_ID=?)
        AND EXISTS (SELECT 1 FROM cntxt_insurers p
          WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
            AND p.PERIOD_START_DATE='2025-01-01' AND p.PERIOD_END_DATE='2025-12-31')
    ),
    minx AS (SELECT MIN(n_axes) AS m FROM cand),
    dedup AS (
      SELECT DISTINCT fp, amount_krw FROM cand, minx WHERE n_axes = minx.m
    )
    SELECT SUM(amount_krw) FROM dedup
    """
    r = con.execute(sql, [cik, cik, element_pattern,
                          "ifrs-full_SeparateMember" if basis_member == "sep" else "ifrs-full_ConsolidatedMember"]).fetchone()[0]
    return float(r) if r else None


print("="*120)
print("8개사 가정변경 element — 별도 / 연결 양쪽 (FY2025, 단위: 억원)")
print("="*120)

results = {}
for cik, (name, lines) in COMPANY_ELEMENTS.items():
    print(f"\n  ── {name} ({cik}) ──")
    if not lines:
        print(f"    ❌ 가정변경 element 미공시")
        results[cik] = {"name": name, "status": "not_disclosed", "lines": []}
        continue
    print(f"    {'라인':<26s}  {'별도':>11s}  {'연결':>11s}")
    print("    " + "─"*55)
    company_lines = []
    for label, pat in lines:
        sep_v = fetch_basis(cik, pat, "sep")
        cons_v = fetch_basis(cik, pat, "cons")
        def f(v): return f"{v/1e8:>+8,.0f}억" if v else "         —"
        marker = "✓" if sep_v else ("⚠연결" if cons_v else "·")
        print(f"    {label:<26s}  {f(sep_v)}  {f(cons_v)}  {marker}")
        company_lines.append({"label": label, "sep": sep_v, "cons": cons_v})
    results[cik] = {"name": name, "status": "extracted", "lines": company_lines}

from pathlib import Path
Path("report/peer_assumption_both.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/peer_assumption_both.json")
