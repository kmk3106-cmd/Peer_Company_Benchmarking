"""계리적가정 표 — 전체 트리 walk + 실제 값 추출."""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
)

CIK = "00112332"
con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# Walk: 최상위 abstract → 모든 자손 (재귀)
ROOT = "entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsAbstract"


def walk_tree(parent: str, depth: int = 0, visited: set = None):
    if visited is None: visited = set()
    if parent in visited: return []
    visited.add(parent)
    rows = con.execute("""
      SELECT DISTINCT p.ELEMENT_ID, p."ORDER",
             MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko
      FROM pre_insurers p
      LEFT JOIN lab_insurers l ON l.CIK=p.CIK AND l.ELMT_ID=p.ELEMENT_ID
      WHERE p.CIK=? AND p.PARENT_ELEMENT_ID=?
      GROUP BY p.ELEMENT_ID, p."ORDER"
      ORDER BY p."ORDER"
    """, [CIK, parent]).fetchall()
    result = []
    for eid, order, ko in rows:
        is_skip = ("Axis" in eid or "Member" in eid)
        is_structural = ("Table" in eid or "Abstract" in eid or "LineItems" in eid)
        if not is_skip:
            result.append((depth, eid, order, ko))
        # walk children regardless (structural nodes have children)
        result += walk_tree(eid, depth + 1, visited)
    return result


print("="*100)
print("계리적가정 표 — 전체 line items 트리 (Axis/Member 제외)")
print("="*100)
all_lines = walk_tree(ROOT)
for depth, eid, order, ko in all_lines:
    indent = "  " * depth
    eshort = eid.replace(f"entity{CIK}_","#")[:60]
    print(f"  {indent}[{order or '?':>4}] {eshort:<62s} ← {ko or ''}")


# 실제 값 추출 (line item 만, 별도·발행, 2025 duration)
print("\n\n" + "="*100)
print("실제 fact 값 (별도·발행 + duration 2025, 단위 억원)")
print("="*100)

line_items = [eid for d, eid, o, k in all_lines]
print(f"\n  대상 line item {len(line_items)} 개:")
for d, eid, order, ko in all_lines:
    eshort = eid.replace(f"entity{CIK}_","#")[:55]
    indent = "    " * d
    # fact 값
    v = fetch_fact_sum(con, FactQuery(
        cik=CIK, report_date="20251231", element_id=eid,
        required_members={CONS_AXIS: SEP_MEMBER, DISAGG_AXIS: ISSUED_MEMBER},
        period_range=("2025-01-01", "2025-12-31"),
    ))
    # without DISAGG filter
    if v is None:
        v = fetch_fact_sum(con, FactQuery(
            cik=CIK, report_date="20251231", element_id=eid,
            required_members={CONS_AXIS: SEP_MEMBER},
            period_range=("2025-01-01", "2025-12-31"),
        ))
    val_s = f"{v/1e8:>+10,.0f}억" if v else "         —"
    print(f"  {indent}{val_s}  {eshort:<57s} ← {ko or ''}")
