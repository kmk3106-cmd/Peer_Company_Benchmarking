"""DI817300 — 보험계약 정보 (CSM 만기분석) 추출.

내용:
- 미래 CSM 인식 기대액 (만기별 — 1년 이하, 1-2년, 2-3년, ..., 30년 초과)
- 신계약 효과 (initial recognition)
- 손실부담계약 정보 (onerous contracts)

핵심 metric:
- CSM 잔존 기간 분포 (장기 vs 단기)
- 신계약 CSM 기여
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER, COMPONENTS_AXIS,
)

PEERS = [
    ("00112332", "미래에셋생명", "생보"),
    ("00126256", "삼성생명",   "생보"),
    ("00113058", "한화생명",   "생보"),
    ("00117267", "동양생명",   "생보"),
    ("00139214", "삼성화재",   "손보"),
    ("00164973", "현대해상",   "손보"),
    ("00159102", "DB손해보험", "손보"),
    ("00135917", "한화손해보험","손보"),
]
ROLE = "dart_2024-06-30_role-DI817300"

MATURITY_AXIS = "ifrs-full_MaturityAxis"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


# Step 1: 각 회사 DI817300 element 개요
print("="*100)
print("STEP 1: DI817300 회사별 보고 element TOP 5")
print("="*100)
for cik, name, sector in PEERS:
    rows = con.execute("""
      SELECT v.ELEMENT_ID,
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
             COUNT(*) AS n
      FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 5
    """, [cik, ROLE]).fetchall()
    print(f"\n  ── {name} ({sector}) ──")
    for eid, ko, n in rows:
        eshort = eid.replace("ifrs-full_", "").replace("dart_", "d:").replace(f"entity{cik}_", "#")[:55]
        print(f"    [{n:>5d}] {eshort:<57s} ← {ko or '(no label)'}")


# Step 2: Maturity axis 멤버 dump (회사별)
print("\n\n" + "="*100)
print("STEP 2: Maturity Axis 멤버 분포 (CSM 만기분석 시간 구간)")
print("="*100)
for cik, name, sector in PEERS:
    rows = con.execute(f"""
      SELECT DISTINCT cx.MEMBER_ELEMENT_ID,
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
             COUNT(*) AS n
      FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      JOIN cntxt_insurers cx ON cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=cx.MEMBER_ELEMENT_ID AND l.LANG='ko'
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
        AND cx.AXIS_ELEMENT_ID=?
      GROUP BY cx.MEMBER_ELEMENT_ID ORDER BY n DESC
    """, [cik, ROLE, MATURITY_AXIS]).fetchall()
    if not rows:
        print(f"\n  {name}: Maturity axis 미보고")
        continue
    print(f"\n  ── {name} ── {len(rows)} 구간")
    for m, ko, n in rows[:8]:
        mshort = m.replace("ifrs-full_", "").replace("Member", "").replace(f"entity{cik}_", "#")[:55]
        print(f"    [{n:>4d}] {mshort:<57s} ← {ko}")


# Step 3: CSM 만기분석 (미래에셋 + 표준 멤버 시도)
print("\n\n" + "="*100)
print("STEP 3: CSM 만기별 분포 — 미래에셋 (FY2025 기말)")
print("="*100)

# 미래에셋의 만기 멤버 (entity 확장 — IDeath Table 멤버 셋)
MIRAE_MATURITY = [
    ("entity00112332_Within10YearsOfAggregatedTimeBandsMemberOfOne63ExpectedRevenueRecognitionAmountByPeriodOfContractualServiceMarginTableOfMember", "10년 이내"),
    ("ifrs-full_LaterThanTenYearsAndNotLaterThanFifteenYearsMember", "10-15년"),
    ("ifrs-full_LaterThanFifteenYearsAndNotLaterThanTwentyYearsMember", "15-20년"),
    ("ifrs-full_LaterThanTwentyYearsAndNotLaterThanTwentyfiveYearsMember", "20-25년"),
    ("entity00112332_Over25YearsButWithin30YearsOfAggregatedTimeBandsMemberOfOne63ExpectedRevenueRecognitionAmountByPeriodOfContractualServiceMarginTableOfMember", "25-30년"),
    ("entity00112332_Over30YearsOfAggregatedTimeBandsMemberOfOne63ExpectedRevenueRecognitionAmountByPeriodOfContractualServiceMarginTableOfMember", "30년 초과"),
]

# 미래에셋 CSM 만기별 인식 기대액 element 찾기
csm_revenue_elem = "ifrs-full_InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices"

print(f"\n  {'만기 구간':<14s}  {'CSM 인식 기대액':>16s}")
print("─" * 50)
total = 0
for member, label in MIRAE_MATURITY:
    v = fetch_fact_sum(con, FactQuery(
        cik="00112332", report_date="20251231",
        element_id=csm_revenue_elem,
        required_members={
            CONS_AXIS: SEP_MEMBER,
            DISAGG_AXIS: ISSUED_MEMBER,
            MATURITY_AXIS: member,
        },
        period_range=("2025-01-01", "2025-12-31"),
    ))
    if v is not None:
        print(f"  {label:<12s}  {v/1e8:>10,.0f}억")
        total += v
print("─" * 50)
print(f"  {'합계':<12s}  {total/1e8:>10,.0f}억")
