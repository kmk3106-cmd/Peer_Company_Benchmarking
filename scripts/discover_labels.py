"""다른 회사들이 누락된 5개 라인을 어떤 라벨로 보고하는지 탐색.

탐색 대상 라인:
- 위험조정 변동
- 과거서비스 변동
- 발생사고요소 조정
- 발생사고비용
- 금융손익_OCI
- 기타증감

각 회사 (미래에셋 외 7개사) × DI817100 × 위 키워드 패턴 element 후보 dump.
"""
from __future__ import annotations
import duckdb

CIK_NAMES = {
    "00126256": "삼성생명",
    "00113058": "한화생명",
    "00117267": "동양생명",
    "00139214": "삼성화재",
    "00164973": "현대해상",
    "00159102": "DB손해보험",
    "00135917": "한화손해보험",
}
ROLE = "dart_2024-06-30_role-DI817100"

# (탐색 key, element_id 패턴 LIKE 들, label 키워드 후보들)
SEARCH = [
    ("위험조정변동", [
        "%ChangeInRiskAdjustment%",
        "%RiskAdjustmentForNonfinancialRisk%",
    ], ["위험조정", "위험 조정"]),
    ("과거서비스변동", [
        "%RelateToPastService%",
        "%PastService%",
    ], ["과거서비스", "과거 서비스"]),
    ("발생사고비용", [
        "%IncurredClaimsAndOtherIncurred%",
    ], ["발생한 보험금", "발생사고", "발생한 사고"]),
    ("발생사고요소조정", [
        "%OtherAdjustmentsOfLiabilitiesForIncurredClaims%",
        "%AdjustmentsOfLiabilitiesForIncurredClaims%",
    ], ["발생사고요소", "발생사고부채"]),
    ("금융손익_OCI", [
        "%InsuranceFinanceIncomeExpenses%Recognise%InOtherCompr%",
        "%InsuranceFinanceIncomeExpenses%Recognise%InOtherComper%",
        "%OtherComprehensiveIncome%Insurance%",
    ], ["기타포괄손익", "OCI", "OCI 인식"]),
    ("기타증감", [
        "%IncreaseDecreaseThroughOtherChanges%InsuranceContracts%",
        "%OtherChangesLiabilitiesUnderInsuranceContracts%",
    ], ["기타증감", "기타 증감", "기타변동"]),
]


def find_candidates(con, cik, patterns, labels):
    """element_id LIKE OR label LIKE 매치된 element 후보 dump.

    role 매핑: DI817100 에서 사용된 element 중 매칭."""
    pat_clause = " OR ".join(f"v.ELEMENT_ID LIKE ?" for _ in patterns)
    lab_clause = " OR ".join(f"l.LABEL LIKE ?" for _ in labels)
    sql = f"""
    SELECT DISTINCT v.ELEMENT_ID,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
           COUNT(*) AS n
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      AND (({pat_clause}) OR ({lab_clause}))
    GROUP BY v.ELEMENT_ID
    ORDER BY n DESC
    """
    params = [cik, ROLE] + list(patterns) + [f"%{kw}%" for kw in labels]
    return con.execute(sql, params).fetchall()


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

    for key, patterns, labels in SEARCH:
        print(f"\n{'='*80}\n  탐색: {key}")
        print(f"  patterns: {patterns}")
        print(f"  label keywords: {labels}\n{'='*80}")
        for cik, name in CIK_NAMES.items():
            rows = find_candidates(con, cik, patterns, labels)
            if not rows:
                print(f"  {name:<14s}  (no match)")
                continue
            print(f"  {name:<14s}  {len(rows)} 후보:")
            for eid, ko, n in rows[:3]:
                eshort = eid.replace("ifrs-full_","").replace("dart_","d:").replace("entity00112332_","#")[:60]
                print(f"    - [{n:>4d}] {eshort:<62s} ← {ko}")


if __name__ == "__main__":
    main()
