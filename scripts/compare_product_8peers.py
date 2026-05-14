"""8개사 × 상품군 분해 비교 (DI817105 잔액).

생보 4개사: 5분류 (사망/건강/연금/저축/기타)
손보 4개사: 4분류 (장기/자동차/일반/기타)

핵심: 회사별 상품군 axis 멤버 자동 매핑 → 5분류(생) / 4분류(손) 정규화.
"""
from __future__ import annotations
import re, json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
    TYPES_AXIS, LRC_LIC_AXIS, LRC_EXCL, LC, LIC,
)

LIFE_PEERS = [
    ("00112332", "미래에셋"),
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
]
NONLIFE_PEERS = [
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손보"),
    ("00135917", "한화손보"),
]

# 매핑 룰 (label-based)
LIFE_RULES = [
    (10, r"변액사망|변액 ?death", "사망"),
    (10, r"변액연금|변액 ?annuity", "연금"),
    (10, r"변액저축|변액 ?savings|변액연금저축", "저축"),
    (10, r"변액(?!.*사망)(?!.*연금)(?!.*저축)|변액기타", "저축"),
    (9,  r"사망(?!.*외)|Death|Life(?!.*외)", "사망"),
    (9,  r"건강|Health|질병|암", "건강"),
    (9,  r"연금(?!.*저축)|Annuity|Pension(?!.*Sav)", "연금"),
    (9,  r"저축|Savings|Endowment|연금저축", "저축"),
    (5,  r"LifeInsuranceMember$", "사망"),
    (5,  r"HealthInsuranceMember$", "건강"),
    (3,  r"OtherInsurance|기타", "기타"),
]
NONLIFE_RULES = [
    (10, r"장기|long.?term", "장기"),
    (10, r"자동차|auto|motor", "자동차"),
    (10, r"일반|general", "일반"),
    (8,  r"건강|health|질병|상해", "장기"),
    (8,  r"저축|연금", "장기"),
    (8,  r"재물", "일반"),
    (5,  r"OtherInsurance|기타", "기타"),
    (3,  r"LifeInsuranceMember$", "장기"),
]


def classify(ko_label: str, element_id: str, rules) -> str:
    text = (ko_label or "") + " " + (element_id or "")
    best = ("미분류", 0)
    for prio, pat, group in rules:
        if re.search(pat, text, re.IGNORECASE):
            if prio > best[1]:
                best = (group, prio)
    return best[0]


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
    WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817105' AND v.amount_krw IS NOT NULL
      AND cx.AXIS_ELEMENT_ID='{TYPES_AXIS}'
      AND EXISTS (SELECT 1 FROM cntxt_insurers cs
        WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
          AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP_MEMBER}')
    GROUP BY cx.MEMBER_ELEMENT_ID
    """
    return [{"member": r[0], "ko": r[1], "n": r[2]} for r in con.execute(sql, [cik]).fetchall()]


def fetch_balance_for_member(con, cik: str, member: str) -> float | None:
    """별도·발행·기말·해당 멤버 잔액 = LRC + LIC."""
    total = 0
    found = False
    for elem in (
        "ifrs-full_InsuranceContractsIssuedThatAreLiabilities",
        "ifrs-full_InsuranceContractsIssuedThatAreAssets",
        "ifrs-full_InsuranceContractsThatAreLiabilities",
        "ifrs-full_InsuranceContractsThatAreAssets",
    ):
        for lrclic in (LRC_EXCL, LC, LIC):
            req = {CONS_AXIS: SEP_MEMBER, TYPES_AXIS: member, LRC_LIC_AXIS: lrclic}
            if "Issued" not in elem:
                req[DISAGG_AXIS] = ISSUED_MEMBER
            v = fetch_fact_sum(con, FactQuery(
                cik=cik, report_date="20251231", element_id=elem,
                required_members=req, period_instant="2025-12-31",
            ))
            if v is not None:
                total += v
                found = True
    return total if found else None


con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def analyze(peers, rules, group_order):
    results = {}
    for cik, name in peers:
        members = get_types_members(con, cik)
        # 멤버별 std group 분류 + 잔액
        by_group = {g: 0 for g in group_order}
        by_group["미분류"] = 0
        for m in members:
            group = classify(m["ko"], m["member"], rules)
            bal = fetch_balance_for_member(con, cik, m["member"])
            if bal is not None:
                by_group[group] = by_group.get(group, 0) + bal
        total = sum(by_group.values())
        results[cik] = {"name": name, "by_group": by_group, "total": total}
    return results


print("="*100)
print("생보 4개사 × 5상품군 잔액 (단위: 억원)")
print("="*100)
life_res = analyze(LIFE_PEERS, LIFE_RULES, ["사망", "건강", "연금", "저축", "기타"])
print(f"\n{'회사':<10s}  {'사망':>10s}  {'건강':>10s}  {'연금':>10s}  {'저축':>10s}  {'기타':>10s}  {'미분류':>10s}  {'합계':>11s}")
print("─"*100)
for cik, name in LIFE_PEERS:
    r = life_res[cik]["by_group"]
    t = life_res[cik]["total"]
    def f(v): return f"{v/1e8:>8,.0f}억" if v else "       —"
    print(f"  {name:<8s}  {f(r['사망'])}  {f(r['건강'])}  {f(r['연금'])}  {f(r['저축'])}  {f(r['기타'])}  {f(r['미분류'])}  {f(t)}")

print(f"\n  구성비 (%):")
print(f"{'회사':<10s}  {'사망':>8s}  {'건강':>8s}  {'연금':>8s}  {'저축':>8s}  {'기타':>8s}  {'미분류':>8s}")
print("─"*70)
for cik, name in LIFE_PEERS:
    r = life_res[cik]["by_group"]
    t = life_res[cik]["total"] or 1
    print(f"  {name:<8s}  " + "  ".join(f"{r[g]/t*100:>6.1f}%" for g in ["사망","건강","연금","저축","기타","미분류"]))


print("\n\n" + "="*100)
print("손보 4개사 × 4상품군 잔액 (단위: 억원)")
print("="*100)
nonlife_res = analyze(NONLIFE_PEERS, NONLIFE_RULES, ["장기", "자동차", "일반", "기타"])
print(f"\n{'회사':<10s}  {'장기':>10s}  {'자동차':>10s}  {'일반':>10s}  {'기타':>10s}  {'미분류':>10s}  {'합계':>11s}")
print("─"*90)
for cik, name in NONLIFE_PEERS:
    r = nonlife_res[cik]["by_group"]
    t = nonlife_res[cik]["total"]
    def f(v): return f"{v/1e8:>8,.0f}억" if v else "       —"
    print(f"  {name:<8s}  {f(r['장기'])}  {f(r['자동차'])}  {f(r['일반'])}  {f(r['기타'])}  {f(r['미분류'])}  {f(t)}")

print(f"\n  구성비 (%):")
print(f"{'회사':<10s}  {'장기':>8s}  {'자동차':>8s}  {'일반':>8s}  {'기타':>8s}  {'미분류':>8s}")
print("─"*70)
for cik, name in NONLIFE_PEERS:
    r = nonlife_res[cik]["by_group"]
    t = nonlife_res[cik]["total"] or 1
    print(f"  {name:<8s}  " + "  ".join(f"{r[g]/t*100:>6.1f}%" for g in ["장기","자동차","일반","기타","미분류"]))


# 저장
Path("report/product_mix_results.json").write_text(
    json.dumps({"life": {c: life_res[c] for c, _ in LIFE_PEERS},
                "nonlife": {c: nonlife_res[c] for c, _ in NONLIFE_PEERS}},
               ensure_ascii=False, indent=2, default=lambda x: float(x) if x else None),
    encoding="utf-8")
print("\nwrote report/product_mix_results.json")
