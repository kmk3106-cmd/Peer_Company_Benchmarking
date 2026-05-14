"""§5-F — 계리 metric 연도별 분해.

위험보험료 / 예상보험금 / 예정유지비 / 예상유지비
× MaturityAxis 멤버 (1년 이내, 1-2년, ..., 30년 초과)
× 8개사 별도 기준
"""
from __future__ import annotations
import json
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, CONS_AXIS, SEP_MEMBER,
)

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
MATURITY_AXIS = "ifrs-full_MaturityAxis"

# 표준 7구간 → 멤버 패턴
BUCKET_PATTERNS = {
    "≤1년":   ["%NotLaterThanOneYear%"],
    "1-2년":  ["%LaterThanOneYearAndNotLaterThanTwoYears%"],
    "2-3년":  ["%LaterThanTwoYearsAndNotLaterThanThreeYears%"],
    "3-4년":  ["%LaterThanThreeYearsAndNotLaterThanFourYears%"],
    "4-5년":  ["%LaterThanFourYearsAndNotLaterThanFiveYears%"],
    "5-10년": ["%LaterThanFiveYearsAndNotLaterThanSixYears%", "%LaterThanSixYearsAndNotLaterThanSevenYears%",
              "%LaterThanSevenYearsAndNotLaterThanEightYears%", "%LaterThanEightYearsAndNotLaterThanNineYears%",
              "%LaterThanNineYearsAndNotLaterThanTenYears%", "%LaterThanFiveYearsAndNotLaterThanTen%",
              "%Within10Years%"],
    "10-15년": ["%LaterThanTenYearsAndNotLaterThanFifteen%", "%Over10%Within15%"],
    "15-20년": ["%LaterThanFifteenYearsAndNotLaterThanTwenty%", "%Over15%Within20%"],
    "20-25년": ["%LaterThanTwentyYearsAndNotLaterThanTwentyfive%", "%Over20%Within25%"],
    "25-30년": ["%LaterThanTwentyfiveYearsAndNotLaterThanThirty%", "%Over25Years%Within30%"],
    ">30년":  ["%LaterThanThirtyYears%", "%Over30Years%"],
}

# Metric 라벨 → ko_label 키워드
METRICS = {
    "위험보험료": ["위험보험료", "RiskPremium", "RiskInsurance"],
    "예상보험금": ["예상보험금", "ExpectedInsuranceAmount", "ExpectedInsurancePayout", "ExpectedInsuranceBenefit"],
    "예정유지비": ["예정유지비", "ScheduledMaintenance", "PlannedMaintenance"],
    "예상유지비": ["예상유지비", "ExpectedMaintenance"],
}

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def find_element_for_metric(cik: str, metric_keywords: list[str]) -> str | None:
    """ko_label 또는 element_id에 키워드 포함 element 중 fact 가장 많은 것."""
    where = " OR ".join(["l.LABEL LIKE ? OR v.ELEMENT_ID LIKE ?" for _ in metric_keywords])
    params = [cik]
    for kw in metric_keywords:
        params.extend([f"%{kw}%", f"%{kw}%"])
    sql = f"""
    SELECT v.ELEMENT_ID, COUNT(*) AS n
    FROM val_insurers v
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND v.amount_krw IS NOT NULL AND ({where})
    GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 1
    """
    r = con.execute(sql, params).fetchone()
    return r[0] if r else None


def fetch_metric_by_bucket(cik: str, element_id: str, bucket_patterns: list[str]) -> float | None:
    """element_id × MaturityAxis member matching patterns, 별도 기준 SUM."""
    if not element_id: return None
    total = None
    found_members = set()
    # 매칭되는 member 찾기
    for pat in bucket_patterns:
        for m in con.execute(f"""
          SELECT DISTINCT cx.MEMBER_ELEMENT_ID FROM cntxt_insurers cx
          WHERE cx.CIK=? AND cx.AXIS_ELEMENT_ID='{MATURITY_AXIS}'
            AND cx.MEMBER_ELEMENT_ID LIKE ?
        """, [cik, pat]).fetchall():
            found_members.add(m[0])

    for member in found_members:
        # instant·duration 둘 다 시도
        for period_kind in ["instant_2025", "duration_2025"]:
            req = {CONS_AXIS: SEP_MEMBER, MATURITY_AXIS: member}
            q = FactQuery(cik=cik, report_date="20251231", element_id=element_id, required_members=req)
            if period_kind == "instant_2025":
                q = FactQuery(cik=cik, report_date="20251231", element_id=element_id,
                              required_members=req, period_instant="2025-12-31")
            else:
                q = FactQuery(cik=cik, report_date="20251231", element_id=element_id,
                              required_members=req, period_range=("2025-01-01", "2025-12-31"))
            v = fetch_fact_sum(con, q)
            if v is not None and abs(v) > 1e5:
                total = (total or 0) + v
                break
    return total


# 실행: 각 metric × 8개사 × 7~11 buckets
results = {}
for metric_name, keywords in METRICS.items():
    print(f"\n══ {metric_name} ══")
    print(f"  {'회사':<10s}  " + "  ".join(f"{b:>9s}" for b in BUCKET_PATTERNS) + f"  {'합계':>10s}")
    metric_data = {}
    for cik, name in PEERS:
        eid = find_element_for_metric(cik, keywords)
        row = {}
        for bucket, patterns in BUCKET_PATTERNS.items():
            v = fetch_metric_by_bucket(cik, eid, patterns)
            row[bucket] = v
        metric_data[cik] = row
        total = sum(v for v in row.values() if v is not None)
        def f(v): return f"{v/1e8:>7,.0f}억" if v else "      —"
        cells = [f(row.get(b)) for b in BUCKET_PATTERNS]
        print(f"  {name:<8s}  " + "  ".join(cells) + f"  {f(total)}")
    results[metric_name] = metric_data

import json as _json
from pathlib import Path
Path("report/actuarial_by_year.json").write_text(
    _json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/actuarial_by_year.json")
