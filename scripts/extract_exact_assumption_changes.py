"""엄격 추출 — 미래에셋 '계리적가정에 의한 보험부채 변동내역' 정확 element만.

기존에 잘못 매핑한 'ChangeEffectOfDiscountRate...' element는 다른 것.
정답: entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptions...
"""
from __future__ import annotations
import duckdb

CIK = "00112332"
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# Step 1: 4개 정확 element가 어느 role 에 속하는지
print("="*100)
print("STEP 1: '계리적가정' element 들의 role 소속")
print("="*100)

elements = con.execute("""
  SELECT l.ELMT_ID, l.LABEL, p.ROLE_ID, p."ORDER"
  FROM lab_insurers l
  LEFT JOIN pre_insurers p ON p.CIK=l.CIK AND p.ELEMENT_ID=l.ELMT_ID
  WHERE l.CIK=? AND l.LANG='ko'
    AND l.LABEL LIKE '%계리적가정%'
  ORDER BY p.ROLE_ID, p."ORDER"
""", [CIK]).fetchall()

for eid, label, role, order in elements:
    role_short = role.split("role-")[-1] if role else "(no role)"
    print(f"  [{role_short:<15s} order={order}] {label[:50]:<50s} ← {eid[:80]}")

# Step 2: 그 role 안의 모든 element + 실제 값
roles_found = set(r[2] for r in elements if r[2])
for role in roles_found:
    print(f"\n\n{'='*100}")
    print(f"STEP 2: ROLE = {role} 의 모든 element + 값")
    print(f"{'='*100}")

    # 이 role 의 element 풀
    role_elems = con.execute("""
      SELECT p.ELEMENT_ID, p."ORDER",
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko
      FROM pre_insurers p
      LEFT JOIN lab_insurers l ON l.CIK=p.CIK AND l.ELMT_ID=p.ELEMENT_ID
      WHERE p.CIK=? AND p.ROLE_ID=?
      GROUP BY p.ELEMENT_ID, p."ORDER"
      ORDER BY p."ORDER"
    """, [CIK, role]).fetchall()
    print(f"\n  role 내 element {len(role_elems)} 개")
    for eid, order, ko in role_elems[:30]:
        eshort = eid.replace("ifrs-full_","").replace("dart_","d:").replace(f"entity{CIK}_","#")[:60]
        print(f"    [{order or '?':>4}] {eshort:<62s} ← {ko or ''}")

    # 이 role 의 실제 값 (fact)
    facts = con.execute(f"""
      SELECT v.ELEMENT_ID, MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
             v.amount_krw/1e8 AS amt_억, COUNT(*) AS n
      FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      GROUP BY v.ELEMENT_ID, v.amount_krw
      ORDER BY ABS(v.amount_krw) DESC LIMIT 40
    """, [CIK, role]).fetchall()
    print(f"\n  실제 fact 값 (상위 40, ABS 큰 순):")
    for eid, ko, amt, n in facts:
        eshort = eid.replace("ifrs-full_","").replace("dart_","d:").replace(f"entity{CIK}_","#")[:55]
        print(f"    {amt:>+12,.0f}억 [n={n}] {eshort:<57s} ← {ko or ''}")
