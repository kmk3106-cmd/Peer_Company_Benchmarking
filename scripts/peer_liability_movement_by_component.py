"""8개사 보험계약부채 변동 — BEL/RA/CSM 컴포넌트별 분해 (회사 합계, 상품군 미분해).

각 회사 별도 FY2025 부채 변동 라인을 ByComponents axis (BEL/RA/CSM)로 나눠서 비교.
- 회사 합계만 표시 (자사 미래에셋의 상품군 분해는 본 비교에서 제외 — 회사간 정합 위해 합산).
- 자사 axes-tuple dedup 적용.

라인: 신계약 인식 / CSM 상각 / CSM조정 추정변동 / CSM미조정 추정변동 / 과거서비스변동 / 보험금융손익.
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb

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

LINES = [
    ("신계약 인식",        "ifrs-full_IncreaseDecreaseThroughEffectsOfContractsInitiallyRecognisedInPeriodInsuranceContractsLiabilityAsset"),
    ("CSM 상각(당기서비스)", "ifrs-full_IncreaseDecreaseThroughChangesThatRelateToCurrentServiceInsuranceContractsLiabilityAsset"),
    ("CSM조정 추정변동",   "ifrs-full_IncreaseDecreaseThroughChangesInEstimatesThatAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
    ("CSM미조정 추정변동", "ifrs-full_IncreaseDecreaseThroughChangesInEstimatesThatDoNotAdjustContractualServiceMarginInsuranceContractsLiabilityAsset"),
    ("과거서비스 변동",    "ifrs-full_IncreaseDecreaseThroughChangesThatRelateToPastServiceInsuranceContractsLiabilityAsset"),
    ("보험금융손익",       "ifrs-full_IncreaseDecreaseThroughInsuranceFinanceIncomeOrExpensesInsuranceContractsLiabilityAsset"),
]

COMPONENTS = [
    ("BEL", "ifrs-full_EstimatesOfPresentValueOfFutureCashFlowsMember"),
    ("RA",  "ifrs-full_RiskAdjustmentForNonfinancialRiskMember"),
    ("CSM", "ifrs-full_ContractualServiceMarginMember"),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def fetch_dedup(cik: str, eid: str, comp_member: str) -> float | None:
    q = """
    WITH v AS (SELECT * FROM val_norm WHERE CIK=? AND ELEMENT_ID=? AND amount_krw IS NOT NULL),
    sep AS (SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers WHERE CIK=? AND MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'),
    comp AS (SELECT DISTINCT CONTEXT_ID FROM cntxt_insurers WHERE CIK=? AND MEMBER_ELEMENT_ID=?),
    periods AS (SELECT CONTEXT_ID, ANY_VALUE(PERIOD_START_DATE) AS p FROM cntxt_insurers WHERE CIK=? GROUP BY 1),
    ax AS (SELECT CONTEXT_ID, STRING_AGG(MEMBER_ELEMENT_ID, '||' ORDER BY MEMBER_ELEMENT_ID) AS axes FROM cntxt_insurers WHERE CIK=? GROUP BY 1)
    SELECT SUM(amt) FROM (
      SELECT ax.axes, ANY_VALUE(v.amount_krw) AS amt
      FROM v JOIN sep USING (CONTEXT_ID) JOIN comp USING (CONTEXT_ID)
      JOIN periods p USING (CONTEXT_ID) JOIN ax USING (CONTEXT_ID)
      WHERE p.p='2025-01-01'
      GROUP BY ax.axes
    )
    """
    r = con.execute(q, [cik, eid, cik, cik, comp_member, cik, cik]).fetchone()
    return r[0] if r and r[0] else None


results = {}
for cik, name in PEERS:
    results[cik] = {"name": name, "components": {}}
    for comp_label, comp_member in COMPONENTS:
        comp_data = {}
        for line_label, eid in LINES:
            v = fetch_dedup(cik, eid, comp_member)
            comp_data[line_label] = v
        results[cik]["components"][comp_label] = comp_data

# Print summary
for comp_label, _ in COMPONENTS:
    print(f"\n{'='*90}")
    print(f"{comp_label} (현금흐름 최선추정치)" if comp_label == "BEL"
          else f"{comp_label} (위험조정)" if comp_label == "RA"
          else f"{comp_label} (보험계약마진)")
    print(f"{'='*90}")
    header = f"  {'회사':<10s}  " + "  ".join(f"{lbl[:10]:>11s}" for lbl, _ in LINES)
    print(header)
    print("─" * len(header))
    for cik, name in PEERS:
        cells = []
        for lbl, _ in LINES:
            v = results[cik]["components"][comp_label][lbl]
            cells.append(f"{v/1e8:>+9,.0f}억" if v is not None else "          —")
        print(f"  {name:<8s}  " + "  ".join(cells))

Path("report/liability_movement_by_component.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v is not None else None),
    encoding="utf-8")
print("\nwrote report/liability_movement_by_component.json")
