"""8개사 가정변경 element — 단순 직접 SQL (별도/연결 모두, BEL/RA/CSM 분해)."""
from __future__ import annotations
import json
import duckdb

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 회사별 정확 element 패턴
COMPANY_ELEMENTS = {
    "00112332": ("미래에셋", [
        ("해지율 가정변경", "%ChangeInCancellationRateAssumption%"),
        ("위험율 가정변경", "%ChangeInRiskRateAssumption%"),
        ("예정율 가정변경", "%ChangeInProjectRatioAssumption%"),
        ("기타 가정변경", "%OtherAssumptionChangesOfEffectOfChangingAssumptions%"),
        ("(추가) 손실요소 변동", "%FluctuationsDueToLossFactorsOfChanges%"),
        ("(추가) 보유물량·투자요소", "%FluctuationsDueToVolumeDifferencesAndDifferencesInInvestmentFactors%"),
    ]),
    "00126256": ("삼성생명", [
        ("가정변경 효과 (단일)", "%EffectOfChangeInEstimateOfIncreaseDecreaseThroughChanges%"),
    ]),
    "00113058": ("한화생명", [
        ("해지율 가정변경", "%EffectsOfChangesInSurrenderRatesInsuranceContracts%"),
        ("위험률 가정변경", "%EffectsOfChangesInRiskRatesInsuranceContracts%"),
        ("사업비율 가정변경", "%EffectsOfChangesInExpenseRatioInsuranceContracts%"),
        ("기타 가정변경", "%EffectsOfChangesInOtherAssumptionInsuranceContracts%"),
        ("가정변경 총합", "%EffectsOfChangesInAssumptionsInsuranceContractsLiabilityAssetOfIncreaseDecreaseOther%"),
    ]),
    "00117267": ("동양생명", []),
    "00139214": ("삼성화재", []),
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

# AXIS 정의
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
SEP = "ifrs-full_SeparateMember"
CONS = "ifrs-full_ConsolidatedMember"
COMP_AXIS = "ifrs-full_InsuranceContractsByComponentsAxis"
BEL = "ifrs-full_EstimatesOfPresentValueOfFutureCashFlowsMember"
RA = "ifrs-full_RiskAdjustmentForNonfinancialRiskMember"
CSM_MEMBERS = [
    "ifrs-full_ContractualServiceMarginMember",
    "ifrs-full_ContractualServiceMarginNotRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachOrFairValueApproachHasBeenAppliedMember",
    "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachHasBeenAppliedMember",
    "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichFairValueApproachHasBeenAppliedMember",
]


def fetch(cik, eid_pattern, basis_member, comp_member=None):
    """단순 직접 SQL — fingerprint dedup."""
    sql = f"""
    WITH cand AS (
      SELECT DISTINCT
        STRING_AGG(cx.AXIS_ELEMENT_ID || '=' || cx.MEMBER_ELEMENT_ID, '|'
                   ORDER BY cx.AXIS_ELEMENT_ID, cx.MEMBER_ELEMENT_ID) AS fp,
        v.amount_krw
      FROM val_insurers v
      JOIN cntxt_insurers cx ON cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
      WHERE v.CIK=? AND v.ELEMENT_ID LIKE ? AND v.amount_krw IS NOT NULL
        AND EXISTS (SELECT 1 FROM cntxt_insurers c WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
          AND c.AXIS_ELEMENT_ID='{CONS_AXIS}' AND c.MEMBER_ELEMENT_ID=?)
        AND EXISTS (SELECT 1 FROM cntxt_insurers p WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
          AND p.PERIOD_START_DATE='2025-01-01' AND p.PERIOD_END_DATE='2025-12-31')
        {f"AND EXISTS (SELECT 1 FROM cntxt_insurers cm WHERE cm.CIK=v.CIK AND cm.REPORT_DATE=v.REPORT_DATE AND cm.CONTEXT_ID=v.CONTEXT_ID AND cm.AXIS_ELEMENT_ID='{COMP_AXIS}' AND cm.MEMBER_ELEMENT_ID=?)" if comp_member else ""}
      GROUP BY v.CONTEXT_ID, v.amount_krw
    )
    SELECT SUM(amount_krw) FROM (SELECT DISTINCT fp, amount_krw FROM cand)
    """
    params = [cik, eid_pattern, basis_member]
    if comp_member: params.append(comp_member)
    r = con.execute(sql, params).fetchone()[0]
    return float(r) if r else None


def fetch_csm_all(cik, eid_pattern, basis_member):
    total = 0; found = False
    for m in CSM_MEMBERS:
        v = fetch(cik, eid_pattern, basis_member, m)
        if v is not None:
            total += v; found = True
    return total if found else None


# 8개사 추출 (별도·연결 모두)
all_data = {}
for cik, (name, lines) in COMPANY_ELEMENTS.items():
    print(f"\n{'='*100}")
    print(f"  {name} ({cik})")
    print(f"{'='*100}")
    if not lines:
        print(f"  ❌ 가정변경 element 미공시")
        all_data[cik] = {"name": name, "status": "not_disclosed", "lines": []}
        continue

    print(f"  {'라인':<26s}  ─── 별도 ───              ─── 연결 ───")
    print(f"  {'':<26s}  {'BEL':>9s} {'RA':>9s} {'CSM':>9s}  {'BEL':>9s} {'RA':>9s} {'CSM':>9s}")
    print("  " + "─"*110)
    company_lines = []
    for label, pat in lines:
        sep_bel = fetch(cik, pat, SEP, BEL)
        sep_ra = fetch(cik, pat, SEP, RA)
        sep_csm = fetch_csm_all(cik, pat, SEP)
        cons_bel = fetch(cik, pat, CONS, BEL)
        cons_ra = fetch(cik, pat, CONS, RA)
        cons_csm = fetch_csm_all(cik, pat, CONS)

        def f(v): return f"{v/1e8:>+7,.0f}억" if v is not None else "        —"
        print(f"  {label:<26s}  {f(sep_bel)} {f(sep_ra)} {f(sep_csm)}  {f(cons_bel)} {f(cons_ra)} {f(cons_csm)}")

        company_lines.append({
            "label": label, "pattern": pat,
            "sep": {"BEL": sep_bel, "RA": sep_ra, "CSM": sep_csm},
            "cons": {"BEL": cons_bel, "RA": cons_ra, "CSM": cons_csm},
        })

    all_data[cik] = {"name": name, "status": "extracted", "lines": company_lines}

from pathlib import Path
Path("report/peer_assumption_final.json").write_text(
    json.dumps(all_data, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print(f"\nwrote report/peer_assumption_final.json")
