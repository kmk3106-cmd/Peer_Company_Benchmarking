"""보험수익·투자요소 element가 어떤 axis 조합으로 보고되었나 확인."""
from __future__ import annotations
import duckdb

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

ELEMS = [
    "ifrs-full_InsuranceRevenue",
    "ifrs-full_IncreaseDecreaseThroughInvestmentComponentsExcludedFromInsuranceRevenueAndInsuranceServiceExpensesInsuranceContractsLiabilityAsset",
]

for elem in ELEMS:
    print("="*70)
    print("ELEMENT:", elem[:90])
    sql = """
    WITH ctx AS (
      SELECT cx.CONTEXT_ID,
        STRING_AGG(cx.AXIS_ELEMENT_ID || '=' || cx.MEMBER_ELEMENT_ID, ' | '
                   ORDER BY cx.AXIS_ELEMENT_ID) AS dims,
        COUNT(*) AS n_axes,
        ANY_VALUE(cx.PERIOD_START_DATE) AS pstart,
        ANY_VALUE(cx.PERIOD_END_DATE) AS pend
      FROM cntxt_insurers cx WHERE cx.CIK='00112332'
      GROUP BY cx.CONTEXT_ID
    )
    SELECT v.amount_krw/1e8 AS amt, c.n_axes, c.dims
    FROM val_insurers v JOIN ctx c USING(CONTEXT_ID)
    WHERE v.CIK='00112332' AND v.ELEMENT_ID=? AND v.amount_krw IS NOT NULL
      AND c.pstart='2025-01-01' AND c.pend='2025-12-31'
    ORDER BY c.n_axes, c.dims
    """
    for r in con.execute(sql, [elem]).fetchall():
        dims = r[2].replace("ifrs-full_","").replace("dart_","d:").replace("entity00112332_","#")[:200]
        print(f"  {r[0]:+12,.0f}억  n={r[1]}  {dims}")
