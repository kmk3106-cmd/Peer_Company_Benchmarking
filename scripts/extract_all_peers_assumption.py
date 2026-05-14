"""8개사 가정 변경 element 정확 추출 — 회사별 element 명세 정확 매칭."""
from __future__ import annotations
import json
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
    COMPONENTS_AXIS, COMP_BEL, COMP_RA, COMP_CSM_ALL,
)

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 회사별 정확 element 매핑 (search 결과 기반, 유추 없음)
COMPANY_ELEMENTS = {
    "00112332": {  # 미래에셋 — Table 자식 트리에서 추출 (기존)
        "name": "미래에셋",
        "lines": [
            ("해지율 가정변경", "entity00112332_ChangeInCancellationRateAssumptionOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
            ("위험율 가정변경", "entity00112332_ChangeInRiskRateAssumptionOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
            ("예정율 가정변경", "entity00112332_ChangeInProjectRatioAssumptionOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
            ("기타 가정변경", "entity00112332_OtherAssumptionChangesOfEffectOfChangingAssumptionsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
            ("(추가) 손실요소 변동", "entity00112332_FluctuationsDueToLossFactorsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
            ("(추가) 보유물량·투자요소", "entity00112332_FluctuationsDueToVolumeDifferencesAndDifferencesInInvestmentFactorsExpectedToBeRecognizedAsCsmAdjustmentsOfChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems"),
        ],
    },
    "00126256": {  # 삼성생명 — 1개 element만
        "name": "삼성생명",
        "lines": [
            ("가정변경 효과 (단일)", "entity00126256_EffectOfChangeInEstimateOfIncreaseDecreaseThroughChangesInEstimatesThatAdjustContractualServiceMarginInsuranceContractsLiabilityAssetOfDisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByComponentsOfInsuranceContractsTableOfItems"),
        ],
    },
    "00113058": {  # 한화생명 — 5개 분해
        "name": "한화생명",
        "lines": [
            ("해지율 가정변경", "entity00113058_IncreaseDecreaseThroughEffectsOfChangesInSurrenderRatesInsuranceContractsLiabilityAsset"),
            ("위험률 가정변경", "entity00113058_IncreaseDecreaseThroughEffectsOfChangesInRiskRatesInsuranceContractsLiabilityAsset"),
            ("사업비율 가정변경", "entity00113058_IncreaseDecreaseThroughEffectsOfChangesInExpenseRatioInsuranceContractsLiabilityAsset"),
            ("기타 가정변경", "entity00113058_IncreaseDecreaseThroughEffectsOfChangesInOtherAssumptionInsuranceContractsLiabilityAsset"),
            ("가정변경 총합", "entity00113058_IncreaseDecreaseThroughEffectsOfChangesInAssumptionsInsuranceContractsLiabilityAsset"),
        ],
    },
    "00117267": {  # 동양생명 — 추정변경만
        "name": "동양생명",
        "lines": [
            ("(가정 분해 미공시 — 추정변경 통합)", None),
        ],
    },
    "00139214": {  # 삼성화재 — 미공시
        "name": "삼성화재",
        "lines": [],
    },
    "00164973": {  # 현대해상 — 5개 분해
        "name": "현대해상",
        "lines": [
            ("해지율 가정변경", "entity00164973_IncreaseDecreaseThroughEffectsOfChangesOfSurrenderRatioAssumptionInsuranceContractsLiabilityAsset"),
            ("위험률 가정변경", "entity00164973_IncreaseDecreaseThroughEffectsOfChangesOfRiskRatioAssumptionInsuranceContractsLiabilityAsset"),
            ("사업비율 가정변경", "entity00164973_IncreaseDecreaseThroughEffectsOfChangesOfOperatingExpenseRateAssumptionInsuranceContractsLiabilityAsset"),
            ("기타 가정변경", "entity00164973_IncreaseDecreaseThroughEffectsOfChangesOfOtherAssumptionInsuranceContractsLiabilityAsset"),
            ("가정변경 총합", "entity00164973_IncreaseDecreaseThroughEffectsOfChangesOfActuarialAssumptionInsuranceContractsLiabilityAsset"),
        ],
    },
    "00159102": {  # DB손보 — 5개 분해 (현대와 동일 패턴)
        "name": "DB손보",
        "lines": [
            ("해지율 가정변경", "entity00159102_IncreaseDecreaseThroughEffectsOfChangesOfSurrenderRatioAssumptionInsuranceContractsLiabilityAsset"),
            ("위험률 가정변경", "entity00159102_IncreaseDecreaseThroughEffectsOfChangesOfRiskRatioAssumptionInsuranceContractsLiabilityAsset"),
            ("사업비율 가정변경", "entity00159102_IncreaseDecreaseThroughEffectsOfChangesOfOperatingExpenseRateAssumptionInsuranceContractsLiabilityAsset"),
            ("기타 가정변경", "entity00159102_IncreaseDecreaseThroughEffectsOfChangesOfOtherAssumptionInsuranceContractsLiabilityAsset"),
            ("가정변경 총합", "entity00159102_IncreaseDecreaseThroughEffectsOfChangesOfActuarialAssumptionInsuranceContractsLiabilityAsset"),
        ],
    },
    "00135917": {  # 한화손보 — CSM 조정하는 4개 가정
        "name": "한화손보",
        "lines": [
            ("해지율 가정변경 (CSM 조정)", "entity00135917_IncreaseDecreaseThroughChangesInSurrenderRatioAssumptionsThatAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
            ("위험률 가정변경 (CSM 조정)", "entity00135917_IncreaseDecreaseThroughChangesInRiskRatioAssumptionsThatAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
            ("사업비율 가정변경 (CSM 조정)", "entity00135917_IncreaseDecreaseThroughChangesInOperatingExpenseRatioAssumptionsThatAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
            ("기타 가정변경 (CSM 조정)", "entity00135917_IncreaseDecreaseThroughChangesInOtherAssumptionsThatAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
            ("가정변경 총합 (CSM 조정)", "entity00135917_IncreaseDecreaseThroughChangesInAssumptionsThatAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
        ],
    },
}


def resolve_element(cik: str, eid_full: str) -> str | None:
    """element id 가 존재하는지 확인 + 정확한 full id 반환."""
    r = con.execute("""
      SELECT v.ELEMENT_ID FROM val_insurers v
      WHERE v.CIK=? AND v.ELEMENT_ID LIKE ?
      LIMIT 1
    """, [cik, eid_full[:100] + "%"]).fetchone()
    return r[0] if r else None


def fetch_by_components(cik: str, eid: str):
    """BEL / RA / CSM(전체) + 합계 추출."""
    def f(comp):
        return fetch_fact_sum(con, FactQuery(
            cik=cik, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER, COMPONENTS_AXIS: comp},
            period_range=("2025-01-01", "2025-12-31"),
        ))
    bel = f(COMP_BEL)
    ra = f(COMP_RA)
    csm = 0; csm_found = False
    for m in COMP_CSM_ALL:
        v = f(m)
        if v is not None:
            csm += v; csm_found = True
    csm = csm if csm_found else None
    # axis 없는 합계
    total_no_ax = fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231", element_id=eid,
        required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
        forbidden_axes=(COMPONENTS_AXIS,),
        period_range=("2025-01-01", "2025-12-31"),
    ))
    return bel, ra, csm, total_no_ax


# 실행
all_data = {}
for cik, info in COMPANY_ELEMENTS.items():
    print(f"\n{'='*100}")
    print(f"  {info['name']} ({cik})")
    print(f"{'='*100}")
    if not info["lines"]:
        print(f"  ❌ 가정 변경 element 미공시")
        all_data[cik] = {"name": info["name"], "lines": [], "status": "not_disclosed"}
        continue

    print(f"\n  {'라인':<28s}  {'BEL':>11s}  {'RA':>11s}  {'CSM':>11s}  {'총합':>11s}")
    print("  " + "─"*92)
    company_lines = []
    for label, eid in info["lines"]:
        if eid is None:
            print(f"  {label:<28s}  (미공시)")
            company_lines.append({"label": label, "eid": None, "BEL": None, "RA": None, "CSM": None, "total": None})
            continue
        # 존재 확인
        actual_eid = resolve_element(cik, eid[:100])
        if not actual_eid:
            # full id로 직접 시도
            actual_eid = eid
        bel, ra, csm, total = fetch_by_components(cik, eid)
        # 만약 컴포넌트 axis로 다 0이면, axis 없이 시도
        if not any(v is not None and abs(v) > 1e7 for v in (bel, ra, csm)):
            # fact 자체가 BEL/RA/CSM 분해 없을 수 있음
            v_simple = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=eid,
                required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
                period_range=("2025-01-01", "2025-12-31"),
            ))
            total = v_simple if v_simple else total

        def f(v): return f"{v/1e8:>+8,.0f}억" if v is not None else "         —"
        print(f"  {label:<28s}  {f(bel)}  {f(ra)}  {f(csm)}  {f(total)}")
        company_lines.append({"label": label, "eid": eid, "BEL": bel, "RA": ra, "CSM": csm, "total": total})

    all_data[cik] = {"name": info["name"], "lines": company_lines, "status": "extracted"}

from pathlib import Path
Path("report/peer_assumption_changes_v2.json").write_text(
    json.dumps(all_data, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print(f"\n\nwrote report/peer_assumption_changes_v2.json")
