"""Step 1: 동업사 부채 관련 주석공시 작성여부 매트릭스.

대상 role:
  - DI817100/105 보험계약부채 변동·잔액 (원수)
  - DI817300/305 보험계약 정보 (CSM 만기분석 등)

각 회사 × role 에 대해:
  - 보고 여부 (fact 존재)
  - 별도(Separate) 기준 보고 여부
  - LRC/LIC × 상품군 분해 보고 여부
  - BEL/RA/CSM (components_axis) 분해 보고 여부
  - 상품군 axis 멤버 다양성 (몇 개 product?)

출력: report/coverage_matrix.csv + 콘솔 요약
"""
from __future__ import annotations
import csv
from pathlib import Path
import duckdb

CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
SEP = "ifrs-full_SeparateMember"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"
LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
COMP_AXIS = "ifrs-full_InsuranceContractsByComponentsAxis"

ROLES = [
    ("DI817100", "보험계약부채 변동"),
    ("DI817105", "보험계약부채 잔액"),
    ("DI817300", "보험계약 정보"),
    ("DI817305", "보험계약 정보 (잔액)"),
]


def peers(con) -> list[tuple[str, str]]:
    """data/ref/companies.csv 에서 peer 목록 읽기."""
    import csv as _csv
    out = []
    with open("data/ref/companies.csv", encoding="utf-8-sig") as f:
        for row in _csv.DictReader(f):
            out.append((row["cik"], row["name_ko"]))
    return sorted(out, key=lambda r: r[1])


def role_id_for(role_code: str) -> str:
    return f"dart_2024-06-30_role-{role_code}"


def coverage_for(con, cik: str, role_code: str) -> dict:
    role_id = role_id_for(role_code)

    # 1) 어떤 element라도 fact 가 있나
    n_facts = con.execute("""
      SELECT COUNT(*) FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
    """, [cik, role_id]).fetchone()[0]

    if n_facts == 0:
        return dict(n_facts=0, has_sep=0, has_lrc_lic=0, has_components=0,
                    has_types=0, n_types=0, types_members="")

    # 2) 별도(Separate) 보고
    has_sep = con.execute(f"""
      SELECT COUNT(*) FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
        AND EXISTS (SELECT 1 FROM cntxt_insurers cx
          WHERE cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
            AND cx.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cx.MEMBER_ELEMENT_ID='{SEP}')
    """, [cik, role_id]).fetchone()[0]

    # 3) LRC/LIC axis 분해 보고 (별도·발행)
    has_lrc_lic = con.execute(f"""
      SELECT COUNT(*) FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
        AND EXISTS (SELECT 1 FROM cntxt_insurers cx
          WHERE cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
            AND cx.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cx.MEMBER_ELEMENT_ID='{SEP}')
        AND EXISTS (SELECT 1 FROM cntxt_insurers cx
          WHERE cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
            AND cx.AXIS_ELEMENT_ID='{LRC_LIC_AXIS}')
    """, [cik, role_id]).fetchone()[0]

    # 4) BEL/RA/CSM components_axis 분해 보고
    has_components = con.execute(f"""
      SELECT COUNT(*) FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
        AND EXISTS (SELECT 1 FROM cntxt_insurers cx
          WHERE cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
            AND cx.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cx.MEMBER_ELEMENT_ID='{SEP}')
        AND EXISTS (SELECT 1 FROM cntxt_insurers cx
          WHERE cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
            AND cx.AXIS_ELEMENT_ID='{COMP_AXIS}')
    """, [cik, role_id]).fetchone()[0]

    # 5) TypesOfContracts axis 멤버 수
    rows = con.execute(f"""
      SELECT DISTINCT cx.MEMBER_ELEMENT_ID,
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko
      FROM val_insurers v
      JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
      JOIN cntxt_insurers cx ON cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=cx.MEMBER_ELEMENT_ID AND l.LANG='ko'
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
        AND cx.AXIS_ELEMENT_ID='{TYPES_AXIS}'
        AND EXISTS (SELECT 1 FROM cntxt_insurers cs
          WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
            AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
      GROUP BY cx.MEMBER_ELEMENT_ID
    """, [cik, role_id]).fetchall()
    types_members = "; ".join(sorted(set(r[1] or r[0].split("_")[-1].replace("Member","") for r in rows)))[:200]

    return dict(
        n_facts=n_facts,
        has_sep=1 if has_sep > 0 else 0,
        has_lrc_lic=1 if has_lrc_lic > 0 else 0,
        has_components=1 if has_components > 0 else 0,
        has_types=1 if rows else 0,
        n_types=len(rows),
        types_members=types_members,
    )


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    peer_list = peers(con)
    print(f"Peers: {len(peer_list)}\n")

    out_rows = []
    for cik, name in peer_list:
        for role_code, role_label in ROLES:
            cov = coverage_for(con, cik, role_code)
            out_rows.append(dict(cik=cik, company=name, role=role_code, role_label=role_label, **cov))

    out_path = Path("report/coverage_matrix.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path}\n")

    # 콘솔 요약: role 별 매트릭스
    for role_code, role_label in ROLES:
        print(f"\n===== {role_code} ({role_label}) =====")
        print(f"  {'회사':<22s}  facts  별도  LRC/LIC  BEL_RA_CSM  상품군  멤버수")
        for cik, name in peer_list:
            cov = [r for r in out_rows if r["cik"]==cik and r["role"]==role_code][0]
            print(f"  {name:<22s}  {cov['n_facts']:>5,}  {'✓' if cov['has_sep'] else '·':>3s}  "
                  f"{'✓' if cov['has_lrc_lic'] else '·':>5s}    {'✓' if cov['has_components'] else '·':>6s}      "
                  f"{'✓' if cov['has_types'] else '·':>3s}     {cov['n_types']:>3d}")

    # 종합 요약: 부채변동 (DI817100) 비교 가용성
    print("\n\n===== 종합 요약 (DI817100 보험계약부채 변동) =====")
    di_rows = [r for r in out_rows if r["role"]=="DI817100"]
    print(f"  전체 회사: {len(di_rows)}")
    print(f"  DI817100 보고: {sum(1 for r in di_rows if r['n_facts']>0)}개사")
    print(f"  별도 기준 보고: {sum(1 for r in di_rows if r['has_sep'])}개사")
    print(f"  LRC/LIC × 상품군 분해: {sum(1 for r in di_rows if r['has_lrc_lic'] and r['has_types'])}개사")
    print(f"  BEL/RA/CSM 분해: {sum(1 for r in di_rows if r['has_components'])}개사")
    print()
    print("  ※ 두 view 모두 가용 회사 (LRC/LIC × 상품군 + BEL/RA/CSM):")
    for r in di_rows:
        if r["has_lrc_lic"] and r["has_types"] and r["has_components"]:
            print(f"    - {r['company']}")
    print()
    print("  ※ 한 view만 가용 회사:")
    for r in di_rows:
        lrc_yes = r["has_lrc_lic"] and r["has_types"]
        comp_yes = r["has_components"]
        if lrc_yes != comp_yes and r["n_facts"]>0:
            views = []
            if lrc_yes: views.append("LRC/LIC×상품군")
            if comp_yes: views.append("BEL/RA/CSM")
            print(f"    - {r['company']}: {', '.join(views)}")


if __name__ == "__main__":
    main()
