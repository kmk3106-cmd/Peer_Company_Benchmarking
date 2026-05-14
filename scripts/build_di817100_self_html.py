"""DI817100 U01~U11 자사(미래에셋) 적재 데이터 HTML.

각 단위의 tree + 값(값 있는 element는 actual context와 amount 모두 표시) — 사업보고서 검증용.
no-inference rule: 단위명·element 라벨은 lab_insurers 정확 search 결과 그대로.

출력: report/di817100_self_data.html
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import duckdb

CIK = "00112332"
COMPANY = "미래에셋생명"
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


def fetch_label(con: duckdb.DuckDBPyConnection, elem: str) -> str:
    """단위 root의 한국어 라벨 정확 search (no-inference)."""
    r = con.execute("""
    SELECT MAX(LABEL) FROM lab_insurers
    WHERE CIK=? AND LANG='ko' AND ELMT_ID=?
      AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
    """, [CIK, elem]).fetchone()
    return (r[0] if r and r[0] else f"(label not found: {elem})")


def fetch_unit_tree(con, root: str):
    """단위 sub-tree (cycle-safe) — value-bearing element 강조용 정보 포함."""
    sql = """
    WITH RECURSIVE walk(elem, parent, ord, depth, path) AS (
      SELECT p.ELEMENT_ID, p.PARENT_ELEMENT_ID, TRY_CAST(p."ORDER" AS DOUBLE), 0,
             [CAST(p.ELEMENT_ID AS VARCHAR)]
      FROM pre_insurers p
      WHERE p.CIK=? AND p.ROLE_ID=? AND p.ELEMENT_ID=?
      UNION ALL
      SELECT p.ELEMENT_ID, p.PARENT_ELEMENT_ID, TRY_CAST(p."ORDER" AS DOUBLE),
             w.depth+1, list_append(w.path, p.ELEMENT_ID)
      FROM pre_insurers p
      JOIN walk w ON p.PARENT_ELEMENT_ID = w.elem
      WHERE p.CIK=? AND p.ROLE_ID=? AND w.depth < 8
        AND NOT list_contains(w.path, p.ELEMENT_ID)
    ),
    nodes AS (
      SELECT elem, parent, MIN(ord) AS ord, MIN(depth) AS depth
      FROM walk GROUP BY elem, parent
    ),
    labels AS (
      SELECT ELMT_ID, MAX(LABEL) AS ko_label FROM lab_insurers
      WHERE CIK=? AND LANG='ko'
        AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
      GROUP BY ELMT_ID
    ),
    val_summary AS (
      SELECT ELEMENT_ID,
             COUNT(DISTINCT CONTEXT_ID) AS n_ctx,
             MAX(ABS(amount_krw)) AS max_abs,
             MIN(amount_krw) AS min_signed,
             MAX(amount_krw) AS max_signed
      FROM val_insurers WHERE CIK=? AND amount_krw IS NOT NULL
      GROUP BY ELEMENT_ID
    )
    SELECT n.elem, n.parent, n.ord, n.depth,
           em.ABSTRACT, em.PERIOD_TYPE, em.BALANCE, em.SUBSTITUTION_GROUP,
           l.ko_label, vs.n_ctx, vs.min_signed, vs.max_signed
    FROM nodes n
    LEFT JOIN elmt_raw em ON em.ELEMENT_ID = n.elem
    LEFT JOIN labels l ON l.ELMT_ID = n.elem
    LEFT JOIN val_summary vs ON vs.ELEMENT_ID = n.elem
    """
    return con.execute(sql, [CIK, ROLE, root, CIK, ROLE, CIK, CIK]).fetchall()


def order_dfs(rows, root):
    """depth-first 정렬."""
    children = {}
    for elem, parent, ord_, depth, *_ in rows:
        children.setdefault(parent, []).append((ord_ if ord_ is not None else 0, elem))
    for k in children:
        children[k].sort()
    row_by_elem = {r[0]: r for r in rows}

    visited = set()
    out = []

    def walk(parent, d):
        for _, eid in children.get(parent, []):
            if eid in visited:
                continue
            visited.add(eid)
            out.append((d, row_by_elem[eid]))
            walk(eid, d + 1)

    if root in row_by_elem:
        visited.add(root)
        out.append((0, row_by_elem[root]))
        walk(root, 1)
    return out


def classify(row):
    sg = row[7] or ""
    abs_ = str(row[4]).lower()
    if "hypercubeItem" in sg:
        return "Table", "table"
    if "dimensionItem" in sg:
        return "Axis", "axis"
    if abs_ == "true":
        return "Abstract", "abstract"
    return "LineItem", "lineitem"


def short(eid):
    return (
        eid.replace("ifrs-full_", "")
        .replace("dart_2024-06-30_", "")
        .replace("dart_", "d:")
        .replace(f"entity{CIK}_", "[자사]")
    )


def render_unit_html(unit_key, root, label, ordered):
    rows_html = []
    n_lineitem = sum(1 for _, r in ordered if classify(r)[0] == "LineItem")
    n_val = sum(1 for _, r in ordered if (r[9] or 0) > 0)
    for depth, r in ordered:
        elem, parent, ord_, _, abs_, period, bal, sg, ko_lbl, n_ctx, vmin, vmax = r
        cls_name, cls_css = classify(r)
        is_entity = elem.startswith("entity")
        has_val = (n_ctx or 0) > 0
        css_classes = [cls_css]
        if is_entity:
            css_classes.append("entity")
        if has_val:
            css_classes.append("hasval")
        indent_px = depth * 14
        vmin_eok = f"{vmin / 1e8:,.0f}" if vmin is not None else ""
        vmax_eok = f"{vmax / 1e8:,.0f}" if vmax is not None else ""
        rows_html.append(
            f'<tr class="{" ".join(css_classes)}">'
            f'<td class="elem" style="padding-left:{indent_px}px">{short(elem)}</td>'
            f'<td class="lbl">{ko_lbl or ""}</td>'
            f'<td class="cls">{cls_name}</td>'
            f'<td class="per">{period or ""}</td>'
            f'<td class="bal">{bal or ""}</td>'
            f'<td class="num">{n_ctx or 0}</td>'
            f'<td class="num">{vmin_eok}</td>'
            f'<td class="num">{vmax_eok}</td>'
            f"</tr>"
        )
    return dedent(f"""
    <section id="{unit_key}">
      <h2>{unit_key}. {label}</h2>
      <p class="meta">root: <code>{short(root)}</code> · 총 {len(ordered)} elements · LineItem {n_lineitem} · 값보유 {n_val}</p>
      <table>
        <thead><tr>
          <th>element</th><th>한국어 라벨 (lab.tsv)</th><th>분류</th>
          <th>period</th><th>bal</th><th>ctx#</th>
          <th>min (억원)</th><th>max (억원)</th>
        </tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </section>
    """)


PAGE_CSS = """
<style>
body { font-family: -apple-system, "Malgun Gothic", "Noto Sans KR", sans-serif;
       max-width: 1400px; margin: 16px auto; padding: 0 16px; color: #1f2937; font-size: 13px; }
h1 { color: #1F4E79; border-bottom: 3px solid #1F4E79; padding-bottom: 8px; }
h2 { color: #1F4E79; margin-top: 32px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }
.meta { color: #6b7280; font-size: 0.9em; margin: 0 0 8px 0; }
.toc { background: #f9fafb; border: 1px solid #e5e7eb; padding: 12px 18px;
       border-radius: 6px; margin-bottom: 24px; }
.toc ol { margin: 0; padding-left: 22px; }
.toc li { margin: 2px 0; line-height: 1.5; }
.toc a { color: #1F4E79; text-decoration: none; }
.toc a:hover { text-decoration: underline; }
table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
th { background: #1F4E79; color: white; padding: 6px 8px; text-align: left;
     position: sticky; top: 0; }
td { border-bottom: 1px solid #e5e7eb; padding: 4px 8px; vertical-align: top; }
td.elem { font-family: Consolas, monospace; font-size: 11px; color: #374151;
          white-space: nowrap; max-width: 480px; overflow: hidden; text-overflow: ellipsis; }
td.lbl { max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
td.cls, td.per, td.bal { color: #6b7280; font-size: 11px; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.table { background: #FCE4D6; font-weight: 600; }
tr.axis { background: #DCE6F1; }
tr.abstract { background: #f3f4f6; color: #6b7280; }
tr.lineitem.hasval { background: #E2EFDA; }
tr.entity td.elem { color: #b45309; font-weight: 600; }
.footer { color: #9ca3af; font-size: 11px; margin-top: 32px;
          border-top: 1px solid #e5e7eb; padding-top: 8px; }
.back { position: fixed; right: 16px; bottom: 16px; padding: 6px 12px;
        background: #1F4E79; color: white; border-radius: 4px;
        text-decoration: none; font-size: 12px; }
</style>
"""


def main() -> int:
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

    units = []
    for key, root in UNIT_ROOTS:
        label = fetch_label(con, root)
        rows = fetch_unit_tree(con, root)
        ordered = order_dfs(rows, root)
        units.append((key, root, label, ordered))
        print(f"  {key}: {label[:55]} ... {len(ordered)} elements")

    con.close()

    toc_html = '<div class="toc"><b>목차 (11 단위)</b><ol>'
    for key, root, label, ordered in units:
        toc_html += f'<li><a href="#{key}">{key}. {label}</a> ({len(ordered)} elements)</li>'
    toc_html += "</ol></div>"

    body = "\n".join(render_unit_html(k, r, l, o) for k, r, l, o in units)

    html = dedent(f"""
    <!doctype html>
    <html lang='ko'><head><meta charset='utf-8'>
    <title>{COMPANY} DI817100 적재 데이터 (U01~U11)</title>
    {PAGE_CSS}
    </head><body>
      <h1>{COMPANY} DI817100 — 11개 단위별 적재 데이터</h1>
      <p class='meta'>
        CIK {CIK} · role: {ROLE}<br>
        no-inference rule: 모든 단위명·element 한국어 라벨은 lab_insurers 정확 search 결과 그대로.<br>
        색상 — 주황: Hypercube/Table, 파랑: Axis, 회색: Abstract, 초록: LineItem 값 보유, 갈색: entity 확장
      </p>
      {toc_html}
      {body}
      <div class='footer'>Generated by build_di817100_self_html.py · DART XBRL 원본 그대로 추출</div>
      <a class='back' href='#top'>↑ 위로</a>
    </body></html>
    """).strip()

    out = Path("report/di817100_self_data.html")
    out.write_text(html, encoding="utf-8")
    print(f"\n✓ wrote {out} ({out.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
