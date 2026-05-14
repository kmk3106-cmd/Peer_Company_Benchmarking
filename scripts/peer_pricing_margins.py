"""8개사 가격책정 마진 — 위험보험료 vs 예상보험금, 예정유지비 vs 예상유지비.

자사 entity 확장 element와 7개 동업사 entity 확장 element를 매핑하여 비교.
용어: '예실차'가 아닌 '가격책정 보수성 마진' (pricing margin / 사업비 마진).
- 위험률 마진 = (위험보험료 - 예상보험금) / 위험보험료 = 1 - (예상/위험)
- 사업비 마진 = (예정유지비 - 예상유지비) / 예정유지비 = 1 - (예상/예정)
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb

PEER_ELEMS = {
    "00112332": ("미래에셋", {
        "risk_premium":  ["entity00112332_RiskInsurancePremiumOfExpectedInsurancePayoutComparedToRiskPremiumOfExpectedInsurancePayoutComparedToRiskPremiumTableOfItems"],
        "expected_claim":["entity00112332_ExpectedInsuranceAmountOfExpectedInsurancePayoutComparedToRiskPremiumOfExpectedInsurancePayoutComparedToRiskPremiumTableOfItems"],
        "planned_maint": ["entity00112332_ScheduledMaintenanceCostOfExpectedMaintenanceCostComparedToPlannedMaintenanceCostEtcOfExpectedMaintenanceCostComparedToPlannedMaintenanceCostEtcTableOfItems"],
        "expected_maint":["entity00112332_ExpectedMaintenanceCostsEtcOfExpectedMaintenanceCostComparedToPlannedMaintenanceCostEtcOfExpectedMaintenanceCostComparedToPlannedMaintenanceCostEtcTableOfItems"],
    }),
    "00126256": ("삼성생명", {
        "risk_premium":  ["entity00126256_RiskPremiumOfDetailOfClaimsIncurredDuringPeriodMeasuredAtAmountsExpectedComparedToRiskPremiumLifeInsuranceOfDetailOfClaimsIncurredDuringPeriodMeasuredAtAmountsExpectedComparedToRiskPremiumLifeInsuranceTableOfItems"],
        "expected_claim":["entity00126256_ExpectedInsurancePremiumsOfDetailOfClaimsIncurredDuringPeriodMeasuredAtAmountsExpectedComparedToRiskPremiumLifeInsuranceOfDetailOfClaimsIncurredDuringPeriodMeasuredAtAmountsExpectedComparedToRiskPremiumLifeInsuranceTableOfItems"],
        "planned_maint": ["entity00126256_ProjectedMaintenanceExpenseOfDisclosureOfExpectedMaintenanceExpenseComparedToProjectedMaintenanceExpenseLifeInsuranceOfDisclosureOfExpectedMaintenanceExpenseComparedToProjectedMaintenanceExpenseLifeInsuranceTableOfItems"],
        "expected_maint":[],
    }),
    "00113058": ("한화생명", {
        "risk_premium":  ["entity00113058_RiskPremiumOfExpectedClaimsByPeriodComparedToRiskPremiumsLineItemsOfExpectedClaimsByPeriodComparedToRiskPremiumsTableOfItems"],
        "expected_claim":["entity00113058_ExpectedClaimOfExpectedClaimsByPeriodComparedToRiskPremiumsLineItemsOfExpectedClaimsByPeriodComparedToRiskPremiumsTableOfItems"],
        "planned_maint": [],
        "expected_maint":[],
    }),
    "00117267": ("동양생명", {
        "risk_premium":  [
            "entity00117267_RiskPremiumsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForNonParFixedInterestProductsLineItemsOfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForNonParFixedInterestProductsTableOfItems",
            "entity00117267_RiskPremiumsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForIndirectParVariableInterestProductsLineItemsOfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForIndirectParVariableInterestProductsTableOfItems",
            "entity00117267_RiskPremiumsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForDirectParParticipatingProductsLineItemsOfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForDirectParParticipatingProductsTableOfItems",
        ],
        "expected_claim":[
            "entity00117267_EstimateOfUndiscountedExpectedClaimsThatAriseFromContractsWithinScopeOfIfrs17OfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForNonParFixedInterestProductsLineItemsOfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForNonParFixedInterestProductsTableOfItems",
            "entity00117267_EstimateOfUndiscountedExpectedClaimsThatAriseFromContractsWithinScopeOfIfrs17OfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForIndirectParVariableInterestProductsLineItemsOfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForIndirectParVariableInterestProductsTableOfItems",
            "entity00117267_EstimateOfUndiscountedExpectedClaimsThatAriseFromContractsWithinScopeOfIfrs17OfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForDirectParParticipatingProductsLineItemsOfDisclosureOfExpectedClaimsRelativeToRiskPremiumsForDirectParParticipatingProductsTableOfItems",
        ],
        "planned_maint": [
            "entity00117267_ScheduledMaintenanceCostsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForNonParFixedInterestProductsLineItemsOfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForNonParFixedInterestProductsTableOfItems",
            "entity00117267_ScheduledMaintenanceCostsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForIndirectParVariableInterestProductsLineItemsOfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForIndirectParVariableInterestProductsTableOfItems",
            "entity00117267_ScheduledMaintenanceCostsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForDirectParParticipatingProductsLineItemsOfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForDirectParParticipatingProductsTableOfItems",
        ],
        "expected_maint":[
            "entity00117267_ExpectedMaintenanceCostsEtcArisingFromContractsIncludedInTheScopeOfApplicationOfIfrs17OfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForNonParFixedInterestProductsLineItemsOfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForNonParFixedInterestProductsTableOfItems",
            "entity00117267_ExpectedMaintenanceCostsEtcArisingFromContractsIncludedInTheScopeOfApplicationOfIfrs17OfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForIndirectParVariableInterestProductsLineItemsOfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForIndirectParVariableInterestProductsTableOfItems",
            "entity00117267_ExpectedMaintenanceCostsEtcArisingFromContractsIncludedInTheScopeOfApplicationOfIfrs17OfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForDirectParParticipatingProductsLineItemsOfDisclosureOfExpectedMaintenanceExpensesRelativeToScheduledMaintenanceExpensesForDirectParParticipatingProductsTableOfItems",
        ],
    }),
    "00139214": ("삼성화재", {
        "risk_premium":  ["entity00139214_RiskPremiumsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedInsuranceBenefitsComparedToRiskInsurancePremiumsForLongTermDamageInsuranceLineItemsOfDisclosureOfExpectedInsuranceBenefitsComparedToRiskInsurancePremiumsForLongTermDamageInsuranceTableOfItems"],
        "expected_claim":["entity00139214_ExpectedInsuranceClaimsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedInsuranceBenefitsComparedToRiskInsurancePremiumsForLongTermDamageInsuranceLineItemsOfDisclosureOfExpectedInsuranceBenefitsComparedToRiskInsurancePremiumsForLongTermDamageInsuranceTableOfItems"],
        "planned_maint": ["entity00139214_ScheduledMaintenanceCostsArisingFromContractsWithinTheScopeOfIfrs17OfDisclosureOfExpectedMaintenanceCostsComparedToExpectedMaintenanceCostsForLongTermDamageInsuranceLineItemsOfDisclosureOfExpectedMaintenanceCostsComparedToExpectedMaintenanceCostsForLongTermDamageInsuranceTableOfItems"],
        "expected_maint":["entity00139214_ExpectedMaintenanceCostsEtcArisingFromContractsIncludedInTheScopeOfApplicationOfIfrs17OfDisclosureOfExpectedMaintenanceCostsComparedToExpectedMaintenanceCostsForLongTermDamageInsuranceLineItemsOfDisclosureOfExpectedMaintenanceCostsComparedToExpectedMaintenanceCostsForLongTermDamageInsuranceTableOfItems"],
    }),
    "00164973": ("현대해상", {
        "risk_premium":  ["entity00164973_UndiscountedRiskPremiumsOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioTableOfItems"],
        "expected_claim":["entity00164973_UndiscountedExpectedPremiumsOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioTableOfItems"],
        "planned_maint": ["entity00164973_UndiscountedAppointedMaintenancePremiumOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioTableOfItems"],
        "expected_maint":["entity00164973_UndiscountedExpectedMaintenanceExpensesAndOthersOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioOfExpectedInsuranceClaimComparedToRiskInsurancePremiumAndMaintenanceFeeComparedToAppointedMaintenancePremiumFixedInterestPortfolioTableOfItems"],
    }),
    "00159102": ("DB손보", {
        "risk_premium":  ["entity00159102_RiskInsurancePremiumOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioLineitemsOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioTableOfItems"],
        "expected_claim":["entity00159102_ExpectedClaimsOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioLineitemsOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioTableOfItems"],
        "planned_maint": ["entity00159102_PlannedMaintenanceExpensesOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioLineitemsOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioTableOfItems"],
        "expected_maint":["entity00159102_ExpectedMaintenanceExpensesOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioLineitemsOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioTableOfItems"],
    }),
    "00135917": ("한화손보", {
        "risk_premium":  ["entity00135917_RiskInsurancePremiumOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioTableOfItems"],
        "expected_claim":["entity00135917_ExpectedInsuranceBenefitsOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioOfDisclosureOfExpectedInsuranceBenefitsAndRiskInsurancePremiumByPortfolioTableOfItems"],
        "planned_maint": ["entity00135917_PlannedMaintenanceExpensesOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioTableOfItems"],
        "expected_maint":["entity00135917_ExpectedMaintenanceExpensesOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioOfDisclosureOfExpectedAndPlannedMaintenanceExpensesByPortfolioTableOfItems"],
    }),
}

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def sum_elem(cik: str, elems: list[str]) -> float | None:
    if not elems:
        return None
    total = 0.0; found = False
    for eid in elems:
        q = """
        WITH v AS (SELECT * FROM val_norm WHERE CIK=? AND ELEMENT_ID=? AND amount_krw IS NOT NULL),
        sep AS (SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers WHERE CIK=? AND MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'),
        periods AS (SELECT CONTEXT_ID, ANY_VALUE(PERIOD_START_DATE) AS p FROM cntxt_insurers WHERE CIK=? GROUP BY 1),
        ax AS (SELECT CONTEXT_ID, STRING_AGG(MEMBER_ELEMENT_ID, '||' ORDER BY MEMBER_ELEMENT_ID) AS axes FROM cntxt_insurers WHERE CIK=? GROUP BY 1)
        SELECT SUM(amt) FROM (
          SELECT ax.axes, ANY_VALUE(v.amount_krw) AS amt
          FROM v JOIN sep USING (CONTEXT_ID) JOIN periods p USING (CONTEXT_ID) JOIN ax USING (CONTEXT_ID)
          WHERE p.p='2025-01-01' OR p.p IS NULL
          GROUP BY ax.axes
        )
        """
        r = con.execute(q, [cik, eid, cik, cik, cik]).fetchone()
        if r and r[0]:
            total += r[0]; found = True
    return total if found else None


print(f"{'회사':<10s}  {'위험보험료':>11s}  {'예상보험금':>11s}  {'예상/위험%':>10s}  {'예정유지비':>11s}  {'예상유지비':>11s}  {'예상/예정%':>10s}")
print("─" * 105)
results = {}
for cik, (name, elems) in PEER_ELEMS.items():
    rp = sum_elem(cik, elems["risk_premium"])
    ep = sum_elem(cik, elems["expected_claim"])
    pm = sum_elem(cik, elems["planned_maint"])
    em = sum_elem(cik, elems["expected_maint"])
    pr = (ep / rp * 100) if rp and ep else None
    mr = (em / pm * 100) if pm and em else None
    results[cik] = {
        "name": name, "risk_premium": rp, "expected_claim": ep,
        "planned_maint": pm, "expected_maint": em,
        "claim_ratio_pct": pr, "maint_ratio_pct": mr,
    }
    def f(v): return f"{v/1e8:>9,.0f}억" if v else "         —"
    pr_s = f"{pr:>8.1f}%" if pr else "        —"
    mr_s = f"{mr:>8.1f}%" if mr else "        —"
    print(f"{name:<8s}  {f(rp)}  {f(ep)}  {pr_s}  {f(pm)}  {f(em)}  {mr_s}")

Path("report/pricing_margins.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/pricing_margins.json")
