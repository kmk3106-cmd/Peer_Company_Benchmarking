"""Step 2 v2: element_id 패턴 기반 매핑으로 재진단.

기존 라벨 매칭 → element_id LIKE 패턴 매칭으로 변경. 더 robust.
"""
from __future__ import annotations
import csv, json, re
from pathlib import Path
import duckdb

PEERS_8 = [
    ("00112332", "미래에셋생명", "life"),
    ("00126256", "삼성생명",   "life"),
    ("00113058", "한화생명",   "life"),
    ("00117267", "동양생명",   "life"),
    ("00139214", "삼성화재",   "non_life"),
    ("00164973", "현대해상",   "non_life"),
    ("00159102", "DB손해보험", "non_life"),
    ("00135917", "한화손해보험","non_life"),
]

ROLE = "dart_2024-06-30_role-DI817100"

# 표준 라인 → element_id 패턴 (LIKE) — 라벨 fallback 추가
STANDARD_LINES = [
    # (std_name, element patterns, label fallback patterns)
    ("기초잔액_자산",       ["%InsuranceContractsThatAreAssets%"], ["자산인 보험계약"]),
    ("기초잔액_부채",       ["%InsuranceContractsThatAreLiabilities%"], ["부채인 보험계약"]),
    ("보험수익",            ["ifrs-full_InsuranceRevenue"], ["보험수익"]),
    ("신계약인식",          ["%EffectsOfContractsInitiallyRecognised%"], ["처음 인식한 계약"]),
    ("CSM조정추정변동",     ["%ChangesInEstimatesThatAdjustContractualServiceMargin%"], ["보험계약마진을 조정하는 추정치"]),
    ("CSM미조정추정변동",   ["%ChangesInEstimatesThatDoNotAdjustContractualServiceMargin%"], ["보험계약마진을 조정하지 않는"]),
    ("위험조정변동",        ["%ChangeInRiskAdjustmentForNonfinancialRisk%"], ["위험조정 변동", "비금융위험"]),
    ("경험조정",            ["%ExperienceAdjustments%InsuranceContracts%"], ["경험조정"]),
    ("과거서비스변동",      ["%RelateToPastServiceInsuranceContracts%"], ["과거 서비스", "과거서비스"]),
    ("손실부담계약손실",    ["%EffectsOfGroupsOfOnerousContracts%"], ["손실부담계약"]),
    ("발생사고요소조정",    ["%OtherAdjustmentsOfLiabilitiesForIncurredClaims%", "%AdjustmentsToLiabilities%IncurredClaims%"], ["발생사고요소", "발생사고부채"]),
    ("발생사고비용",        ["%IncurredClaimsAndOtherIncurredInsuranceServiceExpenses%InsuranceContracts%"], ["발생한 보험금"]),
    ("수취보험료",          ["%PremiumsReceivedForInsuranceContractsIssued%"], ["수취한 보험료"]),
    ("지급보험금",          ["%IncurredClaimsPaidAndOtherInsuranceServiceExpensesPaid%InsuranceContracts%"], ["지급한 보험금"]),
    ("보험취득CF지급",      ["%InsuranceAcquisitionCashFlowsInsuranceContracts%", "%IncreaseDecreaseThroughInsuranceAcquisitionCashFlows%"], ["보험취득 현금흐름"]),
    ("보험취득CF상각",      ["%AmortisationOfInsuranceAcquisitionCashFlows%"], ["보험취득현금흐름의 상각", "취득현금흐름 상각"]),
    ("투자요소",            ["%InvestmentComponentsExcluded%"], ["투자요소"]),
    ("금융손익_PL",         ["%InsuranceFinanceIncomeExpensesFromInsuranceContractsIssued%RecognisedInProfitOrLoss%"], ["당기손익인식 보험금융손익", "당기손익으로 인식한"]),
    ("금융손익_OCI",        ["%InsuranceFinanceIncomeExpenses%RecognisedInOther%", "%OtherComprehensiveIncomeBeforeTaxInsuranceFinanceIncomeExpense%"], ["기타포괄손익", "세전기타포괄손익"]),
    ("기타증감",            ["%OtherChangesLiabilitiesUnderInsuranceContracts%", "%IncreaseDecreaseThroughOtherChanges%InsuranceContract%", "%AdditionalItemsNecessaryToUnderstand%"], ["기타증감", "기타 증감", "기타 변동"]),
]


def reported(con, cik, std_name, patterns, labels):
    pat_clause = " OR ".join("v.ELEMENT_ID LIKE ?" for _ in patterns)
    lab_clause = " OR ".join("l.LABEL LIKE ?" for _ in labels)
    sql = f"""
    SELECT COUNT(*) FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      AND (({pat_clause}) OR ({lab_clause}))
    """
    params = [cik, ROLE] + list(patterns) + [f"%{kw}%" for kw in labels]
    n = con.execute(sql, params).fetchone()[0]
    return n > 0


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

    # 라인 × 회사 매트릭스
    matrix = {std: {cik: False for cik, _, _ in PEERS_8} for std, _, _ in STANDARD_LINES}
    for cik, name, _ in PEERS_8:
        for std, pats, labs in STANDARD_LINES:
            matrix[std][cik] = reported(con, cik, std, pats, labs)

    # 콘솔 출력
    names = {cik: name for cik, name, _ in PEERS_8}
    life = ["00112332", "00126256", "00113058", "00117267"]
    nonlife = ["00139214", "00164973", "00159102", "00135917"]
    all_ciks = life + nonlife

    print(f"\n{'라인':<22s}  {'미래':>4s}{'삼성':>4s}{'한화':>4s}{'동양':>4s}  {'삼화':>4s}{'현대':>4s}{'DB':>4s}{'한손':>4s}  합계 (생/손)")
    print("─"*100)
    n_8of8 = n_75 = n_warn = n_review = 0
    line_results = []
    for std, _, _ in STANDARD_LINES:
        cells = []
        n_life = n_nonlife = 0
        for cik in all_ciks:
            v = matrix[std][cik]
            cells.append("✓" if v else "·")
            if v:
                if cik in life: n_life += 1
                else: n_nonlife += 1
        total = n_life + n_nonlife
        line_results.append({"line": std, "n_life": n_life, "n_nonlife": n_nonlife, "n_total": total})
        if total == 8: n_8of8 += 1
        if total >= 6: n_75 += 1
        elif total >= 3: n_warn += 1
        else: n_review += 1
        print(f"  {std:<20s}  {cells[0]:>4s}{cells[1]:>4s}{cells[2]:>4s}{cells[3]:>4s}  "
              f"{cells[4]:>4s}{cells[5]:>4s}{cells[6]:>4s}{cells[7]:>4s}   "
              f"{total:>2d}/8 ({n_life}/{n_nonlife})")

    total_lines = len(STANDARD_LINES)
    print(f"\n  ★ 8/8 전 회사: {n_8of8}/{total_lines}")
    print(f"  ★ 6/8 이상 (PASS): {n_75}/{total_lines} = {n_75/total_lines*100:.0f}%")
    print(f"  ★ 3~5/8 (WARNING): {n_warn}/{total_lines} = {n_warn/total_lines*100:.0f}%")
    print(f"  ★ 2/8 이하 (REVIEW): {n_review}/{total_lines} = {n_review/total_lines*100:.0f}%")

    # v1 비교
    print(f"\n  v1 매핑 (라벨만): PASS 8 / WARNING 8 / REVIEW 5")
    print(f"  v2 매핑 (element 우선): PASS {n_75} / WARNING {n_warn} / REVIEW {n_review}")

    # CSV 저장
    out = Path("report/line_crosstab_v2.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line"] + [names[c] for c in all_ciks] + ["n_life", "n_nonlife", "n_total"])
        for std, _, _ in STANDARD_LINES:
            row = [std] + ["Y" if matrix[std][c] else "N" for c in all_ciks]
            n_life = sum(1 for c in life if matrix[std][c])
            n_nonlife = sum(1 for c in nonlife if matrix[std][c])
            row += [n_life, n_nonlife, n_life + n_nonlife]
            w.writerow(row)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
