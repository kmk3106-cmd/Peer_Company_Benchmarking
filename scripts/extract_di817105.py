"""DI817105 — 보험계약부채(자산) 잔액 추출 (8개사 × 별도·발행).

DI817100 이 변동표라면 DI817105 는 잔액표 (시점 분포).
주요 element: ThatAreAssets / ThatAreLiabilities / IssuedThatAreLiabilities 등.

각 회사에 대해:
- ComponentsAxis (BEL/RA/CSM) 분해 잔액 (이미 BEL/RA/CSM compare 에서 완료)
- LRC/LIC × TypesOfContractsAxis 분해 잔액 (신규)
- 자산 측 잔액 (음수 → 부채 측 차감)
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    fetch_balance_separate_issued,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER, HELD_MEMBER,
    TYPES_AXIS, LRC_LIC_AXIS, COMPONENTS_AXIS,
    LRC_EXCL, LC, LIC,
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

ROLE_105 = "dart_2024-06-30_role-DI817105"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def list_elements_in_role(cik: str, role: str) -> list[tuple]:
    """role 에 보고된 element + ko_label 목록."""
    return con.execute(f"""
      SELECT DISTINCT v.ELEMENT_ID,
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
             COUNT(*) AS n
      FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      GROUP BY v.ELEMENT_ID
      ORDER BY n DESC
    """, [cik, role]).fetchall()


def fetch_balance(cik: str, period: str, by_lrclic: str = None, by_types: str = None,
                  by_components: str = None) -> float | None:
    """별도·발행 잔액 — ThatAreAssets + ThatAreLiabilities 부호합.

    여러 axis 멤버 조합 옵션 지원.
    """
    total = None
    for elem in (
        "ifrs-full_InsuranceContractsIssuedThatAreLiabilities",
        "ifrs-full_InsuranceContractsIssuedThatAreAssets",
        "ifrs-full_InsuranceContractsThatAreLiabilities",
        "ifrs-full_InsuranceContractsThatAreAssets",
    ):
        req = {CONS_AXIS: SEP_MEMBER}
        if "Issued" not in elem:  # non-Issued element 는 DisaggAxis=Issued 필요
            req[DISAGG_AXIS] = ISSUED_MEMBER
        if by_lrclic: req[LRC_LIC_AXIS] = by_lrclic
        if by_types: req[TYPES_AXIS] = by_types
        if by_components: req[COMPONENTS_AXIS] = by_components

        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=elem,
            required_members=req,
            period_instant=period,
        ))
        if v is not None:
            total = (total or 0) + v
    return total


# ─── 1) 회사별 role 보고 element 개요 ───
print("="*90)
print("STEP 1: DI817105 회사별 보고 element 개수")
print("="*90)
for cik, name, sector in PEERS:
    elems = list_elements_in_role(cik, ROLE_105)
    print(f"\n  ── {name} ({sector}) ── {len(elems)}개 element 보고")
    for eid, ko, n in elems[:6]:
        eshort = eid.replace("ifrs-full_", "").replace("dart_", "d:").replace("entity00112332_", "#")[:55]
        print(f"    [{n:>5d}] {eshort:<57s} ← {ko or '(no label)'}")

# ─── 2) 기말 잔액 — LRC/LIC × 상품군 mini-cube ───
print("\n\n" + "="*90)
print("STEP 2: 기말 잔액 LRC 합산 (LRC excl + LC) vs LIC — 8개사")
print("="*90)
print(f"\n{'회사':<14s}  {'LRC':>14s}  {'LIC':>14s}  {'합계':>14s}  {'BS 참고':>14s}  정확도")
print("─"*90)

# 표준 5상품군 + 합계
PRODUCT_5 = {
    "사망": "dart_LifeInsuranceMember",
    "건강": "dart_HealthInsuranceMember",
    "연금": "entity00112332_PensionInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember",
    "저축": "entity00112332_SavingsInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember",
    "기타": "dart_OtherInsuranceMember",
}

BS_REF = {  # 단위 조원
    "00112332": 27.0, "00126256": 200.0, "00113058": 100.0, "00117267": 28.0,
    "00139214": 49.0, "00164973": 35.0, "00159102": 50.0, "00135917": 25.0,
}

results_lrc_lic = []
for cik, name, sector in PEERS:
    # 합계: 상품군 필터 없이 LRC/LIC 별
    lrc_excl = fetch_balance(cik, "2025-12-31", by_lrclic=LRC_EXCL)
    lc = fetch_balance(cik, "2025-12-31", by_lrclic=LC)
    lic = fetch_balance(cik, "2025-12-31", by_lrclic=LIC)
    lrc = (lrc_excl or 0) + (lc or 0) if (lrc_excl or lc) else None
    total = (lrc or 0) + (lic or 0) if (lrc or lic) else None

    bs = BS_REF[cik]
    acc = (total / 1e12 / bs * 100) if total else 0

    def fmt(v):
        return f"{v/1e8:>9,.0f}억" if v else "       —"

    print(f"  {name:<12s}  {fmt(lrc)}  {fmt(lic)}  {fmt(total)}  {bs:>8.0f}조      {acc:>5.0f}%")
    results_lrc_lic.append((cik, name, sector, lrc, lic, total, bs, acc))

# ─── 3) 미래에셋 5상품군 LRC/LIC 분해 (검증된 표준) ───
print("\n\n" + "="*90)
print("STEP 3: 미래에셋 5상품군 × LRC/LIC 분해 (DI817105 기말잔액)")
print("="*90)
print(f"\n{'상품군':<8s}  {'LRC':>14s}  {'LIC':>14s}  {'소계':>14s}")
print("─"*70)
mirae_total_lrc = mirae_total_lic = 0
for group, member in PRODUCT_5.items():
    lrc_excl = fetch_balance("00112332", "2025-12-31", by_lrclic=LRC_EXCL, by_types=member)
    lc = fetch_balance("00112332", "2025-12-31", by_lrclic=LC, by_types=member)
    lic = fetch_balance("00112332", "2025-12-31", by_lrclic=LIC, by_types=member)
    lrc = (lrc_excl or 0) + (lc or 0)
    sub = lrc + (lic or 0)
    mirae_total_lrc += lrc
    mirae_total_lic += (lic or 0)
    def fmt(v):
        return f"{v/1e8:>9,.0f}억" if v else "       —"
    print(f"  {group:<6s}  {fmt(lrc)}  {fmt(lic)}  {fmt(sub)}")
print("─"*70)
print(f"  {'합계':<6s}  {fmt(mirae_total_lrc)}  {fmt(mirae_total_lic)}  {fmt(mirae_total_lrc + mirae_total_lic)}")
print(f"\n  → 미래에셋 BS 기말 보험계약부채: 270,000억 (27.00조)")
print(f"  → DI817105 5상품군 LRC+LIC 합: {(mirae_total_lrc+mirae_total_lic)/1e8:,.0f}억 ({(mirae_total_lrc+mirae_total_lic)/1e12*100/27:.1f}%)")
