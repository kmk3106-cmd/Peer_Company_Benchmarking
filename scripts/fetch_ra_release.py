"""RA 상각 (위험조정 해소) element 정확 search + 8개사 추출.

표준 element: ifrs-full_InsuranceRevenueChangeInRiskAdjustmentForNonfinancialRisk
  (보험수익 중 위험조정 해소 기여분 — 양수 = RA가 줄어들면서 보험수익으로 인식)

예실차 도출:
  보험수익 - 보험서비스비용 = CSM 상각 + RA 상각 + 예실차
  → 예실차 = 보험서비스결과 - CSM 상각 - RA 상각
"""
from __future__ import annotations
import json
import duckdb
from peer_benchmarking.analysis.fact_fetcher import fetch_fact_sum, FactQuery, CONS_AXIS, SEP_MEMBER

PEERS = [
    ("00112332", "미래에셋생명"),
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손해보험"),
    ("00135917", "한화손해보험"),
    ("00103176", "흥국화재"),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# RA 상각 element 후보 — 표준 + entity 확장
RA_RELEASE_PATTERNS = [
    ("표준 - 보험수익 RA 해소",
     "ifrs-full_InsuranceRevenueChangeInRiskAdjustmentForNonfinancialRisk"),
    ("표준 (LRC LossComp 제외)",
     "ifrs-full_InsuranceRevenueChangeInRiskAdjustmentForNonfinancialRiskExcludingLossComponent"),
]

print("="*100)
print("RA 상각 element 회사별 search 결과")
print("="*100)
for cik, name in PEERS:
    print(f"\n  ── {name} ──")
    for label, eid in RA_RELEASE_PATTERNS:
        rows = con.execute("""
          SELECT COUNT(*) AS n,
                 MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko
          FROM val_insurers v
          LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
          WHERE v.CIK=? AND v.ELEMENT_ID=? AND v.amount_krw IS NOT NULL
          GROUP BY v.ELEMENT_ID
        """, [cik, eid]).fetchone()
        if rows and rows[0] > 0:
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=eid,
                required_members={CONS_AXIS: SEP_MEMBER},
                period_range=("2025-01-01", "2025-12-31"),
            ))
            v_s = f"{v/1e8:,.0f}억" if v else "—"
            print(f"    ✓ [{label}] facts={rows[0]} 값={v_s} ← {rows[1] or ''}")
        else:
            print(f"    ✗ [{label}] 미공시")

# 종합 (가장 큰 값 채택)
print("\n\n" + "="*100)
print("RA 상각 — 채택값 (FY2025 별도)")
print("="*100)

results = {}
for cik, name in PEERS:
    best = None; src = ""
    for label, eid in RA_RELEASE_PATTERNS:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v is not None and (best is None or abs(v) > abs(best)):
            best = v; src = label
    results[cik] = {"name": name, "ra_release": best, "source": src}
    v_s = f"{best/1e8:,.0f}억" if best else "—"
    print(f"  {name:<14s}  {v_s}  ({src})")

from pathlib import Path
Path("report/ra_release.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/ra_release.json")
