"""CSM 변동 무브먼트 — DI817100 × ComponentsAxis=CSM 분해.

기시 CSM (2024-12-31)
+ 신계약 인식 (EffectsOfContractsInitiallyRecognised)
+ 추정변동 CSM 조정 (ChangesInEstimatesThatAdjustCSM)
+ 경험조정 (ExperienceAdjustments)
+ 보험금융손익 (InsuranceFinanceIncomeOrExpenses)
+ 기타 변동 (OtherChanges)
- CSM 상각 (InsuranceRevenueCSMRecognisedInPL — CSM이 보험수익으로 인식되며 차감)
= 기말 CSM (2025-12-31)

검증: 기시 + Σ(변동) = 기말
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, fetch_components_total, fetch_csm_total_all_variants,
    CONS_AXIS, SEP_MEMBER, COMPONENTS_AXIS,
    COMP_CSM_ALL,
)

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

# CSM 변동 element 패턴 (LIKE) - 라인 이름 매핑
CSM_MOVEMENT_LINES = [
    ("신계약 인식",   ["%EffectsOfContractsInitiallyRecognised%"]),
    ("CSM 조정 추정변동", ["%ChangesInEstimatesThatAdjustContractualServiceMargin%"]),
    ("CSM 미조정 추정변동", ["%ChangesInEstimatesThatDoNotAdjustContractualServiceMargin%"]),
    ("경험조정",      ["%ExperienceAdjustments%InsuranceContracts%"]),
    ("과거서비스 변동", ["%RelateToPastServiceInsuranceContracts%", "%RelateToFutureService%"]),
    ("보험금융손익",   ["%InsuranceFinanceIncomeOrExpenses%InsuranceContracts%", "%InsuranceFinanceIncomeExpenses%InsuranceContracts%"]),
    ("CSM 상각(보험수익)", ["%InsuranceRevenueContractualServiceMargin%", "%RecognitionOfContractualServiceMargin%"]),
    ("환율변동",      ["%ChangesInForeignExchangeRates%", "%dart_ChangesInForeignExchangeRates%"]),
    ("기타증감",      ["%OtherChangesLiabilitiesUnderInsuranceContracts%", "%AdditionalItemsNecessary%"]),
]


con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def find_elements(cik: str, patterns: list[str]) -> list[str]:
    or_parts = " OR ".join("v.ELEMENT_ID LIKE ?" for _ in patterns)
    sql = f"""
    SELECT DISTINCT v.ELEMENT_ID FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817100' AND v.amount_krw IS NOT NULL
      AND ({or_parts})
    """
    return [r[0] for r in con.execute(sql, [cik] + patterns).fetchall()]


def fetch_csm_movement_line(cik: str, patterns: list[str]) -> float | None:
    """ComponentsAxis=CSM (4가지 변형 모두) × 매칭 element × duration FY2025 합산."""
    eids = find_elements(cik, patterns)
    if not eids: return None
    total = 0; found = False
    for eid in eids:
        for csm_member in COMP_CSM_ALL:
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=eid,
                required_members={CONS_AXIS: SEP_MEMBER, COMPONENTS_AXIS: csm_member},
                period_range=("2025-01-01", "2025-12-31"),
            ))
            if v is not None:
                total += v
                found = True
    return total if found else None


print("="*120)
print("CSM 변동 무브먼트 — 8개사 (FY2025 별도, 단위: 억원)")
print("="*120)

# 컬럼 정의
COLS = ["기시 CSM"] + [n for n, _ in CSM_MOVEMENT_LINES] + ["변동 합", "기말 CSM (계산)", "기말 CSM (실측)", "오차"]

# 헤더
print(f"\n  {'회사':<10s}  " + "  ".join(f"{c[:12]:>10s}" for c in COLS))
print("─"*150)

results = {}
for cik, name in PEERS:
    row = {}
    # 기시·기말 CSM 잔액
    beg = fetch_csm_total_all_variants(con, cik, "20251231", "2024-12-31") or 0
    end = fetch_csm_total_all_variants(con, cik, "20251231", "2025-12-31") or 0
    row["기시 CSM"] = beg
    # 변동 라인별
    for label, patterns in CSM_MOVEMENT_LINES:
        v = fetch_csm_movement_line(cik, patterns)
        row[label] = v
    # 변동 합
    move_sum = sum(v for v in [row[n] for n, _ in CSM_MOVEMENT_LINES] if v is not None)
    row["변동 합"] = move_sum
    row["기말 CSM (계산)"] = beg + move_sum
    row["기말 CSM (실측)"] = end
    row["오차"] = (beg + move_sum) - end

    def f(v): return f"{v/1e8:>+9,.0f}억" if v else "       —"
    cells = [f(row[c]) for c in COLS]
    print(f"  {name:<8s}  " + "  ".join(cells))
    results[cik] = row

Path("report/csm_movement.json").write_text(
    json.dumps({c: {k: v for k, v in r.items()} for c, r in results.items()},
               ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/csm_movement.json")
