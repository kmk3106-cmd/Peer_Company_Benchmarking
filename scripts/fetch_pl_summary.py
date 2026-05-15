"""8개사 + 자사 보험서비스수익·보험서비스비용·당기순이익 정확 추출."""
from __future__ import annotations
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

ELEMS = [
    ("보험서비스수익", "ifrs-full_InsuranceRevenue"),
    ("보험서비스비용 (1차)", "ifrs-full_InsuranceServiceExpense"),
    ("보험서비스비용 (2차)", "ifrs-full_InsuranceServiceExpensesFromInsuranceContractsIssued"),
    ("보험서비스결과", "ifrs-full_InsuranceServiceResult"),
    ("당기순이익", "ifrs-full_ProfitLoss"),
    ("당기순이익 (계속영업)", "ifrs-full_ProfitLossFromContinuingOperations"),
]

print(f"{'회사':<14s}  " + "  ".join(f"{n:>14s}" for n, _ in ELEMS))
print("─"*120)
for cik, name in PEERS:
    cells = []
    for label, elem in ELEMS:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=elem,
            required_members={CONS_AXIS: SEP_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        cells.append(f"{v/1e8:>11,.0f}억" if v else "         —")
    print(f"  {name:<12s}  " + "  ".join(cells))
