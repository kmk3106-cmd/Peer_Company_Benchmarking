"""Phase 2: DI817100 U01~U11에 대해 8개 동업사 매핑 가능성 검토.

매핑 등급 (comparison_pipeline.md의 70/20/10 룰 적용):
  PASS    : 동일 element_id (표준) 또는 정확 라벨 일치 (entity 확장)
  WARNING : 라벨 부분 일치 (lab.tsv LIKE '%핵심 키워드%')
  REVIEW  : 정확/부분 일치 모두 미발견 → 해당사 미공시 또는 entity 확장 다른 명명

no-inference rule:
  - 자사 단위 root의 한국어 라벨을 lab_insurers 정확 search
  - 다른 회사들의 lab_insurers에서 같은 라벨 정확 LIKE
  - 부분 일치는 별도 표시, 임의 매핑 금지

출력: report/peer_mapping_di817100.csv + 콘솔 표
"""
from __future__ import annotations

import csv
from pathlib import Path

import duckdb

from peer_benchmarking.domain import peer_groups

SELF_CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"

UNIT_ROOTS = [
    ("U01", "entity00112332_Title20256517565149Abstract"),
    ("U02", "entity00112332_Title20257289204290Abstract"),
    ("U03", "entity00112332_Title202516161119540Abstract"),
    ("U04", "entity00112332_Title20251616323362Abstract"),
    ("U05", "entity00112332_Title202516171838316Abstract"),
    ("U06", "entity00112332_Title202516172856136Abstract"),
    ("U07", "entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsAbstract"),
    ("U08", "entity00112332_DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByComponentsClassificationByDividendStatusAbstract"),
    ("U09", "entity00112332_DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByRemainingCoverageAndIncurredClaimsClassificationByDividendStatusAbstract"),
    ("U10", "dart_DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByComponentsAbstract"),
    ("U11", "dart_DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByRemainingCoverageAndIncurredClaimsAbstract"),
]

# Peers (자사 외 8개 IFRS17 풍부 회사 — Pipeline 메모리 기준)
PEER_CIKS = ("00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917", "00103176")


def get_self_label(con, root: str) -> str:
    """자사 단위 root의 한국어 라벨 정확 search."""
    r = con.execute("""
    SELECT MAX(LABEL) FROM lab_insurers
    WHERE CIK=? AND LANG='ko' AND ELMT_ID=?
      AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
    """, [SELF_CIK, root]).fetchone()
    return (r[0] if r and r[0] else "")


def map_peer(con, peer_cik: str, self_root: str, self_label: str) -> dict:
    """1개 peer에서 self_root에 해당하는 element 매핑.

    1) 자사가 표준 (dart_/ifrs-full_) 이면 동일 element_id가 peer pre_insurers에 있는지
    2) entity 확장이면 동일 한국어 라벨로 peer lab_insurers 정확 search
    3) 못 찾으면 라벨 부분 일치 (LIKE) 시도 — WARNING
    """
    result = {"cik": peer_cik, "self_root": self_root, "status": "REVIEW",
              "peer_element": None, "peer_label": None, "match_kind": None}

    is_entity_self = self_root.startswith("entity")

    if not is_entity_self:
        # 표준 element — peer pre_insurers에 동일 element_id 있는지
        r = con.execute("""
        SELECT COUNT(DISTINCT ELEMENT_ID) FROM pre_insurers
        WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
        """, [peer_cik, ROLE, self_root]).fetchone()
        if r[0] > 0:
            result["status"] = "PASS"
            result["peer_element"] = self_root
            result["match_kind"] = "exact_standard_element_id"
            # label
            lbl = con.execute("""
            SELECT MAX(LABEL) FROM lab_insurers
            WHERE CIK=? AND LANG='ko' AND ELMT_ID=?
              AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
            """, [peer_cik, self_root]).fetchone()
            result["peer_label"] = lbl[0] if lbl and lbl[0] else ""
            return result

    # entity 확장 또는 표준 미보유 → 라벨 정확 search
    if self_label:
        r = con.execute("""
        SELECT ELMT_ID, MAX(LABEL) FROM lab_insurers
        WHERE CIK=? AND LANG='ko' AND LABEL=?
          AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
        GROUP BY ELMT_ID LIMIT 1
        """, [peer_cik, self_label]).fetchone()
        if r and r[0]:
            # peer에 동일 라벨 element 존재 — 그 element가 DI817100에 등장하는지 확인
            in_role = con.execute("""
            SELECT COUNT(*) FROM pre_insurers
            WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
            """, [peer_cik, ROLE, r[0]]).fetchone()
            if in_role[0] > 0:
                result["status"] = "PASS"
                result["peer_element"] = r[0]
                result["peer_label"] = r[1]
                result["match_kind"] = "exact_label_in_role"
                return result
            # else: 같은 라벨 있지만 DI817100 role 밖 → WARNING
            result["status"] = "WARNING"
            result["peer_element"] = r[0]
            result["peer_label"] = r[1]
            result["match_kind"] = "label_match_other_role"
            return result

        # 정확 일치 없음 → 라벨 핵심 키워드 LIKE search (WARNING 후보)
        # 핵심 키워드: 자사 라벨에서 "[ 개요 ]" 제거하고 시작 6글자 패턴
        core = self_label.replace("[ 개요 ]", "").replace("[개요]", "").strip()
        if len(core) >= 8:
            # 첫 8글자로 LIKE search
            head = core[:8]
            r = con.execute(f"""
            SELECT ELMT_ID, MAX(LABEL) FROM lab_insurers
            WHERE CIK=? AND LANG='ko' AND LABEL LIKE ?
              AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
            GROUP BY ELMT_ID LIMIT 1
            """, [peer_cik, f"%{head}%"]).fetchone()
            if r and r[0]:
                in_role = con.execute("""
                SELECT COUNT(*) FROM pre_insurers
                WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
                """, [peer_cik, ROLE, r[0]]).fetchone()
                result["status"] = "WARNING"
                result["peer_element"] = r[0]
                result["peer_label"] = r[1]
                result["match_kind"] = "label_partial_in_role" if in_role[0] > 0 else "label_partial_other_role"
                return result

    # 발견 못함
    return result


def main() -> int:
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    name_map = peer_groups.load_companies()

    print(f"=== Phase 2: DI817100 U01~U11 동업사 매핑 (no-inference) ===")
    print(f"  자사: {SELF_CIK} {name_map[SELF_CIK].name_ko}")
    print(f"  동업사: {len(PEER_CIKS)}개")
    print()

    all_rows = []
    header_row = ["unit", "self_label", "self_root"]
    for cik in PEER_CIKS:
        header_row.append(f"{name_map[cik].name_ko}_status")
        header_row.append(f"{name_map[cik].name_ko}_peer_elem")
    all_rows.append(header_row)

    # Console table
    print(f"{'unit':5s} {'self label (short)':35s} ", end="")
    for cik in PEER_CIKS:
        print(f"{name_map[cik].name_ko[:5]:>6s}", end=" ")
    print()
    print("-" * 110)

    summary = {"PASS": 0, "WARNING": 0, "REVIEW": 0}
    for unit_key, self_root in UNIT_ROOTS:
        self_label = get_self_label(con, self_root)
        row = [unit_key, self_label, self_root]
        cli_short = self_label.replace("[ 개요 ]", "").replace("[개요]", "")[:33]
        print(f"{unit_key:5s} {cli_short:35s} ", end="")
        for cik in PEER_CIKS:
            m = map_peer(con, cik, self_root, self_label)
            row.append(m["status"])
            row.append(m["peer_element"] or "")
            summary[m["status"]] += 1
            marker = {"PASS": "✓", "WARNING": "~", "REVIEW": "✗"}[m["status"]]
            print(f"{marker:>6s}", end=" ")
        print()
        all_rows.append(row)

    print()
    total = sum(summary.values())
    print(f"=== 매핑 결과 요약 (총 {total}개 셀) ===")
    for status, cnt in summary.items():
        pct = cnt / total * 100
        print(f"  {status}: {cnt} ({pct:.1f}%)")

    out = Path("report/peer_mapping_di817100.csv")
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerows(all_rows)
    print(f"\n✓ wrote {out}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
