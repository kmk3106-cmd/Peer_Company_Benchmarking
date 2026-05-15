"""각 회사 DI817105 모든 element 의 모든 라벨 (terse, label, verbose) 덤프.

13행 라벨과 의미 매칭 가능한 element 찾기 위한 자료.
"""
from __future__ import annotations
import duckdb
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

PEERS = [
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손해보험"),
    ("00135917", "한화손해보험"),
]
ROLE = "dart_2024-06-30_role-DI817105"

SQL = """
WITH role_elems AS (
  SELECT DISTINCT ELEMENT_ID FROM pre_insurers
  WHERE CIK=? AND REPORT_DATE='20251231' AND ROLE_ID=?
)
SELECT re.ELEMENT_ID, l.LABEL, l.LABEL_ROLE_URI
FROM role_elems re
LEFT JOIN lab_insurers l ON l.ELMT_ID=re.ELEMENT_ID AND l.CIK=? AND l.REPORT_DATE='20251231' AND l.LANG='ko'
ORDER BY re.ELEMENT_ID, l.LABEL_ROLE_URI
"""

for cik, name in PEERS:
    print(f"\n=== {name} ({cik}) — DI817105 elements & labels ===")
    rows = con.execute(SQL, [cik, ROLE, cik]).fetchall()
    cur = None
    for eid, lbl, role in rows:
        if eid != cur:
            cur = eid
            short = eid.replace("ifrs-full_", "").replace("entity"+cik+"_", "ent_")
            print(f"\n  {short[:80]}")
        role_short = (role or "").split("/")[-1][:30] if role else ""
        print(f"      [{role_short:<30s}] {lbl}")
