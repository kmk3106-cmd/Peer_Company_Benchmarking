"""DI817305 — 위험보험료·예정유지비·예상보험금·예상유지비 추출.

각 회사가 entity 확장 element 또는 dart element 로 보고. 라벨 매칭으로 식별.

핵심 metric:
- 예상보험금 / 위험보험료 ratio (손실률 시그널)
- 예상유지비 / 예정유지비 ratio (사업비 마진)
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
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

# 각 metric → 라벨 키워드
METRICS = [
    ("위험보험료", ["위험보험료", "RiskPremium", "RiskInsurancePremium"]),
    ("예상보험금", ["예상보험금", "ExpectedInsuranceAmount", "ExpectedInsurancePayout", "ExpectedInsuranceBenefit"]),
    ("예정유지비", ["예정유지비", "ScheduledMaintenance", "PlannedMaintenance"]),
    ("예상유지비", ["예상유지비", "ExpectedMaintenance"]),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def find_element_by_keyword(cik: str, role_id: str, keywords: list[str]) -> str | None:
    """해당 role에서 라벨이 키워드 포함하는 element 중 가장 많은 facts."""
    where_parts = []
    params = [cik, role_id]
    for kw in keywords:
        where_parts.append("(l.LABEL LIKE ? OR v.ELEMENT_ID LIKE ?)")
        params.extend([f"%{kw}%", f"%{kw}%"])
    sql = f"""
    SELECT v.ELEMENT_ID, COUNT(*) AS n
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      AND ({" OR ".join(where_parts)})
    GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 1
    """
    r = con.execute(sql, params).fetchone()
    return r[0] if r else None


def fetch_metric_total(cik: str, element_id: str) -> float | None:
    """별도 기준 element 총합 — duration period."""
    if not element_id: return None
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231",
        element_id=element_id,
        required_members={CONS_AXIS: SEP_MEMBER},
        period_range=("2025-01-01", "2025-12-31"),
    ))


ROLE_305 = "dart_2024-06-30_role-DI817305"
ROLE_300 = "dart_2024-06-30_role-DI817300"

print("="*100)
print("계리적 metric — 위험보험료 / 예상보험금 / 예정유지비 / 예상유지비 (FY2025, 단위 억원)")
print("="*100)

# 각 회사 × metric
print(f"\n  {'회사':<10s}  {'위험보험료':>10s}  {'예상보험금':>10s}  {'예정유지비':>10s}  {'예상유지비':>10s}  {'예보/위험':>9s}  {'예유/예정':>9s}")
print("─"*110)
results = []
for cik, name, sector in PEERS:
    # 두 role 모두에서 element 찾기
    vals = {}
    for metric_name, keywords in METRICS:
        eid_305 = find_element_by_keyword(cik, ROLE_305, keywords)
        eid_300 = find_element_by_keyword(cik, ROLE_300, keywords)
        v_305 = fetch_metric_total(cik, eid_305)
        v_300 = fetch_metric_total(cik, eid_300)
        # 큰 쪽 채택 (중복 가능)
        candidates = [v for v in (v_305, v_300) if v is not None and v > 0]
        vals[metric_name] = max(candidates) if candidates else None

    def f(v): return f"{v/1e8:>7,.0f}억" if v else "       —"
    risk = vals["위험보험료"]; expect = vals["예상보험금"]
    sched = vals["예정유지비"]; exp_m = vals["예상유지비"]
    ratio1 = (expect/risk*100) if (risk and expect) else None
    ratio2 = (exp_m/sched*100) if (sched and exp_m) else None
    def pct(v): return f"{v:>7.1f}%" if v else "      —"

    print(f"  {name:<8s}  {f(risk)}  {f(expect)}  {f(sched)}  {f(exp_m)}  {pct(ratio1)}  {pct(ratio2)}")
    results.append({"cik": cik, "name": name, "sector": sector,
                    "위험보험료": risk, "예상보험금": expect,
                    "예정유지비": sched, "예상유지비": exp_m,
                    "예보_위험비율": ratio1, "예유_예정비율": ratio2})

print("\n해석:")
print("  - 예상보험금/위험보험료: 보장 마진 (100% = 보험료가 예상보험금 모두 cover)")
print("  - 예상유지비/예정유지비: 사업비 마진 (100% = 예정 사업비가 실제 예상과 일치)")
