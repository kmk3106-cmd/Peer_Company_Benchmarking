"""손실부담계약 손실/환입 후보 element 값 추출."""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
)

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

CANDIDATES = [
    ("A", "ifrs-full_IncreaseDecreaseThroughEffectsOfGroupsOfOnerousContractsInitiallyRecognisedInPeriodInsuranceContractsLiabilityAsset", "신규손실부담계약 효과"),
    ("B", "dart_InsuranceServiceExpensesAmountsThroughChangesThatRelateToFutureService", "보험서비스비용-미래서비스 손실(환입)"),
    ("C", "ifrs-full_IncreaseDecreaseThroughChangesThatRelateToFutureServiceInsuranceContractsLiabilityAsset", "미래서비스변동 손실(환입)"),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def fetch(cik, eid, with_issued=True):
    req = {CONS_AXIS: SEP_MEMBER}
    if with_issued:
        req[DISAGG_AXIS] = ISSUED_MEMBER
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231", element_id=eid,
        required_members=req, period_range=("2025-01-01", "2025-12-31"),
    ))


for code, eid, name in CANDIDATES:
    print(f"\n[{code}] {name}")
    print(f"    element: {eid[:80]}")
    print("─"*80)
    for cik, peer in PEERS:
        v_issued = fetch(cik, eid, with_issued=True)
        v_sep = fetch(cik, eid, with_issued=False)
        def f(v): return f"{v/1e8:>+9,.0f}억" if v is not None else "        -"
        print(f"  {peer:<14s}  발행={f(v_issued)}  별도전체={f(v_sep)}")
