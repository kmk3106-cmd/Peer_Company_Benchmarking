"""표준 IFRS17 손실부담 비용(P&L) element 추출.

ifrs-full_InsuranceServiceExpensesLossesOnOnerousContractsAndReversalsOfSuchLosses
= 보험서비스비용 중 손실부담계약 손실 및 환입분.

또는 entity 확장 / dart element 시도.
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

# 보험서비스비용 안의 손실부담 관련 element (P&L) 후보
LOSS_PNL_ELEMS = [
    "ifrs-full_InsuranceServiceExpensesLossesOnOnerousContractsAndReversalsOfSuchLosses",
    "ifrs-full_LossesOnOnerousInsuranceContractsAndReversalsOfSuchLossesArisingFromInsuranceContractsIssuedRecognisedInProfitOrLoss",
    "dart_InsuranceServiceExpensesAmountsThroughChangesThatRelateToFutureService",
]

# fallback element_id LIKE 패턴
LOSS_PNL_PATTERNS = [
    "%InsuranceServiceExpensesLossesOnOnerousContractsAndReversals%",
    "%InsuranceServiceExpensesAmountsThroughChangesThatRelateToFutureService%",
    "%LossesOnOnerousInsuranceContracts%",
]

print("="*100)
print("표준 element 별 회사별 추출")
print("="*100)
results = {}
for cik, name in PEERS:
    best = None; src = None
    # 1. 직접 element_id
    for eid in LOSS_PNL_ELEMS:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v is not None:
            if best is None or abs(v) > abs(best):
                best = v; src = eid.split("_")[-1][:50]
    # 2. LIKE 패턴 (entity 확장 포함)
    if best is None:
        for pat in LOSS_PNL_PATTERNS:
            rows = con.execute("""
              SELECT v.ELEMENT_ID, SUM(v.amount_krw) FROM val_insurers v
              WHERE v.CIK=? AND v.amount_krw IS NOT NULL AND v.ELEMENT_ID LIKE ?
                AND EXISTS (SELECT 1 FROM cntxt_insurers c WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE
                  AND c.CONTEXT_ID=v.CONTEXT_ID AND c.AXIS_ELEMENT_ID=? AND c.MEMBER_ELEMENT_ID=?)
                AND EXISTS (SELECT 1 FROM cntxt_insurers p WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE
                  AND p.CONTEXT_ID=v.CONTEXT_ID AND p.PERIOD_START_DATE='2025-01-01' AND p.PERIOD_END_DATE='2025-12-31')
              GROUP BY v.ELEMENT_ID ORDER BY ABS(SUM(v.amount_krw)) DESC LIMIT 1
            """, [cik, pat, CONS_AXIS, SEP_MEMBER]).fetchone()
            if rows and rows[1]:
                if best is None or abs(rows[1]) > abs(best):
                    best = float(rows[1])
                    src = rows[0][:60]

    results[cik] = {"name": name, "loss_pnl": best, "source": src}
    v_s = f"{best/1e8:+,.0f}억" if best else "—"
    print(f"  {name:<14s}  {v_s}  ({src or 'none'})")

from pathlib import Path
Path("report/loss_component_pnl.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/loss_component_pnl.json")
