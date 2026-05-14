"""8개사 BS 발행보험계약부채 잔액 재검증 — n_axes-safe fetcher 사용.

비교: 종전 SUM 방식 (n_axes redundancy 포함) vs n_axes-safe.
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_balance_separate_issued,
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER,
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
]

# 참고 — 사업보고서 BS 보험계약부채 (공개 자료 기준, 별도, FY2025 기말)
# 미래에셋생명은 27조 검증됨, 다른 회사는 대략적 reference
REFERENCE_BS_조 = {
    "00112332": 27.0,    # 미래에셋 — 27.00조 (사업보고서 확인)
    "00126256": 200.0,   # 삼성생명 — 200조 대
    "00113058": 100.0,   # 한화생명 — 100조 대
    "00117267": 28.0,    # 동양생명 — 28조 대
    "00139214": 49.0,    # 삼성화재
    "00164973": 35.0,    # 현대해상
    "00159102": 50.0,    # DB손보
    "00135917": 25.0,    # 한화손보
}


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

    print(f"\n{'회사':<14s}  {'n_axes-safe':>15s}  {'종전 SUM':>15s}  {'참고 BS':>10s}  {'safe vs ref':>12s}")
    print("─" * 80)

    for cik, name in PEERS:
        # n_axes-safe (MIN n_axes only)
        safe = fetch_balance_separate_issued(con, cik, "20251231", "2025-12-31")
        safe_조 = safe / 1e12 if safe else 0

        # 종전 SUM (n_axes 무시)
        raw = con.execute(f"""
          SELECT SUM(v.amount_krw)/1e12
          FROM val_insurers v
          WHERE v.CIK=? AND v.amount_krw IS NOT NULL
            AND v.ELEMENT_ID='ifrs-full_InsuranceContractsIssuedThatAreLiabilities'
            AND EXISTS (SELECT 1 FROM cntxt_insurers c
              WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
                AND c.AXIS_ELEMENT_ID='{CONS_AXIS}' AND c.MEMBER_ELEMENT_ID='{SEP_MEMBER}')
            AND EXISTS (SELECT 1 FROM cntxt_insurers p
              WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
                AND p.PERIOD_INSTANT='2025-12-31')
        """, [cik]).fetchone()[0] or 0

        ref = REFERENCE_BS_조.get(cik, 0)
        ratio = (safe_조 / ref * 100) if ref else 0

        print(f"  {name:<12s}  {safe_조:>10.2f}조  {raw:>10.2f}조  {ref:>6.2f}조  {ratio:>8.1f}%")


if __name__ == "__main__":
    main()
