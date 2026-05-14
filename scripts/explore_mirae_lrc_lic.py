"""미래에셋 DI817100 — LRC/LIC × 상품군(entity axis) 멤버 탐색."""
from __future__ import annotations
import duckdb
import pandas as pd

CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

print("\n=== 1. DI817100 role 에 등장하는 ELEMENT 분포 ===")
sql = """
SELECT DISTINCT v.ELEMENT_ID, MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
       COUNT(*) AS n_facts
FROM pre_insurers p
JOIN val_insurers v ON v.CIK=p.CIK AND v.ELEMENT_ID=p.ELEMENT_ID
LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
WHERE p.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
GROUP BY v.ELEMENT_ID
ORDER BY n_facts DESC
"""
df = con.execute(sql, [CIK, ROLE]).df()
print(df.to_string(index=False, max_colwidth=80))

print("\n=== 2. 등장하는 AXIS / MEMBER 조합 ===")
sql = """
WITH ctx_in_role AS (
  SELECT DISTINCT v.CONTEXT_ID
  FROM val_insurers v JOIN pre_insurers p USING (CIK, ELEMENT_ID)
  WHERE p.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
)
SELECT cx.AXIS_ELEMENT_ID, cx.MEMBER_ELEMENT_ID,
       MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS member_ko,
       COUNT(DISTINCT cx.CONTEXT_ID) AS n_ctx
FROM cntxt_insurers cx
LEFT JOIN lab_insurers l ON l.CIK=cx.CIK AND l.ELMT_ID=cx.MEMBER_ELEMENT_ID AND l.LANG='ko'
WHERE cx.CIK=? AND cx.CONTEXT_ID IN (SELECT CONTEXT_ID FROM ctx_in_role)
GROUP BY cx.AXIS_ELEMENT_ID, cx.MEMBER_ELEMENT_ID
ORDER BY cx.AXIS_ELEMENT_ID, n_ctx DESC
"""
ax = con.execute(sql, [CIK, ROLE, CIK]).df()
for axis, group in ax.groupby("AXIS_ELEMENT_ID"):
    print(f"\n  --- AXIS: {axis} ---")
    for _, r in group.iterrows():
        print(f"    {r['MEMBER_ELEMENT_ID']:<90s}  {r['member_ko'] or '':<40s}  ({r['n_ctx']})")
