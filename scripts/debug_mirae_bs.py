"""미래에셋 IssuedThatAreLiabilities × 별도 × 2025 context dump."""
import duckdb
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
CIK = "00112332"
sql = """
WITH ax AS (
  SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
  FROM cntxt_insurers WHERE CIK=? GROUP BY CIK, REPORT_DATE, CONTEXT_ID
),
ctx_dim AS (
  SELECT cx.CONTEXT_ID,
    STRING_AGG(cx.AXIS_ELEMENT_ID || '=' || cx.MEMBER_ELEMENT_ID, ' | ') AS dims
  FROM cntxt_insurers cx WHERE cx.CIK=? GROUP BY cx.CONTEXT_ID
)
SELECT v.amount_krw/1e12 AS amt_조, ax.n_axes, ctx_dim.dims
FROM val_insurers v
JOIN ax USING (CIK, REPORT_DATE, CONTEXT_ID)
JOIN ctx_dim USING (CONTEXT_ID)
WHERE v.CIK=?
  AND v.ELEMENT_ID='ifrs-full_InsuranceContractsIssuedThatAreLiabilities'
  AND v.amount_krw IS NOT NULL
  AND EXISTS (SELECT 1 FROM cntxt_insurers c
    WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
      AND c.AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
      AND c.MEMBER_ELEMENT_ID='ifrs-full_SeparateMember')
  AND EXISTS (SELECT 1 FROM cntxt_insurers p
    WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
      AND p.PERIOD_INSTANT='2025-12-31')
ORDER BY ax.n_axes, v.amount_krw DESC
"""
for r in con.execute(sql, [CIK, CIK, CIK]).fetchall():
    dims = r[2].replace("ifrs-full_", "").replace("Member","").replace("entity00112332_","#")[:170]
    print(f"  {r[0]:>8.2f}조  n={r[1]}  {dims}")
