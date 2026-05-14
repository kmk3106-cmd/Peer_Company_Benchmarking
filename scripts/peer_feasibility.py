"""Step 2: 8개사 부채변동 비교 적합성 진단.

대상 회사 (Step 1 결과):
  생보 4: 미래에셋생명, 삼성생명, 한화생명, 동양생명
  손보 4: 삼성화재, 현대해상, DB손해보험, 한화손해보험

각 회사에 대해:
A) TypesOfContractsAxis 멤버 → 표준 5상품군(사망/건강/연금/저축/기타) 매핑
B) DI817100 표준 라인 (수취보험료·지급보험금·취득CF·금융손익 등) 보고 여부
C) BEL/RA/CSM components_axis 멤버 dump
D) 잔액 vs BS 부채총계 검증

출력:
  - report/feasibility_<cik>.json
  - report/feasibility_summary.csv
  - report/feasibility_report.html (step 4 에서 확장)
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
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
SEP = "ifrs-full_SeparateMember"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
COMP_AXIS = "ifrs-full_InsuranceContractsByComponentsAxis"
LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"

# 표준 5상품군 매핑 룰 (라벨 키워드)
PRODUCT_RULES = [
    # (priority, regex, standard_group)
    (10, r"(변액)?사망(?!.*외)|Death|Life(?!.*Insurance.*Other)", "사망"),
    (10, r"건강|Health|질병|암", "건강"),
    (10, r"(변액)?연금(?!.*저축)|Annuity|Pension(?!.*Saving)", "연금"),
    (10, r"(변액)?저축|Savings|Endowment|연금저축", "저축"),
    # generic mappers (lower priority)
    (5,  r"LifeInsuranceMember$", "사망"),
    (5,  r"HealthInsuranceMember$", "건강"),
    (5,  r"OtherInsuranceMember$|기타(보험)?$|일반$", "기타"),
    # 손보 long-term/general/auto
    (8,  r"장기|일반|자동차|Auto|General|LongTerm", "기타"),  # 손보는 5분류 매핑 약함
]

STANDARD_LINES = [
    # (label_keyword, std_name)
    ("기초 장부금액", "기초잔액"),
    ("자산인 보험계약", "기초잔액_자산"),
    ("부채인 보험계약", "기초잔액_부채"),
    ("보험수익", "보험수익"),
    ("처음 인식한 계약", "신계약인식"),
    ("보험계약마진을 조정하는 추정치", "CSM조정추정변동"),
    ("보험계약마진을 조정하지 않는", "CSM미조정추정변동"),
    ("위험조정 변동분", "위험조정변동"),
    ("경험조정", "경험조정"),
    ("과거서비스", "과거서비스변동"),
    ("손실부담계약", "손실부담계약손실"),
    ("발생사고요소의 조정", "발생사고요소조정"),
    ("발생한 보험금", "발생사고비용"),
    ("수취한 보험료", "수취보험료"),
    ("지급한 보험금", "지급보험금"),
    ("보험취득 현금흐름에 따른", "보험취득CF지급"),
    ("보험취득 현금흐름의 상각", "보험취득CF상각"),
    ("투자요소", "투자요소"),
    ("당기손익인식 보험금융손익", "금융손익_PL"),
    ("기타포괄손익인식 보험금융손익", "금융손익_OCI"),
    ("기타증감", "기타증감"),
]


def classify_product(ko_label: str, element_id: str) -> tuple[str, int]:
    """Return (standard_group, confidence) — confidence 10=HIGH, 5=MEDIUM, 0=미분류."""
    text = (ko_label or "") + " " + (element_id or "")
    best = ("미분류", 0)
    for priority, pattern, group in PRODUCT_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            if priority > best[1]:
                best = (group, priority)
    return best


def get_types_members(con, cik: str) -> list[dict]:
    """별도·발행 컨텍스트에서 사용된 TypesOfContractsAxis 멤버."""
    sql = f"""
    SELECT DISTINCT cx.MEMBER_ELEMENT_ID AS member,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko_label,
           COUNT(*) AS n_ctx
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    JOIN cntxt_insurers cx ON cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=cx.MEMBER_ELEMENT_ID AND l.LANG='ko'
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      AND cx.AXIS_ELEMENT_ID='{TYPES_AXIS}'
      AND EXISTS (SELECT 1 FROM cntxt_insurers cs
        WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
          AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
      AND EXISTS (SELECT 1 FROM cntxt_insurers cd
        WHERE cd.CIK=v.CIK AND cd.REPORT_DATE=v.REPORT_DATE AND cd.CONTEXT_ID=v.CONTEXT_ID
          AND cd.AXIS_ELEMENT_ID='{DISAGG_AXIS}' AND cd.MEMBER_ELEMENT_ID='{ISSUED}')
    GROUP BY cx.MEMBER_ELEMENT_ID
    ORDER BY n_ctx DESC
    """
    rows = con.execute(sql, [cik, ROLE]).fetchall()
    out = []
    for member, ko, n in rows:
        group, conf = classify_product(ko, member)
        out.append({
            "member": member,
            "ko_label": ko,
            "n_ctx": n,
            "std_group": group,
            "confidence": conf,
        })
    return out


def get_components_members(con, cik: str) -> list[dict]:
    """별도·발행 컨텍스트에서 사용된 ComponentsAxis 멤버 (BEL/RA/CSM)."""
    sql = f"""
    SELECT DISTINCT cx.MEMBER_ELEMENT_ID AS member,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko_label,
           COUNT(*) AS n
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    JOIN cntxt_insurers cx ON cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=cx.MEMBER_ELEMENT_ID AND l.LANG='ko'
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      AND cx.AXIS_ELEMENT_ID='{COMP_AXIS}'
      AND EXISTS (SELECT 1 FROM cntxt_insurers cs
        WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
          AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
    GROUP BY cx.MEMBER_ELEMENT_ID
    ORDER BY n DESC
    """
    rows = con.execute(sql, [cik, ROLE]).fetchall()
    out = []
    for member, ko, n in rows:
        std = None
        text = (ko or "") + " " + (member or "")
        if "EstimatesOfPresentValueOfFutureCashFlows" in member or "현금흐름의 현재가치" in (ko or "") or "BEL" in text:
            std = "BEL"
        elif "RiskAdjustment" in member or "위험조정" in (ko or "") or "RA" in text:
            std = "RA"
        elif "ContractualServiceMargin" in member or "보험계약마진" in (ko or "") or "CSM" in text:
            std = "CSM"
        out.append({"member": member, "ko_label": ko, "n": n, "std": std})
    return out


def get_standard_lines(con, cik: str) -> list[dict]:
    """DI817100 에서 보고된 element + ko_label 으로 표준 라인 매핑 여부."""
    sql = f"""
    SELECT DISTINCT v.ELEMENT_ID,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
           COUNT(*) AS n
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      AND EXISTS (SELECT 1 FROM cntxt_insurers cs
        WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
          AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
    GROUP BY v.ELEMENT_ID
    """
    rows = con.execute(sql, [cik, ROLE]).fetchall()

    # 표준 라인 매칭
    reported_lines = {std: False for _, std in STANDARD_LINES}
    sample_elements = {std: [] for _, std in STANDARD_LINES}
    for eid, ko, n in rows:
        if not ko:
            continue
        for keyword, std in STANDARD_LINES:
            if keyword in ko:
                reported_lines[std] = True
                sample_elements[std].append(eid)
                break
    return [
        {"line": std, "reported": reported_lines[std], "elements": sample_elements[std][:2]}
        for _, std in STANDARD_LINES
    ]


def check_balance_total(con, cik: str) -> dict:
    """기말 잔액 총합 검증 (BS 보험계약부채 비교용)."""
    sql = f"""
    SELECT SUM(v.amount_krw) / 1e8 AS sum_억
    FROM val_insurers v
    WHERE v.CIK=? AND v.amount_krw IS NOT NULL
      AND v.ELEMENT_ID = 'ifrs-full_InsuranceContractsIssuedThatAreLiabilities'
      AND EXISTS (SELECT 1 FROM cntxt_insurers cs
        WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
          AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
      AND EXISTS (SELECT 1 FROM cntxt_insurers p
        WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
          AND p.PERIOD_INSTANT='2025-12-31')
    """
    val = con.execute(sql, [cik]).fetchone()[0]
    return {"BS_liability_total_억": val}


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    out_path = Path("report")
    out_path.mkdir(parents=True, exist_ok=True)

    summary = []
    details = {}

    for cik, name, sector in PEERS_8:
        print(f"\n{'='*60}\n{name} ({cik}, {sector})\n{'='*60}")
        types = get_types_members(con, cik)
        comps = get_components_members(con, cik)
        lines = get_standard_lines(con, cik)
        bs = check_balance_total(con, cik)

        # 5상품군 멤버 분포
        group_dist = {"사망":0, "건강":0, "연금":0, "저축":0, "기타":0, "미분류":0}
        for t in types:
            group_dist[t["std_group"]] = group_dist.get(t["std_group"], 0) + 1

        # 표준 라인 보고 수
        n_lines_reported = sum(1 for L in lines if L["reported"])

        # BEL/RA/CSM 식별
        bel_rep = any(c["std"]=="BEL" for c in comps)
        ra_rep = any(c["std"]=="RA" for c in comps)
        csm_rep = any(c["std"]=="CSM" for c in comps)

        print(f"  TypesOfContracts 멤버: {len(types)}개")
        print(f"    표준 5상품군 분포: {group_dist}")
        print(f"  Components 멤버: BEL={bel_rep} RA={ra_rep} CSM={csm_rep}")
        print(f"  표준 라인 보고: {n_lines_reported}/{len(STANDARD_LINES)}")
        print(f"  BS 발행보험부채(기말, 별도): {bs['BS_liability_total_억']:,.0f}억" if bs['BS_liability_total_억'] else "  BS 잔액 없음")

        # 라인별 ✓ 표시
        print(f"  ─── 표준 라인 보고 여부 ───")
        for L in lines:
            mark = "✓" if L["reported"] else "·"
            print(f"    [{mark}] {L['line']}")

        details[cik] = {
            "company": name,
            "sector": sector,
            "types_members": types,
            "components_members": comps,
            "standard_lines": lines,
            "balance": bs,
            "summary": {
                "n_types": len(types),
                "group_dist": group_dist,
                "n_unclassified": group_dist.get("미분류", 0),
                "n_lines_reported": n_lines_reported,
                "n_lines_total": len(STANDARD_LINES),
                "bel_csm_ra": [bel_rep, ra_rep, csm_rep],
            },
        }
        summary.append({
            "cik": cik, "company": name, "sector": sector,
            "n_types": len(types),
            "사망": group_dist["사망"], "건강": group_dist["건강"],
            "연금": group_dist["연금"], "저축": group_dist["저축"],
            "기타": group_dist["기타"], "미분류": group_dist["미분류"],
            "BEL": bel_rep, "RA": ra_rep, "CSM": csm_rep,
            "lines_reported": f"{n_lines_reported}/{len(STANDARD_LINES)}",
            "BS_liability_억": int(bs["BS_liability_total_억"] or 0),
        })

    # JSON dump (per company detail)
    (out_path / "feasibility_details.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path / 'feasibility_details.json'}")

    # CSV summary
    csv_path = out_path / "feasibility_summary.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print(f"wrote {csv_path}")

    # 콘솔 종합 요약
    print(f"\n\n{'='*60}\n종합 요약\n{'='*60}\n")
    print(f"  {'회사':<14s}  {'sector':<8s}  {'멤버수':>4s}  {'사망':>2s} {'건강':>2s} {'연금':>2s} {'저축':>2s} {'기타':>2s} {'미분류':>4s}  BEL RA CSM  {'라인':>5s}  {'BS잔액':>12s}")
    for s in summary:
        print(f"  {s['company']:<14s}  {s['sector']:<8s}  {s['n_types']:>4d}  "
              f"{s['사망']:>2d} {s['건강']:>2d} {s['연금']:>2d} {s['저축']:>2d} {s['기타']:>2d} {s['미분류']:>4d}  "
              f"{'Y' if s['BEL'] else 'N':>2s}  {'Y' if s['RA'] else 'N':>2s}  {'Y' if s['CSM'] else 'N':>2s}    "
              f"{s['lines_reported']:>5s}  {s['BS_liability_억']:>10,}억")


if __name__ == "__main__":
    main()
