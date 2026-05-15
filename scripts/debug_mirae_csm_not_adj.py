"""미래에셋 보험계약마진 미조정 추정변동 axis breakdown."""
import duckdb
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
sql = """
SELECT cx.AXIS_ELEMENT_ID, cx.MEMBER_ELEMENT_ID, SUM(v.amount_krw)/1e8 AS amt, COUNT(*) AS n
FROM val_insurers v JOIN cntxt_insurers cx USING (CIK, REPORT_DATE, CONTEXT_ID)
WHERE v.CIK='00112332' AND v.amount_krw IS NOT NULL
  AND v.ELEMENT_ID LIKE '%ChangesInEstimatesThatDoNotAdjustContractualServiceMargin%'
  AND EXISTS (SELECT 1 FROM cntxt_insurers p WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
    AND p.PERIOD_START_DATE='2025-01-01' AND p.PERIOD_END_DATE='2025-12-31')
GROUP BY cx.AXIS_ELEMENT_ID, cx.MEMBER_ELEMENT_ID
ORDER BY cx.AXIS_ELEMENT_ID, ABS(SUM(v.amount_krw)) DESC
"""
print("axis × member breakdown")
for r in con.execute(sql).fetchall():
    axis = (r[0] or "").replace("ifrs-full_","")[:55]
    mem = (r[1] or "").replace("ifrs-full_","").replace("entity00112332_","#").replace("dart_","d:")[:55]
    print(f"  {axis:<57s} {mem:<57s} {r[2]:>+9,.0f}억 (n={r[3]})")
