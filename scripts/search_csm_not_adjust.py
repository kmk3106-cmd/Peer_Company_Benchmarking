"""미래에셋 + 8개사 「보험계약마진을 조정하지 않는」 element 정확 search."""
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
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

print("="*100)
print("회사별 「보험계약마진을 조정하지 않는」 element 정확 search")
print("="*100)

for cik, name in PEERS:
    sql = """
    SELECT v.ELEMENT_ID,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
           COUNT(*) AS n
    FROM val_insurers v
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND v.amount_krw IS NOT NULL
      AND (l.LABEL LIKE '%보험계약마진을 조정하지 않는%'
           OR l.LABEL LIKE '%CSM을 조정하지 않는%'
           OR l.LABEL LIKE '%보험계약마진 미조정%')
    GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 5
    """
    rows = con.execute(sql, [cik]).fetchall()
    print(f"\n  ── {name} ──")
    for eid, ko, n in rows:
        eshort = eid.replace("ifrs-full_","").replace(f"entity{cik}_","#")[:75]
        print(f"    [{n:>4d}] {eshort:<77s}")
        print(f"          ← {ko}")
        # 정확값
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        v_s = f"{v/1e8:+,.0f}억" if v else "(별도·duration 매치 없음)"
        print(f"          값: {v_s}")
