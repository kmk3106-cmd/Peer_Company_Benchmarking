"""계리적가정 보험부채 변동내역 표 — 정확 children elements 추출.

부모 element: entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptions...
이 abstract/table의 자식 line items 만 사용 (PARENT_ELEMENT_ID).
"""
from __future__ import annotations
import duckdb

CIK = "00112332"
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 1) 부모 elements 식별
PARENTS = [
    "entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsAbstract",
    "entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTable",
    "entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsOfChanges",  # 부분 매치
]

# 정확 매치되는 부모 element 모두 찾기
all_parents = con.execute("""
  SELECT DISTINCT ELMT_ID FROM lab_insurers
  WHERE CIK=? AND LANG='ko' AND LABEL LIKE '%계리적가정%'
""", [CIK]).fetchall()
parent_eids = [r[0] for r in all_parents]
print("계리적가정 element 목록:")
for p in parent_eids: print(f"  {p}")

# 2) PARENT_ELEMENT_ID 가 이 element 중 하나인 자식 elements
print("\n\n자식 element들 (PARENT_ELEMENT_ID 매칭):")
print("="*100)
parent_in = ",".join(f"'{p}'" for p in parent_eids)
children = con.execute(f"""
  SELECT DISTINCT p.ELEMENT_ID, p.PARENT_ELEMENT_ID, p."ORDER",
         MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko
  FROM pre_insurers p
  LEFT JOIN lab_insurers l ON l.CIK=p.CIK AND l.ELMT_ID=p.ELEMENT_ID
  WHERE p.CIK=? AND p.PARENT_ELEMENT_ID IN ({parent_in})
  GROUP BY p.ELEMENT_ID, p.PARENT_ELEMENT_ID, p."ORDER"
  ORDER BY p."ORDER"
""", [CIK]).fetchall()

for eid, parent, order, ko in children:
    eshort = eid.replace(f"entity{CIK}_", "#").replace("ifrs-full_","").replace("dart_","d:")[:80]
    parent_short = parent.replace(f"entity{CIK}_", "#")[:50]
    print(f"  [{order or '?':>4}] {eshort:<82s} ← {ko or ''}")
    print(f"          parent={parent_short}")

# 3) 자손까지 (재귀 — 1단계)
print("\n\n자손 element (자식의 자식까지):")
child_eids = [r[0] for r in children]
if child_eids:
    child_in = ",".join(f"'{e}'" for e in child_eids)
    grandchildren = con.execute(f"""
      SELECT DISTINCT p.ELEMENT_ID, p.PARENT_ELEMENT_ID, p."ORDER",
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko
      FROM pre_insurers p
      LEFT JOIN lab_insurers l ON l.CIK=p.CIK AND l.ELMT_ID=p.ELEMENT_ID
      WHERE p.CIK=? AND p.PARENT_ELEMENT_ID IN ({child_in})
      GROUP BY p.ELEMENT_ID, p.PARENT_ELEMENT_ID, p."ORDER"
      ORDER BY p."ORDER"
    """, [CIK]).fetchall()
    for eid, parent, order, ko in grandchildren:
        eshort = eid.replace(f"entity{CIK}_", "#").replace("ifrs-full_","").replace("dart_","d:")[:75]
        print(f"  [{order or '?':>4}] {eshort:<77s} ← {ko or ''}")
