"""1) 예상보험금 대비 실제보험금 예실차 — element 탐색.
   - 예상보험금 (Expected Insurance Amount/Payout): DI817305
   - 실제보험금: 발생사고비용 (IncurredClaims), 지급보험금 (IncurredClaimsPaid)
   - 경험조정 (Experience Adjustment): IFRS17 §103

2) CSM 변동 무브먼트 — DI817100 CSM 분해 element.
"""
from __future__ import annotations
import duckdb

PEERS = [
    ("00112332", "미래에셋"),
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손보"),
    ("00135917", "한화손보"),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# ─── 1) 예상보험금 vs 실제보험금 element 식별 ───
print("="*100)
print("STEP 1: 예상보험금 vs 실제보험금 — element 탐색")
print("="*100)

# 회사별 두 element 식별
for cik, name in PEERS:
    print(f"\n  ── {name} ──")
    # 예상보험금
    expected = con.execute("""
      SELECT v.ELEMENT_ID, MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko, COUNT(*) AS n
      FROM val_insurers v
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND v.amount_krw IS NOT NULL
        AND (l.LABEL LIKE '%예상보험금%' OR l.LABEL LIKE '%ExpectedInsurance%' OR v.ELEMENT_ID LIKE '%ExpectedInsuranceAmount%' OR v.ELEMENT_ID LIKE '%ExpectedInsurancePayout%')
      GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 2
    """, [cik]).fetchall()
    print(f"    예상보험금:")
    for eid, ko, n in expected:
        eshort = eid[:60]
        print(f"      [{n:>4d}] {eshort:<60s} ← {ko}")

    # 실제 발생사고비용
    actual = con.execute("""
      SELECT v.ELEMENT_ID, MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko, COUNT(*) AS n
      FROM val_insurers v
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND v.amount_krw IS NOT NULL
        AND v.ELEMENT_ID LIKE '%IncurredClaimsAndOtherIncurred%'
      GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 2
    """, [cik]).fetchall()
    print(f"    실제 발생사고비용:")
    for eid, ko, n in actual:
        eshort = eid[:60]
        print(f"      [{n:>4d}] {eshort:<60s} ← {ko}")

# ─── 2) CSM 변동 무브먼트 element 탐색 ───
print("\n\n" + "="*100)
print("STEP 2: CSM 변동 무브먼트 — DI817100 × CSM axis 분해")
print("="*100)

# CSM × 변동 element (이미 알고 있는 라인) 확인
COMPONENTS_AXIS = "ifrs-full_InsuranceContractsByComponentsAxis"
CSM_MEMBERS = (
    "ifrs-full_ContractualServiceMarginMember",
    "ifrs-full_ContractualServiceMarginNotRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachOrFairValueApproachHasBeenAppliedMember",
    "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachHasBeenAppliedMember",
    "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichFairValueApproachHasBeenAppliedMember",
)

# DI817100 에서 CSM axis 와 함께 보고된 element 풀
for cik, name in PEERS:
    csm_members_str = ",".join(f"'{m}'" for m in CSM_MEMBERS)
    rows = con.execute(f"""
      SELECT DISTINCT v.ELEMENT_ID,
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
             COUNT(*) AS n
      FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      JOIN cntxt_insurers cx ON cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817100' AND v.amount_krw IS NOT NULL
        AND cx.AXIS_ELEMENT_ID='{COMPONENTS_AXIS}'
        AND cx.MEMBER_ELEMENT_ID IN ({csm_members_str})
      GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 8
    """, [cik]).fetchall()
    print(f"\n  ── {name} ──")
    for eid, ko, n in rows:
        eshort = eid.replace("ifrs-full_", "").replace("dart_", "d:").replace(f"entity{cik}_", "#")[:60]
        print(f"    [{n:>4d}] {eshort:<62s} ← {ko}")
