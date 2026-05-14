"""보험수익 — TypesOfContractsAxis 별 값 dump (별도, 발행)."""
from __future__ import annotations
import duckdb

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

for elem, name in [
    ("ifrs-full_InsuranceRevenue", "보험수익"),
    ("ifrs-full_IncreaseDecreaseThroughInvestmentComponentsExcludedFromInsuranceRevenueAndInsuranceServiceExpensesInsuranceContractsLiabilityAsset", "투자요소"),
]:
    print("="*70)
    print(name, ":", elem[:80])
    sql = """
    WITH ctx AS (
      SELECT cx.CONTEXT_ID,
        MAX(CASE WHEN cx.AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis' THEN cx.MEMBER_ELEMENT_ID END) AS cons,
        MAX(CASE WHEN cx.AXIS_ELEMENT_ID='ifrs-full_DisaggregationOfInsuranceContractsAxis' THEN cx.MEMBER_ELEMENT_ID END) AS disagg,
        MAX(CASE WHEN cx.AXIS_ELEMENT_ID='ifrs-full_TypesOfContractsAxis' THEN cx.MEMBER_ELEMENT_ID END) AS types,
        MAX(CASE WHEN cx.AXIS_ELEMENT_ID='ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis' THEN cx.MEMBER_ELEMENT_ID END) AS lrclic,
        MAX(CASE WHEN cx.AXIS_ELEMENT_ID='ifrs-full_InsuranceContractsAxis' THEN cx.MEMBER_ELEMENT_ID END) AS ic_axis,
        COUNT(*) AS n
      FROM cntxt_insurers cx WHERE cx.CIK='00112332'
      GROUP BY cx.CONTEXT_ID
    )
    SELECT v.amount_krw/1e8 AS amt, c.cons, c.disagg, c.types, c.lrclic, c.ic_axis, c.n
    FROM val_insurers v JOIN ctx c USING(CONTEXT_ID)
    WHERE v.CIK='00112332' AND v.ELEMENT_ID=? AND v.amount_krw IS NOT NULL
      AND c.cons='ifrs-full_SeparateMember'
      AND c.disagg='ifrs-full_InsuranceContractsIssuedMember'
    ORDER BY c.types NULLS FIRST, c.lrclic NULLS FIRST
    """
    for r in con.execute(sql, [elem]).fetchall():
        types_s = (r[3] or "<none>").replace("ifrs-full_", "").replace("dart_", "d:").replace("entity00112332_", "#")[:60]
        lrclic_s = (r[4] or "<none>").replace("ifrs-full_", "").replace("Member", "")[:35]
        ic_s = (r[5] or "<none>")[:30]
        print(f"  {r[0]:+12,.0f}억  types={types_s:<40s} lrclic={lrclic_s:<35s} ic={ic_s} n={r[6]}")
