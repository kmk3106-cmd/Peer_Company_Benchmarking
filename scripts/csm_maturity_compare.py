"""CSM 만기 분포 — 미래에셋 7구간 표준화 매핑 후 8개사 비교.

표준 7구간:
  ≤10년 / 10-15년 / 15-20년 / 20-25년 / 25-30년 / >30년

타사 36구간 → 7구간 매핑:
  1년이내 + 1-2 + 2-3 + ... + 9-10 = ≤10년
  10-15 → 10-15
  15-20 → 15-20
  20-25 → 20-25
  25-30 → 25-30
  30+ → >30
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
)

MATURITY_AXIS = "ifrs-full_MaturityAxis"

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

# 표준 단기 멤버 (10년 이내)
SHORT_TERM_MEMBERS = [
    "ifrs-full_NotLaterThanOneYear",
    "ifrs-full_LaterThanOneYearAndNotLaterThanTwoYears",
    "ifrs-full_LaterThanTwoYearsAndNotLaterThanThreeYears",
    "ifrs-full_LaterThanThreeYearsAndNotLaterThanFourYears",
    "ifrs-full_LaterThanFourYearsAndNotLaterThanFiveYears",
    "ifrs-full_LaterThanFiveYearsAndNotLaterThanSixYears",
    "ifrs-full_LaterThanSixYearsAndNotLaterThanSevenYears",
    "ifrs-full_LaterThanSevenYearsAndNotLaterThanEightYears",
    "ifrs-full_LaterThanEightYearsAndNotLaterThanNineYears",
    "ifrs-full_LaterThanNineYearsAndNotLaterThanTenYears",
]

# 동일 만기 구간을 다양한 회사 멤버로 매핑
BUCKET_MEMBERS = {
    "≤10년": SHORT_TERM_MEMBERS + ["Member"],  # entity 'Within10Years' 도 마지막에 별도 처리
    "10-15년": ["ifrs-full_LaterThanTenYearsAndNotLaterThanFifteenYearsMember", "ifrs-full_LaterThanTenYearsAndNotLaterThanFifteenYears"],
    "15-20년": ["ifrs-full_LaterThanFifteenYearsAndNotLaterThanTwentyYearsMember", "ifrs-full_LaterThanFifteenYearsAndNotLaterThanTwentyYears"],
    "20-25년": ["ifrs-full_LaterThanTwentyYearsAndNotLaterThanTwentyfiveYearsMember", "ifrs-full_LaterThanTwentyYearsAndNotLaterThanTwentyfiveYears"],
    "25-30년": ["ifrs-full_LaterThanTwentyfiveYearsAndNotLaterThanThirtyYearsMember", "ifrs-full_LaterThanTwentyfiveYearsAndNotLaterThanThirtyYears"],
    ">30년": ["ifrs-full_LaterThanThirtyYearsMember", "ifrs-full_LaterThanThirtyYears"],
}

# Entity 확장 멤버 (미래에셋 등)
ENTITY_SHORT_PATTERN = "Within10Years"
ENTITY_LONG_PATTERN = "Over30Years"
ENTITY_25_30_PATTERN = "Over25Years"
ENTITY_10_15_PATTERN = "Over10"  # rough

CSM_RECOGNISED_ELEM = "ifrs-full_ContractualServiceMargin"  # 잔액 element (instant)

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def find_maturity_members(cik: str) -> list[tuple[str, str]]:
    """해당 회사가 사용하는 만기 멤버."""
    rows = con.execute(f"""
      SELECT DISTINCT cx.MEMBER_ELEMENT_ID, MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END)
      FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      JOIN cntxt_insurers cx ON cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=cx.MEMBER_ELEMENT_ID AND l.LANG='ko'
      WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817300'
        AND v.amount_krw IS NOT NULL
        AND cx.AXIS_ELEMENT_ID='{MATURITY_AXIS}'
      GROUP BY cx.MEMBER_ELEMENT_ID
    """, [cik]).fetchall()
    return rows


def classify_maturity(member: str, ko: str) -> str:
    """멤버 → 7구간 매핑."""
    text = (member or "") + " " + (ko or "")
    # 표준 IFRS
    if any(s in member for s in [
        "NotLaterThanOneYear", "OneYearAndNotLaterThanTwo", "TwoYearsAndNotLaterThanThree",
        "ThreeYearsAndNotLaterThanFour", "FourYearsAndNotLaterThanFive",
        "FiveYearsAndNotLaterThanSix", "SixYearsAndNotLaterThanSeven",
        "SevenYearsAndNotLaterThanEight", "EightYearsAndNotLaterThanNine",
        "NineYearsAndNotLaterThanTen", "FiveYearsAndNotLaterThanTenYears",
    ]):
        return "≤10년"
    if "TenYearsAndNotLaterThanFifteen" in member: return "10-15년"
    if "FifteenYearsAndNotLaterThanTwentyMember" in member or "FifteenYearsAndNotLaterThanTwenty" in member: return "15-20년"
    if "TwentyYearsAndNotLaterThanTwentyfive" in member: return "20-25년"
    if "TwentyfiveYearsAndNotLaterThanThirty" in member: return "25-30년"
    if "LaterThanThirtyYears" in member: return ">30년"
    # Entity
    if "Within10Years" in member: return "≤10년"
    if "Over30Years" in member: return ">30년"
    if "Over25Years" in member and "Within30" in member: return "25-30년"
    if "Within10" in member: return "≤10년"
    # 라벨 fallback
    if ko:
        if "10년 이내" in ko or "1년" in ko or "5년 이내" in ko: return "≤10년"
        if "10년 초과 15년" in ko: return "10-15년"
        if "15년 초과 20년" in ko: return "15-20년"
        if "20년 초과 25년" in ko: return "20-25년"
        if "25년 초과 30년" in ko: return "25-30년"
        if "30년 초과" in ko: return ">30년"
    return "미분류"


def fetch_csm_by_maturity(cik: str, member: str) -> float | None:
    """CSM 만기별 기대 인식액 — duration 또는 instant 시도."""
    # 1차: instant 시점 (2025-12-31)
    v = fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231",
        element_id=CSM_RECOGNISED_ELEM,
        required_members={
            CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER,
            MATURITY_AXIS: member,
        },
        period_instant="2025-12-31",
    ))
    if v is not None: return v
    # 2차: duration
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231",
        element_id=CSM_RECOGNISED_ELEM,
        required_members={
            CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER,
            MATURITY_AXIS: member,
        },
        period_range=("2025-01-01", "2025-12-31"),
    ))


BUCKETS = ["≤10년", "10-15년", "15-20년", "20-25년", "25-30년", ">30년"]

print("="*100)
print("CSM 만기별 인식 기대액 (FY2025) — 8개사 × 7 표준 구간 (단위: 억원)")
print("="*100)
print(f"\n  {'회사':<10s}  " + "  ".join(f"{b:>9s}" for b in BUCKETS) + f"  {'미분류':>9s}  {'합계':>10s}")
print("─"*120)

results = []
for cik, name, sector in PEERS:
    members = find_maturity_members(cik)
    by_bucket = {b: 0 for b in BUCKETS + ["미분류"]}
    for member, ko in members:
        bucket = classify_maturity(member, ko)
        v = fetch_csm_by_maturity(cik, member)
        if v is not None:
            by_bucket[bucket] = by_bucket.get(bucket, 0) + v
    total = sum(by_bucket.values())
    results.append((cik, name, sector, by_bucket, total))

    def f(v): return f"{v/1e8:>7,.0f}억" if v else "       —"
    cells = [f(by_bucket[b]) for b in BUCKETS] + [f(by_bucket["미분류"])]
    print(f"  {name:<8s}  " + "  ".join(cells) + f"  {f(total)}")

print(f"\n  구성비 (%, 미분류 포함):")
print(f"  {'회사':<10s}  " + "  ".join(f"{b:>9s}" for b in BUCKETS))
print("─"*100)
for cik, name, sector, by_bucket, total in results:
    if total == 0:
        print(f"  {name:<8s}  (보고 없음)")
        continue
    pcts = [f"{by_bucket[b]/total*100:>7.1f}%" for b in BUCKETS]
    print(f"  {name:<8s}  " + "  ".join(pcts))
