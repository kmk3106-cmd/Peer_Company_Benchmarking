"""DI818200 — 총 금융자산 vs 보험계약부채 ratio (자산-부채 매칭).

각 회사 별도 기준:
- 총 금융자산 (DI818200, ifrs-full_FinancialAssets 류)
- 보험계약부채 (DI817105, IssuedThatAreLiabilities, 26~200조)
- Coverage ratio = 자산 / 부채
- BS 부채총계도 참고
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    fetch_balance_separate_issued,
    CONS_AXIS, SEP_MEMBER,
)

PEERS = [
    ("00112332", "미래에셋", "life"),
    ("00126256", "삼성생명", "life"),
    ("00113058", "한화생명", "life"),
    ("00117267", "동양생명", "life"),
    ("00139214", "삼성화재", "non_life"),
    ("00164973", "현대해상", "non_life"),
    ("00159102", "DB손보", "non_life"),
    ("00135917", "한화손보", "non_life"),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def find_total_financial_asset_element(cik: str) -> str | None:
    """DI818200 에서 '총 금융자산' 라벨 element 찾기."""
    sql = """
    SELECT v.ELEMENT_ID, COUNT(*) AS n
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI818200'
      AND v.amount_krw IS NOT NULL
      AND (l.LABEL LIKE '%총 금융자산%' OR v.ELEMENT_ID = 'ifrs-full_FinancialAssets')
    GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 1
    """
    r = con.execute(sql, [cik]).fetchone()
    return r[0] if r else None


print("="*110)
print("자산-부채 매칭 (FY2025 기말, 별도)")
print("="*110)

print(f"\n  {'회사':<10s}  {'총 금융자산':>14s}  {'보험계약부채':>14s}  {'Coverage':>10s}  {'차이':>14s}  {'sector':<8s}")
print("─"*110)

for cik, name, sector in PEERS:
    # 1) 총 금융자산 (DI818200)
    asset_elem = find_total_financial_asset_element(cik)
    asset = fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231",
        element_id=asset_elem or "ifrs-full_FinancialAssets",
        required_members={CONS_AXIS: SEP_MEMBER},
        period_instant="2025-12-31",
    )) if asset_elem else None

    # 2) 보험계약부채 (BS 발행보험)
    liab = fetch_balance_separate_issued(con, cik, "20251231", "2025-12-31")

    def f(v): return f"{v/1e12:>10,.2f}조" if v else "         —"
    cov = None
    diff = None
    if asset and liab:
        cov = asset / liab * 100
        diff = asset - liab

    cov_s = f"{cov:>8.1f}%" if cov else "        —"
    diff_s = f"{diff/1e12:>+9,.2f}조" if diff else "         —"

    print(f"  {name:<8s}  {f(asset)}  {f(liab)}  {cov_s}  {diff_s}  {sector}")
