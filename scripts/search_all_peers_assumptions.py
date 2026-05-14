"""8개사 모두 '계리적가정에 의한 보험부채 변동내역' 또는 유사 표 정확 search.

각 회사 entity element 다름 → 회사별 lab_insurers 검색.
발견된 표 element 의 자식 line items + 실제 값 추출.
유추·유사 매핑 금지. 정확 매칭만.
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery,
    CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
    COMPONENTS_AXIS, COMP_BEL, COMP_RA, COMP_CSM_ALL,
)

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

# 검색 키워드 — 정확 매칭 우선, 변형 허용
SEARCH_KEYWORDS = [
    "계리적가정에 의한 보험부채 변동내역",
    "계리적가정",
    "계리가정",
    "가정변경에 의한",
    "가정에 의한 보험부채",
    "ActuarialAssumption",
    "AssumptionChange",
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def search_assumption_tables(cik: str) -> list[dict]:
    """회사의 계리적가정 관련 element search."""
    results = []
    for kw in SEARCH_KEYWORDS:
        rows = con.execute("""
          SELECT DISTINCT l.ELMT_ID, l.LABEL
          FROM lab_insurers l
          WHERE l.CIK=? AND l.LANG='ko' AND l.LABEL LIKE ?
        """, [cik, f"%{kw}%"]).fetchall()
        for eid, label in rows:
            results.append({"eid": eid, "label": label, "keyword": kw})
        if results:
            break  # 첫 매치 키워드 결과만
    return results


def get_table_root(cik: str, candidates: list[dict]) -> str | None:
    """후보 element 중 Table/Abstract/LineItems 부모 식별."""
    for c in candidates:
        eid = c["eid"]
        if "Table" in eid and "OfLineItems" not in eid:
            return eid
    # Abstract fallback
    for c in candidates:
        if "Abstract" in c["eid"]:
            return c["eid"]
    return None


def walk_children(cik: str, parent: str, depth: int = 0, visited: set = None) -> list[dict]:
    if visited is None: visited = set()
    if parent in visited or depth > 5: return []
    visited.add(parent)
    rows = con.execute("""
      SELECT DISTINCT p.ELEMENT_ID, p."ORDER",
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko
      FROM pre_insurers p
      LEFT JOIN lab_insurers l ON l.CIK=p.CIK AND l.ELMT_ID=p.ELEMENT_ID
      WHERE p.CIK=? AND p.PARENT_ELEMENT_ID=?
      GROUP BY p.ELEMENT_ID, p."ORDER"
      ORDER BY CAST(p."ORDER" AS DOUBLE)
    """, [cik, parent]).fetchall()
    out = []
    for eid, order, ko in rows:
        is_skip = ("Axis" in eid or "Member" in eid)
        is_struct = ("Table" in eid or "Abstract" in eid or "LineItems" in eid)
        if not is_skip and not is_struct:
            out.append({"eid": eid, "label": ko, "depth": depth, "order": order})
        # 자손 재귀
        out += walk_children(cik, eid, depth + 1, visited)
    return out


def fetch_by_components(cik: str, eid: str):
    """BEL / RA / CSM(전체) 합."""
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
    # 합계: components axis 없이도 시도
    total = fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231", element_id=eid,
        required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
        forbidden_axes=(COMPONENTS_AXIS,),
        period_range=("2025-01-01", "2025-12-31"),
    ))
    return bel, ra, csm, total


# 8개사 실행
all_results = {}
for cik, name in PEERS:
    print(f"\n{'='*100}")
    print(f"  {name} ({cik})")
    print(f"{'='*100}")

    candidates = search_assumption_tables(cik)
    if not candidates:
        print(f"  ❌ '계리적가정' 또는 유사 표 element 미공시")
        all_results[cik] = {"name": name, "status": "not_disclosed", "lines": []}
        continue

    print(f"  ✓ 매치 element {len(candidates)}개:")
    for c in candidates[:5]:
        eshort = c["eid"].replace("ifrs-full_","").replace(f"entity{cik}_","#")[:60]
        print(f"    [{c['keyword']:<25s}] {eshort:<62s} ← {c['label'][:60]}")

    root = get_table_root(cik, candidates)
    if not root:
        # fallback: 첫 element 사용
        root = candidates[0]["eid"]
    print(f"\n  → ROOT 선택: {root[:80]}")

    children = walk_children(cik, root)
    if not children:
        print(f"  ⚠ 자식 line items 없음 (이 element 가 textBlock/summary 일 수 있음)")
        all_results[cik] = {"name": name, "status": "no_children", "root": root, "lines": []}
        continue

    print(f"\n  자식 line items {len(children)}개. 값 추출 중...")
    line_data = []
    for c in children:
        bel, ra, csm, total = fetch_by_components(cik, c["eid"])
        line_data.append({
            "eid": c["eid"], "label": c["label"], "depth": c["depth"], "order": c["order"],
            "BEL": bel, "RA": ra, "CSM": csm, "total": total,
        })

    # 출력
    print(f"\n  {'라인':<50s}  {'BEL':>11s}  {'RA':>11s}  {'CSM':>11s}  {'합계':>11s}")
    print("  " + "─"*100)
    for d in line_data:
        indent = "  " * d["depth"]
        label_s = (indent + (d["label"] or d["eid"][-30:]))[:48]
        def f(v): return f"{v/1e8:>+8,.0f}억" if v is not None else "         —"
        print(f"  {label_s:<50s}  {f(d['BEL'])}  {f(d['RA'])}  {f(d['CSM'])}  {f(d['total'])}")

    all_results[cik] = {
        "name": name, "status": "extracted",
        "root": root, "lines": line_data,
    }

# 저장
Path("report/peer_assumption_changes.json").write_text(
    json.dumps(all_results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\n\n" + "="*100)
print(f"  종합: 8개사 중")
for cik, name in PEERS:
    r = all_results[cik]
    if r["status"] == "extracted":
        print(f"    ✓ {name}: {len(r['lines'])} 라인 추출")
    elif r["status"] == "no_children":
        print(f"    ⚠ {name}: element 있으나 자식 없음")
    else:
        print(f"    ❌ {name}: 미공시")
print(f"\nwrote report/peer_assumption_changes.json")
