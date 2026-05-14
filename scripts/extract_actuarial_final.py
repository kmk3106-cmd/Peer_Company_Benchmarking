"""계리적가정 표 최종 — BEL/RA/CSM axis 별로 값 추출.

표는 (가정변경 항목) × (BEL/RA/CSM) 매트릭스로 보고됨.
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
    COMPONENTS_AXIS, COMP_BEL, COMP_RA, COMP_CSM, COMP_CSM_ALL,
)

CIK = "00112332"
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 정확 line items (계리적가정 표 트리에서 발견)
LINES = [
    ("신계약에 기인한 미래서비스의 변동",
     "entity00112332_ChangesInFutureServicesDueToNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("신계약 외 미래서비스 변동 (합계)",
     "entity00112332_ChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("── 가정변경 효과 (소계)",
     "entity00112332_EffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("    해지율 가정변경",
     "entity00112332_ChangeInCancellationRateAssumptionOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("    위험율 가정변경",
     "entity00112332_ChangeInRiskRateAssumptionOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("    예정율 가정변경",
     "entity00112332_ChangeInProjectRatioAssumptionOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("    기타 가정변경",
     "entity00112332_OtherAssumptionChangesOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("── 보유물량·투자요소 차이",
     "entity00112332_FluctuationsDueToVolumeDifferencesAndDifferencesInInvestmentFactorsExpectedToBeRecognizedAsCsmAdjustmentsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
    ("── 손실요소에 의한 변동",
     "entity00112332_FluctuationsDueToLossFactorsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
]

# 실제 element_id 가 다를 수 있으니 LIKE 검색으로 식별
LINE_PATTERNS = [
    ("신계약에 기인한 미래서비스의 변동", "%ChangesInFutureServicesDueToNewContracts%"),
    ("신계약 외 미래서비스 변동 (합계)", "%ChangesInFutureServicesAttributableToFactorsOtherThanNewContracts%"),
    ("── 가정변경 효과 (소계)", "%EffectOfChangingAssumptionsOfChangesInFutureServicesAttributable%"),
    ("    해지율 가정변경", "%ChangeInCancellationRateAssumption%"),
    ("    위험율 가정변경", "%ChangeInRiskRateAssumption%"),
    ("    예정율 가정변경", "%ChangeInProjectRatioAssumption%"),
    ("    기타 가정변경", "%OtherAssumptionChangesOfEffectOfChangingAssumptions%"),
    ("── 보유물량·투자요소 차이", "%FluctuationsDueToVolumeDifferencesAndDifferencesInInvestmentFactors%"),
    ("── 손실요소에 의한 변동", "%FluctuationsDueToLossFactors%ChangesInFutureServices%"),
]


def resolve(pattern: str) -> str | None:
    r = con.execute("""
      SELECT v.ELEMENT_ID FROM val_insurers v
      WHERE v.CIK=? AND v.amount_krw IS NOT NULL AND v.ELEMENT_ID LIKE ?
        AND v.ELEMENT_ID LIKE 'entity00112332_%'
        AND v.ELEMENT_ID LIKE '%ChangesInInsuranceLiabilities%'
      GROUP BY v.ELEMENT_ID
      ORDER BY COUNT(*) DESC LIMIT 1
    """, [CIK, pattern]).fetchone()
    return r[0] if r else None


# BEL/RA/CSM 별로 값 추출
print("="*120)
print("【미래에셋 (entity00112332) 계리적가정에 의한 보험부채 변동내역】")
print("="*120)
print(f"\n  ※ 정확한 entity element만 사용. 추정·유추 없음.")
print(f"  ※ ComponentsAxis = BEL / RA / CSM (CSM은 standard + transition 3변형 합산)")
print(f"  ※ 기준: 별도(Separate) + 발행(Issued) + duration 2025\n")

print(f"  {'가정 변경 항목':<30s}  {'BEL':>12s}  {'RA':>12s}  {'CSM':>12s}  {'합계':>12s}")
print("─"*100)


def fetch_by_component(eid, comp_member):
    return fetch_fact_sum(con, FactQuery(
        cik=CIK, report_date="20251231", element_id=eid,
        required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER, COMPONENTS_AXIS: comp_member},
        period_range=("2025-01-01", "2025-12-31"),
    ))


def fetch_csm_all(eid):
    total = 0; found = False
    for m in COMP_CSM_ALL:
        v = fetch_by_component(eid, m)
        if v is not None:
            total += v; found = True
    return total if found else None


for label, pattern in LINE_PATTERNS:
    eid = resolve(pattern)
    if not eid:
        print(f"  {label:<30s}  ELEMENT NOT FOUND ({pattern[:50]})")
        continue
    bel = fetch_by_component(eid, COMP_BEL)
    ra = fetch_by_component(eid, COMP_RA)
    csm = fetch_csm_all(eid)
    total = sum(v for v in (bel, ra, csm) if v is not None) if any((bel, ra, csm)) else None

    def f(v): return f"{v/1e8:>+9,.0f}억" if v is not None else "         —"
    print(f"  {label:<30s}  {f(bel)}  {f(ra)}  {f(csm)}  {f(total)}")
