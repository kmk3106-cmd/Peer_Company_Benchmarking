"""LOSS발생분 (손실부담계약 비용 전입·환입) element 정확 search.

표준 IFRS17 element 후보:
- ifrs-full_InsuranceServiceExpensesLossesOnOnerousContractsAndReversalsOfSuchLosses
- ifrs-full_LossesOnOnerousInsuranceContractsAndReversalsOfSuchLossesArisingFromInsuranceContractsIssuedRecognisedInProfitOrLoss
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

# 라벨 키워드로 회사별 element search
KEYWORDS = ["손실부담", "손실요소", "Onerous", "LossComponent", "LossesAndReversal", "ReversalsOfLosses"]

print("="*100)
print("회사별 손실부담계약 비용 (LOSS발생분) element search")
print("="*100)
for cik, name in PEERS:
    print(f"\n  ── {name} ──")
    where = " OR ".join(["l.LABEL LIKE ? OR v.ELEMENT_ID LIKE ?" for _ in KEYWORDS])
    params = [cik]
    for kw in KEYWORDS:
        params.extend([f"%{kw}%", f"%{kw}%"])
    sql = f"""
    SELECT v.ELEMENT_ID,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
           COUNT(*) AS n
    FROM val_insurers v
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND v.amount_krw IS NOT NULL AND ({where})
    GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 6
    """
    for eid, ko, n in con.execute(sql, params).fetchall():
        eshort = eid.replace("ifrs-full_","").replace("dart_","d:").replace(f"entity{cik}_","#")[:65]
        print(f"    [{n:>5d}] {eshort:<67s} ← {ko or ''}")
