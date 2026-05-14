"""CSM 상각률 v2 — DI817105 §103 「당기서비스 변동 × CSM 컬럼」 정확 추출.

수정사항 (vs v1):
  - v1은 InsuranceRevenueContractualServiceMargin... 등 4개 element 패턴을 단순 합산.
    Mirae는 이 element를 1-63 미래기간별 인식예정 표에서 광범위하게 태깅 (90행 / 21,087억).
    결과: v1이 자사 CSM 상각액을 2.11조로 잘못 산출 → 상각률 101.95% (오류).
  - v2는 IFRS17 §103 표준 element `IncreaseDecreaseThroughChangesThatRelateToCurrentService`
    × `InsuranceContractsByComponentsAxis = ContractualServiceMargin*Member` 슬라이스를 1차 추출.
    이 셀이 「당기서비스 관련 변동」 행과 「CSM 컬럼」의 교차 = 당기 CSM 상각액.
  - 자사 미래에셋 검증: 비배당 -1,940.6억 + 배당 -117.7억 = -2,058.3억 (상각률 ≈ 9.9%).
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, fetch_csm_total_all_variants,
    CONS_AXIS, SEP_MEMBER, COMPONENTS_AXIS, COMP_CSM_ALL,
    DISAGG_AXIS, ISSUED_MEMBER,
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

CURRENT_SERVICE_ELEM = (
    "ifrs-full_IncreaseDecreaseThroughChangesThatRelateToCurrentServiceInsuranceContractsLiabilityAsset"
)
LEGACY_PATTERNS = [
    "ifrs-full_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices",
    "dart_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices",
    "ifrs-full_IncreaseDecreaseThroughRecognitionOfContractualServiceMarginInsuranceContractsLiabilityAsset",
    "ifrs-full_IncreaseDecreaseThroughRecognitionOfContractualServiceMargin",
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def fetch_csm_amort_clean(cik: str, csm_avg: float | None) -> tuple[float | None, str]:
    """§103 「당기서비스 변동 × CSM 컬럼」 셀 — IFRS17 표준 추출.

    1차: CurrentService element × CSM-component axis (Mirae, 한화생명, 동양생명 적합).
    2차: legacy patterns (Recognition-of-CSM 등 — 손보·삼성생명에 흔함).
    1차 결과가 평균 CSM의 3% 미만이면 부적합 의심 → 2차 결과와 비교 후 큰 값 채택.
    Returns (값, 산출방법).
    """
    clean = 0.0; clean_found = False
    for csm in COMP_CSM_ALL:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=CURRENT_SERVICE_ELEM,
            required_members={CONS_AXIS: SEP_MEMBER, COMPONENTS_AXIS: csm},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v is not None:
            clean += v; clean_found = True

    legacy = 0.0; legacy_found = False
    for elem in LEGACY_PATTERNS:
        for csm in COMP_CSM_ALL:
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=elem,
                required_members={CONS_AXIS: SEP_MEMBER, COMPONENTS_AXIS: csm},
                period_range=("2025-01-01", "2025-12-31"),
            ))
            if v is not None:
                legacy += v; legacy_found = True
        v2 = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=elem,
            required_members={CONS_AXIS: SEP_MEMBER},
            forbidden_axes=(COMPONENTS_AXIS,),
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v2 is not None and abs(v2) > abs(legacy):
            legacy = v2; legacy_found = True

    clean_abs = abs(clean) if clean_found else 0
    legacy_abs = abs(legacy) if legacy_found else 0
    threshold = (csm_avg or 0) * 0.03  # 평균 CSM의 3% 미만이면 1차 부적합

    if clean_abs > threshold and clean_found:
        return clean_abs, "v2-clean (CurrentService × CSM-component)"
    if legacy_abs > 0:
        return legacy_abs, "v2-fallback (legacy patterns)"
    if clean_abs > 0:
        return clean_abs, "v2-clean (low confidence)"
    return None, "no-data"


print("="*110)
print("CSM 상각률 v2 — DI817105 §103 「당기서비스 × CSM 컬럼」 정확 추출")
print("="*110)
print(f"\n  {'회사':<10s}  {'기시 CSM':>13s}  {'기말 CSM':>13s}  {'평균 CSM':>13s}  {'당기 상각':>13s}  {'상각률':>8s}  방법")
print("─"*110)

results = {}
for cik, name in PEERS:
    beg = fetch_csm_total_all_variants(con, cik, "20251231", "2024-12-31")
    end = fetch_csm_total_all_variants(con, cik, "20251231", "2025-12-31")
    avg = ((beg or 0) + (end or 0)) / 2 if (beg and end) else None
    amort, method = fetch_csm_amort_clean(cik, avg)

    rate = None
    if amort and avg and abs(avg) > 1e8:
        rate = amort / abs(avg) * 100

    def f(v): return f"{v/1e8:>+10,.0f}억" if v else "         —"
    rate_s = f"{rate:>6.1f}%" if rate else "     —"
    print(f"  {name:<8s}  {f(beg)}  {f(end)}  {f(avg)}  {f(amort)}  {rate_s}  {method}")
    results[cik] = {"beg": beg, "end": end, "avg": avg, "amort": amort, "rate": rate, "method": method}

Path("report/csm_amortization.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/csm_amortization.json (v2)")
