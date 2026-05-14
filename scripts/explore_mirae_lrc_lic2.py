"""LRC/LIC × 상품군 dimension 조합 탐색."""
from __future__ import annotations
import duckdb
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 60)
pd.set_option("display.max_rows", 100)

CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"
LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
SEP = "ifrs-full_SeparateMember"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

print("=== LRC/LIC 축이 붙은 context 들의 모든 axis 조합 ===")
sql = """
WITH ctx_in_role AS (
  SELECT DISTINCT v.CONTEXT_ID
  FROM val_insurers v JOIN pre_insurers p USING (CIK, ELEMENT_ID)
  WHERE p.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
),
ctx_with_lrclic AS (
  SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers
  WHERE CIK=? AND AXIS_ELEMENT_ID=? AND CONTEXT_ID IN (SELECT CONTEXT_ID FROM ctx_in_role)
)
SELECT cx.CONTEXT_ID,
       STRING_AGG(cx.AXIS_ELEMENT_ID || '=' || cx.MEMBER_ELEMENT_ID, ' | ' ORDER BY cx.AXIS_ELEMENT_ID) AS dims,
       ANY_VALUE(cx.PERIOD_START_DATE) AS pstart,
       ANY_VALUE(cx.PERIOD_END_DATE) AS pend,
       ANY_VALUE(cx.PERIOD_INSTANT) AS pinst
FROM cntxt_insurers cx
WHERE cx.CIK=? AND cx.CONTEXT_ID IN (SELECT CONTEXT_ID FROM ctx_with_lrclic)
GROUP BY cx.CONTEXT_ID
"""
df = con.execute(sql, [CIK, ROLE, CIK, LRC_LIC_AXIS, CIK]).df()
df["dims_short"] = df["dims"].str.replace("ifrs-full_", "").str.replace("dart_", "d:").str.replace("entity00112332_", "#")
print(f"\ntotal LRC/LIC contexts: {len(df)}")
print(df[["CONTEXT_ID", "pstart", "pend", "pinst", "dims_short"]].head(40).to_string(index=False))

print("\n=== LRC/LIC 축이 붙은 fact (값 있는) — element × member ===")
sql = """
WITH ctx_in_role AS (
  SELECT DISTINCT v.CONTEXT_ID
  FROM val_insurers v JOIN pre_insurers p USING (CIK, ELEMENT_ID)
  WHERE p.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
),
ctx_lrclic AS (
  SELECT cx.CONTEXT_ID, cx.MEMBER_ELEMENT_ID AS lrclic_mem
  FROM cntxt_insurers cx
  WHERE cx.CIK=? AND cx.AXIS_ELEMENT_ID=? AND cx.CONTEXT_ID IN (SELECT CONTEXT_ID FROM ctx_in_role)
)
SELECT v.ELEMENT_ID, c.lrclic_mem,
       COUNT(*) AS n, SUM(v.amount_krw)/1e12 AS sum_조,
       ANY_VALUE(v.amount_krw) AS sample
FROM val_insurers v
JOIN ctx_lrclic c ON c.CONTEXT_ID=v.CONTEXT_ID
WHERE v.CIK=? AND v.amount_krw IS NOT NULL
GROUP BY v.ELEMENT_ID, c.lrclic_mem
ORDER BY v.ELEMENT_ID, c.lrclic_mem
"""
df2 = con.execute(sql, [CIK, ROLE, CIK, LRC_LIC_AXIS, CIK]).df()
df2["elem_short"] = df2["ELEMENT_ID"].str.replace("ifrs-full_", "").str.replace("dart_", "d:").str[:60]
df2["mem_short"] = df2["lrclic_mem"].str.replace("ifrs-full_", "").str.replace("Member", "")
print(df2[["elem_short", "mem_short", "n", "sum_조"]].to_string(index=False))
