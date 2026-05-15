"""미래에셋 +5,926억 (발생한 보험금 등) — XBRL 에서 어디?"""
from __future__ import annotations
import duckdb
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
CIK = "00112332"
# 사용자값 +5,926억 = +592,626,787,607원
TARGET = 592_626_787_607

SQL = """
WITH ko AS (
  SELECT ELMT_ID, MIN(LABEL) AS LABEL FROM lab_insurers
  WHERE CIK=? AND REPORT_DATE='20251231' AND LANG='ko' GROUP BY ELMT_ID
)
SELECT v.ELEMENT_ID, v.CONTEXT_ID, v.amount_krw,
       (SELECT STRING_AGG(MEMBER_ELEMENT_ID, ' | ') FROM cntxt_insurers c
        WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID) AS members,
       COALESCE(ko.LABEL,'') AS LABEL
FROM val_insurers v LEFT JOIN ko ON ko.ELMT_ID=v.ELEMENT_ID
WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.amount_krw IS NOT NULL
  AND ABS(v.amount_krw - ?) < 1e6
ORDER BY v.ELEMENT_ID
"""
rows = con.execute(SQL, [CIK, CIK, TARGET]).fetchall()
print(f"미래에셋 사용자값 +592,626,787,607원 = +5,926.27억 매칭 fact:")
for eid, ctx, amt, mem, lbl in rows:
    print(f"  {amt/1e8:>+10,.0f}억  {lbl[:40]:<40s}  | {eid[:60]} | ctx={ctx}")
    print(f"            members: {mem}")
print()

# 음수도 (혹시 사용자가 부호 반대로 봤을 수 있음)
print(f"\n부호반대 -5,926.27억 매칭:")
rows = con.execute(SQL, [CIK, CIK, -TARGET]).fetchall()
for eid, ctx, amt, mem, lbl in rows:
    print(f"  {amt/1e8:>+10,.0f}억  {lbl[:40]:<40s}  | {eid[:60]} | ctx={ctx}")
    print(f"            members: {mem}")
