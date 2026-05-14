"""CSM 변동 무브먼트 v2 — 정확 element 매핑 + axes-tuple dedup.

v1 → v2 변경점:
  1. LIKE 패턴 → **exact element 매핑**으로 교체 (패턴 중복 매칭 차단)
     - v1의 `%ChangesThat%` 와일드카드가 CurrentService/Past/FutureService를 모두 매칭하여
       동일 fact가 여러 라인에 합산되는 오류 발생
  2. CSM-component-axis 필터는 **broad CSM Member**(ContractualServiceMarginMember)만 사용.
     transition 변형 3개는 별도 axes-tuple로 들어가서 dedup으로 자동 제거됨.
  3. **axes-tuple dedup**: STRING_AGG(MEMBER ORDER BY)를 GROUP BY 키로 ANY_VALUE 채택.
     동일 fact가 여러 표(예: 1-66 income table + 신계약효과 별표)에 중복 태깅되는 것을 제거.

자사 검증 (미래에셋 별도 FY2025):
  - 신계약 인식: v1 10,513억 → v2 5,256억 (사용자 도메인 6,000억쯤 정합)
  - CSM 상각:   v1 2,108억(1-63 미래표 오염) → v2 2,058억 (§103 정확 셀)
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import fetch_csm_total_all_variants

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

# 라인 라벨 → 정확 element ID 매핑 (NON-OVERLAPPING)
CSM_MOVEMENT_LINES: list[tuple[str, str]] = [
    ("신계약 인식",          "ifrs-full_IncreaseDecreaseThroughEffectsOfContractsInitiallyRecognisedInPeriodInsuranceContractsLiabilityAsset"),
    ("CSM조정 추정변동",     "ifrs-full_IncreaseDecreaseThroughChangesInEstimatesThatAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
    ("CSM미조정 추정변동",   "ifrs-full_IncreaseDecreaseThroughChangesInEstimatesThatDoNotAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
    ("경험조정",            "ifrs-full_IncreaseDecreaseThroughExperienceAdjustmentsInsuranceContractsLiabilityAsset"),
    ("과거서비스 변동",      "ifrs-full_IncreaseDecreaseThroughChangesThatRelateToPastServiceInsuranceContractsLiabilityAsset"),
    ("보험금융손익",         "ifrs-full_IncreaseDecreaseThroughInsuranceFinanceIncomeOrExpensesInsuranceContractsLiabilityAsset"),
    ("CSM 상각(당기서비스)", "ifrs-full_IncreaseDecreaseThroughChangesThatRelateToCurrentServiceInsuranceContractsLiabilityAsset"),
    ("기타증감",            "ifrs-full_IncreaseDecreaseThroughOtherChangesLiabilitiesUnderInsuranceContractsAndReinsuranceContractsIssued"),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

CSM_BROAD_SQL = """
WITH v AS (
  SELECT * FROM val_norm WHERE CIK = ? AND UNIT_ID='KRW' AND ELEMENT_ID = ?
),
sep AS (SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers
        WHERE CIK = ? AND MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'),
csm AS (SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers
        WHERE CIK = ? AND MEMBER_ELEMENT_ID='ifrs-full_ContractualServiceMarginMember'),
periods AS (SELECT CONTEXT_ID, ANY_VALUE(PERIOD_START_DATE) AS pstart
            FROM cntxt_insurers WHERE CIK = ? GROUP BY 1),
ctx_axes AS (SELECT CONTEXT_ID, STRING_AGG(MEMBER_ELEMENT_ID, '||' ORDER BY MEMBER_ELEMENT_ID) AS axes
             FROM cntxt_insurers WHERE CIK = ? GROUP BY 1),
joined AS (
  SELECT v.CONTEXT_ID, v.amount_krw, ca.axes
  FROM v JOIN sep USING (CONTEXT_ID) JOIN csm USING (CONTEXT_ID)
  JOIN periods p USING (CONTEXT_ID) JOIN ctx_axes ca USING (CONTEXT_ID)
  WHERE p.pstart='2025-01-01'
)
SELECT axes, ANY_VALUE(amount_krw) FROM joined GROUP BY axes
"""

# Fallback: CSM-transition 멤버만 태깅한 회사 (broad 없는 경우)
CSM_TRANSITION_SQL = """
WITH v AS (
  SELECT * FROM val_norm WHERE CIK = ? AND UNIT_ID='KRW' AND ELEMENT_ID = ?
),
sep AS (SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers
        WHERE CIK = ? AND MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'),
csm_any AS (SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers
            WHERE CIK = ?
              AND MEMBER_ELEMENT_ID IN (
                'ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachHasBeenAppliedMember',
                'ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichFairValueApproachHasBeenAppliedMember',
                'ifrs-full_ContractualServiceMarginNotRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachOrFairValueApproachHasBeenAppliedMember'
              )),
periods AS (SELECT CONTEXT_ID, ANY_VALUE(PERIOD_START_DATE) AS pstart
            FROM cntxt_insurers WHERE CIK = ? GROUP BY 1),
ctx_axes AS (SELECT CONTEXT_ID, STRING_AGG(MEMBER_ELEMENT_ID, '||' ORDER BY MEMBER_ELEMENT_ID) AS axes
             FROM cntxt_insurers WHERE CIK = ? GROUP BY 1),
joined AS (
  SELECT v.CONTEXT_ID, v.amount_krw, ca.axes
  FROM v JOIN sep USING (CONTEXT_ID) JOIN csm_any USING (CONTEXT_ID)
  JOIN periods p USING (CONTEXT_ID) JOIN ctx_axes ca USING (CONTEXT_ID)
  WHERE p.pstart='2025-01-01'
)
SELECT axes, ANY_VALUE(amount_krw) FROM joined GROUP BY axes
"""


def fetch_csm_line(cik: str, element_id: str) -> float | None:
    """1차: CSM-broad / 2차: CSM-transition 변형. axes-tuple dedup 후 합산."""
    rows = con.execute(CSM_BROAD_SQL, [cik, element_id, cik, cik, cik, cik]).fetchall()
    if rows:
        return sum(amt for _, amt in rows if amt is not None) or None
    rows = con.execute(CSM_TRANSITION_SQL, [cik, element_id, cik, cik, cik, cik]).fetchall()
    if rows:
        return sum(amt for _, amt in rows if amt is not None) or None
    return None


print("="*145)
print("CSM 변동 무브먼트 v2 — 정확 element 매핑 + axes-tuple dedup (FY2025 별도, 억원)")
print("="*145)

COLS = ["기시 CSM"] + [n for n, _ in CSM_MOVEMENT_LINES] + ["변동 합", "기말 (계산)", "기말 (실측)", "오차"]
print(f"\n  {'회사':<10s}  " + "  ".join(f"{c[:11]:>10s}" for c in COLS))
print("─"*155)

results = {}
for cik, name in PEERS:
    row = {}
    beg = fetch_csm_total_all_variants(con, cik, "20251231", "2024-12-31") or 0
    end = fetch_csm_total_all_variants(con, cik, "20251231", "2025-12-31") or 0
    row["기시 CSM"] = beg
    move_sum = 0.0
    for label, eid in CSM_MOVEMENT_LINES:
        v = fetch_csm_line(cik, eid)
        row[label] = v
        if v is not None:
            move_sum += v
    row["변동 합"] = move_sum
    row["기말 (계산)"] = beg + move_sum
    row["기말 (실측)"] = end
    row["오차"] = (beg + move_sum) - end

    def f(v):
        if v is None: return "         —"
        return f"{v/1e8:>+8,.0f}억"
    print(f"  {name:<8s}  " + "  ".join(f(row[c]) for c in COLS))
    results[cik] = row

Path("report/csm_movement.json").write_text(
    json.dumps({c: {k: v for k, v in r.items()} for c, r in results.items()},
               ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/csm_movement.json (v2)")
