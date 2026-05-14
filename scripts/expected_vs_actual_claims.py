"""예실차 (Expected vs Actual Claims) — 8개사.

예상보험금 (entity element) vs 실제 발생사고비용 (ifrs-full 표준).
예실차 = (실제 - 예상) / 예상 × 100%   (양수 = 실제가 예상 초과 = 위험)
"""
from __future__ import annotations
import json, duckdb
from peer_benchmarking.analysis.fact_fetcher import fetch_fact_sum, FactQuery, CONS_AXIS, SEP_MEMBER

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


def find_expected_element(cik: str) -> str | None:
    """예상보험금 라벨 매칭 element."""
    r = con.execute("""
      SELECT v.ELEMENT_ID, COUNT(*) AS n
      FROM val_insurers v
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND v.amount_krw IS NOT NULL
        AND (l.LABEL = '예상보험금'
             OR l.LABEL = 'IFRS 17의 적용범위에 포함되는 계약에서 생기는 예상보험금'
             OR l.LABEL LIKE '%할인되지 않은 예상보험금%'
             OR l.LABEL LIKE '%보험계약에서 생기는 할인되지 않은 예상보험금 추정치%')
      GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 1
    """, [cik]).fetchone()
    return r[0] if r else None


def fetch_sum(cik, elem):
    if not elem: return None
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231", element_id=elem,
        required_members={CONS_AXIS: SEP_MEMBER},
        period_range=("2025-01-01", "2025-12-31"),
    ))


def fetch_sum_instant(cik, elem, period):
    if not elem: return None
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231", element_id=elem,
        required_members={CONS_AXIS: SEP_MEMBER},
        period_instant=period,
    ))


def fetch_sum_all_periods(cik, elem):
    """예상보험금은 instant + duration 모두 시도, 큰 쪽."""
    if not elem: return None
    candidates = []
    for period in [("instant", "2025-12-31"), ("duration", ("2025-01-01", "2025-12-31"))]:
        if period[0] == "instant":
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=elem,
                required_members={CONS_AXIS: SEP_MEMBER},
                period_instant=period[1],
            ))
        else:
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=elem,
                required_members={CONS_AXIS: SEP_MEMBER},
                period_range=period[1],
            ))
        if v is not None: candidates.append(v)
    return max(candidates, key=abs) if candidates else None


# 실제 발생사고비용 - 표준 element
ACTUAL_ELEM_BASE = "ifrs-full_IncreaseDecreaseThroughIncurredClaimsAndOtherIncurredInsuranceServiceExpenses"


def find_actual_element(cik: str) -> str | None:
    r = con.execute("""
      SELECT v.ELEMENT_ID, COUNT(*) AS n
      FROM val_insurers v
      WHERE v.CIK=? AND v.amount_krw IS NOT NULL
        AND v.ELEMENT_ID LIKE 'ifrs-full_IncreaseDecreaseThroughIncurredClaimsAndOtherIncurred%InsuranceContracts%'
      GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 1
    """, [cik]).fetchone()
    return r[0] if r else None


print("="*100)
print("예실차 (Expected vs Actual Claims) — FY2025 별도 기준")
print("="*100)
print(f"\n  {'회사':<10s}  {'예상보험금':>15s}  {'실제 발생사고비용':>18s}  {'예실차(절대)':>14s}  {'예실비율':>10s}  시그널")
print("─"*110)

results = {}
for cik, name in PEERS:
    exp_e = find_expected_element(cik)
    act_e = find_actual_element(cik)
    exp_v = fetch_sum_all_periods(cik, exp_e)
    act_v = fetch_sum(cik, act_e)

    diff = None; ratio = None
    if exp_v and act_v and abs(exp_v) > 1e8:
        diff = act_v - exp_v
        ratio = act_v / exp_v * 100

    def f(v): return f"{v/1e8:>11,.0f}억" if v else "        —"
    diff_s = f(diff) if diff is not None else "        —"
    ratio_s = f"{ratio:>7.1f}%" if ratio else "      —"
    signal = ""
    if ratio is not None:
        if ratio > 110: signal = "⚠ 실제가 예상 크게 초과 (손실 risk)"
        elif ratio > 100: signal = "실제 > 예상 (소폭 초과)"
        elif ratio > 90: signal = "실제 ≈ 예상"
        else: signal = "✓ 실제 < 예상 (보수적)"

    print(f"  {name:<8s}  {f(exp_v)}  {f(act_v)}  {diff_s}  {ratio_s}  {signal}")
    results[cik] = {
        "expected": exp_v, "actual": act_v,
        "diff": diff, "ratio": ratio,
        "exp_elem": exp_e, "act_elem": act_e,
    }

from pathlib import Path
Path("report/expected_vs_actual.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/expected_vs_actual.json")
