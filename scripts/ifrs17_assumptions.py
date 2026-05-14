"""IFRS17 가정적용 사항 — 회계측정모형 / CSM transition / PL vs OCI 분포.

1) 측정모형 (DisaggregationOfInsuranceContractsAxis 또는 InsuranceContractsAxis):
   - PAA (보험료배분접근법, 1년 미만 단기, 손보 주력)
   - GMM (일반모형, 보장성 위주, 생보 주력)
   - VFA (변동수수료접근법, 변액보험 직접참여계약, 생보)

2) CSM Transition approach:
   - ModifiedRetrospective (수정소급법)
   - FairValue (공정가치법)
   - NotRelatedToTransition (Full Retrospective + 신계약)

3) 보험금융손익 PL vs OCI 비중 — 회계정책 선택
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, fetch_components_total,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
    COMPONENTS_AXIS, COMP_CSM_ALL,
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

# 측정모형 axis 멤버
# IFRS17 표준: PAA 사용 vs 미사용
PAA_MEMBER = "ifrs-full_InsuranceContractsToWhichPremiumAllocationApproachHasBeenAppliedMember"
NONPAA_MEMBER = "ifrs-full_InsuranceContractsOtherThanThoseToWhichPremiumAllocationApproachHasBeenAppliedMember"

# entity GMM / VFA 패턴 (회사별 다름)
GMM_PATTERN = "%GeneralModel%"
VFA_PATTERN = "%VariableFeeApproach%"

INSURANCE_CONTRACTS_AXIS = "ifrs-full_InsuranceContractsAxis"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def fetch_with_axis_member(cik: str, period: str, axis: str, member: str) -> float | None:
    """잔액 (Assets+Liab 부호합) — 특정 axis-member 조합."""
    total = None
    for elem in (
        "ifrs-full_InsuranceContractsIssuedThatAreLiabilities",
        "ifrs-full_InsuranceContractsIssuedThatAreAssets",
        "ifrs-full_InsuranceContractsThatAreLiabilities",
        "ifrs-full_InsuranceContractsThatAreAssets",
    ):
        req = {CONS_AXIS: SEP_MEMBER, axis: member}
        if "Issued" not in elem:
            req[DISAGG_AXIS] = ISSUED_MEMBER
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=elem,
            required_members=req, period_instant=period,
        ))
        if v is not None:
            total = (total or 0) + v
    return total


def find_member_by_pattern(cik: str, axis: str, pattern: str) -> list[str]:
    """엔티티 확장 멤버 찾기."""
    return [r[0] for r in con.execute(f"""
      SELECT DISTINCT cx.MEMBER_ELEMENT_ID
      FROM cntxt_insurers cx
      WHERE cx.CIK=? AND cx.AXIS_ELEMENT_ID=?
        AND cx.MEMBER_ELEMENT_ID LIKE ?
    """, [cik, axis, pattern]).fetchall()]


# ─── 1) 측정모형 잔액 분포 ───
print("="*100)
print("§ A. IFRS17 측정모형 잔액 분포 (FY2025 기말)")
print("="*100)

# 각 회사: PAA / Non-PAA / GMM (entity) / VFA (entity)
print(f"\n  {'회사':<10s}  {'PAA':>11s}  {'Non-PAA':>11s}  {'GMM (entity)':>14s}  {'VFA (entity)':>14s}  비고")
print("─"*100)

ifrs17_results = []
for cik, name, sector in PEERS:
    paa = fetch_with_axis_member(cik, "2025-12-31", INSURANCE_CONTRACTS_AXIS, PAA_MEMBER) or \
          fetch_with_axis_member(cik, "2025-12-31", DISAGG_AXIS, PAA_MEMBER)
    nonpaa = fetch_with_axis_member(cik, "2025-12-31", INSURANCE_CONTRACTS_AXIS, NONPAA_MEMBER) or \
             fetch_with_axis_member(cik, "2025-12-31", DISAGG_AXIS, NONPAA_MEMBER)

    # GMM/VFA — entity 확장 멤버 (axis는 회사 따라 다름)
    gmm_members = find_member_by_pattern(cik, DISAGG_AXIS, GMM_PATTERN) + find_member_by_pattern(cik, INSURANCE_CONTRACTS_AXIS, GMM_PATTERN)
    vfa_members = find_member_by_pattern(cik, DISAGG_AXIS, VFA_PATTERN) + find_member_by_pattern(cik, INSURANCE_CONTRACTS_AXIS, VFA_PATTERN)

    gmm = vfa = None
    for m in gmm_members[:1]:  # 가장 빈도 높은 멤버 하나만
        v = fetch_with_axis_member(cik, "2025-12-31", DISAGG_AXIS, m) or fetch_with_axis_member(cik, "2025-12-31", INSURANCE_CONTRACTS_AXIS, m)
        if v: gmm = v; break
    for m in vfa_members[:1]:
        v = fetch_with_axis_member(cik, "2025-12-31", DISAGG_AXIS, m) or fetch_with_axis_member(cik, "2025-12-31", INSURANCE_CONTRACTS_AXIS, m)
        if v: vfa = v; break

    def fmt(v): return f"{v/1e12:>8,.2f}조" if v else "        —"
    note = ""
    if sector == "non_life": note = "손보 — PAA 주력"
    elif sector == "life":
        if vfa and gmm: note = "생보 — GMM+VFA"
        elif gmm: note = "생보 — GMM 위주"
        else: note = "생보"
    print(f"  {name:<8s}  {fmt(paa)}  {fmt(nonpaa)}  {fmt(gmm)}  {fmt(vfa)}  {note}")
    ifrs17_results.append({"cik": cik, "name": name, "sector": sector,
                           "PAA": paa, "NonPAA": nonpaa, "GMM": gmm, "VFA": vfa})


# ─── 2) CSM Transition Approach ───
print("\n\n" + "="*100)
print("§ B. CSM Transition Approach 적용 비중 (FY2025 기말)")
print("="*100)

# COMP_CSM_ALL = standard + 3 transition members
TRANSITION_MEMBERS = {
    "Standard": "ifrs-full_ContractualServiceMarginMember",
    "ModifiedRetrospective": "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachHasBeenAppliedMember",
    "FairValue": "ifrs-full_ContractualServiceMarginRelatedToContractsThatExistedAtTransitionDateToWhichFairValueApproachHasBeenAppliedMember",
    "NotRelated (Full Retro + 신계약)": "ifrs-full_ContractualServiceMarginNotRelatedToContractsThatExistedAtTransitionDateToWhichModifiedRetrospectiveApproachOrFairValueApproachHasBeenAppliedMember",
}

print(f"\n  {'회사':<10s}  " + "  ".join(f"{k:>22s}" for k in TRANSITION_MEMBERS))
print("─"*120)
for cik, name, sector in PEERS:
    cells = []
    for label, member in TRANSITION_MEMBERS.items():
        v = fetch_components_total(con, cik, "20251231", member, "2025-12-31")
        cells.append(f"{v/1e8:>18,.0f}억" if v else "                 —")
    print(f"  {name:<8s}  " + "  ".join(cells))

# 구성비 (Modified/FairValue/NotRelated만, Standard 제외)
print(f"\n  Transition member 구성비 (Modified + FairValue + NotRelated = 100%):")
print(f"  {'회사':<10s}  {'Modified':>11s}  {'FairValue':>11s}  {'NotRelated':>11s}")
print("─"*60)
for cik, name, sector in PEERS:
    mod = fetch_components_total(con, cik, "20251231", TRANSITION_MEMBERS["ModifiedRetrospective"], "2025-12-31") or 0
    fv = fetch_components_total(con, cik, "20251231", TRANSITION_MEMBERS["FairValue"], "2025-12-31") or 0
    nr = fetch_components_total(con, cik, "20251231", TRANSITION_MEMBERS["NotRelated (Full Retro + 신계약)"], "2025-12-31") or 0
    tot = mod + fv + nr
    if tot > 0:
        print(f"  {name:<8s}  {mod/tot*100:>9.1f}%  {fv/tot*100:>9.1f}%  {nr/tot*100:>9.1f}%")
    else:
        print(f"  {name:<8s}  (transition member 미사용 — standard CSMMember 만 사용)")


# ─── 3) 보험금융손익 PL vs OCI 비중 ───
print("\n\n" + "="*100)
print("§ C. 보험금융손익 PL vs OCI 회계정책 (FY2025 duration)")
print("="*100)

# PL element
PL_PATTERN = "%InsuranceFinanceIncomeExpensesFromInsuranceContractsIssued%RecognisedInProfitOrLoss%"
OCI_PATTERN_1 = "%InsuranceFinanceIncomeExpenses%RecognisedInOther%"
OCI_PATTERN_2 = "%OtherComprehensiveIncomeBeforeTaxInsuranceFinanceIncomeExpense%"

print(f"\n  {'회사':<10s}  {'PL 인식':>14s}  {'OCI 인식':>14s}  {'합계':>14s}  {'PL 비중':>9s}  회계정책")
print("─"*100)
for cik, name, sector in PEERS:
    # PL
    pl_eids = [r[0] for r in con.execute("""
      SELECT DISTINCT v.ELEMENT_ID FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817100' AND v.amount_krw IS NOT NULL
        AND v.ELEMENT_ID LIKE ?
    """, [cik, PL_PATTERN]).fetchall()]
    pl_total = 0
    for eid in pl_eids:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v is not None: pl_total += v
    pl_total = pl_total if pl_total else None

    # OCI
    oci_eids = [r[0] for r in con.execute(f"""
      SELECT DISTINCT v.ELEMENT_ID FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817100' AND v.amount_krw IS NOT NULL
        AND (v.ELEMENT_ID LIKE '{OCI_PATTERN_1}' OR v.ELEMENT_ID LIKE '{OCI_PATTERN_2}')
    """, [cik]).fetchall()]
    oci_total = 0
    for eid in oci_eids:
        v = fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
        if v is not None: oci_total += v
    oci_total = oci_total if oci_total else None

    total_abs = abs(pl_total or 0) + abs(oci_total or 0)
    pl_pct = (abs(pl_total or 0) / total_abs * 100) if total_abs > 0 else None
    policy = ""
    if pl_pct is not None:
        if pl_pct > 80: policy = "PL only (OCI 비선택)"
        elif pl_pct > 50: policy = "PL 위주"
        elif pl_pct > 20: policy = "PL+OCI 혼합"
        else: policy = "OCI 위주"

    def fmt(v): return f"{v/1e8:>10,.0f}억" if v else "         —"
    pct_s = f"{pl_pct:>7.1f}%" if pl_pct is not None else "       —"
    print(f"  {name:<8s}  {fmt(pl_total)}  {fmt(oci_total)}  {fmt(pl_total or 0 + (oci_total or 0))}  {pct_s}  {policy}")
