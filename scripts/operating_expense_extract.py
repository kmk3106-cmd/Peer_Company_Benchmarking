"""사업비 영역 8개사 추출 — 공통 element 활용."""
from __future__ import annotations
import json
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, CONS_AXIS, SEP_MEMBER,
)

PEERS = [
    ("00112332", "미래에셋", "생보"),
    ("00126256", "삼성생명", "생보"),
    ("00113058", "한화생명", "생보"),
    ("00117267", "동양생명", "생보"),
    ("00139214", "삼성화재", "손보"),
    ("00164973", "현대해상", "손보"),
    ("00159102", "DB손보", "손보"),
    ("00135917", "한화손보", "손보"),
]

# 사업비 핵심 element (전부 duration period, DI320000 손익계산서)
EXPENSE_ELEMS = [
    ("판매비와관리비", "ifrs-full_SellingGeneralAndAdministrativeExpense"),
    ("보험영업비용", "dart_OperatingExpenseInsurance"),
    ("투자영업비용", "dart_OperatingExpenseInvestment"),
    ("기타보험영업비용", "dart_OtherOperatingExpenseInsurance"),
    ("기타투자영업비용", "dart_OtherOperatingExpenseInvestment"),
    ("영업외비용", "dart_NonOperatingExpense"),
]

# 참고: 보험수익 (분모로 사용)
BENCHMARK_REVENUE = "ifrs-full_InsuranceRevenue"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def fetch_sum(cik, element_id):
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231", element_id=element_id,
        required_members={CONS_AXIS: SEP_MEMBER},
        period_range=("2025-01-01", "2025-12-31"),
    ))


print("="*120)
print("사업비 영역 — 8개사 FY2025 별도 손익 항목 (단위: 억원)")
print("="*120)
print(f"\n  {'회사':<10s}  " + "  ".join(f"{n:>11s}" for n, _ in EXPENSE_ELEMS) + f"  {'보험수익':>13s}  {'사업비율':>9s}")
print("─"*150)

results = {}
for cik, name, sector in PEERS:
    row = {"sector": sector}
    for label, eid in EXPENSE_ELEMS:
        v = fetch_sum(cik, eid)
        row[label] = v
    revenue = fetch_sum(cik, BENCHMARK_REVENUE)
    row["보험수익"] = revenue

    # 핵심 사업비 = 판관비 + 보험영업비용 (간단 합)
    핵심_사업비 = (row["판매비와관리비"] or 0) + (row["보험영업비용"] or 0)
    expense_ratio = (핵심_사업비 / revenue * 100) if revenue and abs(revenue) > 1e8 else None
    row["핵심사업비"] = 핵심_사업비
    row["사업비율"] = expense_ratio

    def f(v):
        if v is None: return "       —"
        return f"{v/1e8:>8,.0f}억"
    cells = [f(row[n]) for n, _ in EXPENSE_ELEMS] + [f(revenue)]
    ratio_s = f"{expense_ratio:>7.1f}%" if expense_ratio else "      —"
    print(f"  {name:<8s}  " + "  ".join(cells) + f"  {ratio_s}")
    results[cik] = row

import json as _json
from pathlib import Path
Path("report/operating_expense_results.json").write_text(
    _json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/operating_expense_results.json")
