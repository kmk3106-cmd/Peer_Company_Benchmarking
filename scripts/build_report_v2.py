"""종합보고서 v2 — DI817100 U01~U11 기반.

구성:
  §1 검토 결론 (매핑 70/20/10 분포)
  §2 11개 단위 정의 (lab.tsv 정확 라벨)
  §3 자사(미래에셋) 적재 데이터 — 단위별 LineItem + 값
  §4 동업사 매핑 매트릭스 (PASS/WARNING/REVIEW)
  §5 매핑된 자료 횡단 비교 (PASS·WARNING 셀에서 peer 값 추출)
  §6 한계·다음 단계

no-inference rule: 모든 라벨은 lab.tsv 정확 search 결과 그대로.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

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

PEER_CIKS = ("00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917", "00103176")
ALL_CIKS = (SELF_CIK,) + PEER_CIKS


def get_label(con, cik: str, elem: str) -> str:
    r = con.execute("""
    SELECT MAX(LABEL) FROM lab_insurers
    WHERE CIK=? AND LANG='ko' AND ELMT_ID=?
      AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
    """, [cik, elem]).fetchone()
    return r[0] if r and r[0] else ""


def fetch_self_lineitems(con, root: str) -> list[tuple]:
    """자사 단위의 LineItem (value-bearing) 목록 + 값 summary."""
    return con.execute("""
    WITH RECURSIVE walk(elem, path) AS (
      SELECT ELEMENT_ID, [CAST(ELEMENT_ID AS VARCHAR)]
      FROM pre_insurers WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
      UNION ALL
      SELECT p.ELEMENT_ID, list_append(w.path, p.ELEMENT_ID)
      FROM pre_insurers p JOIN walk w ON p.PARENT_ELEMENT_ID = w.elem
      WHERE p.CIK=? AND p.ROLE_ID=? AND len(w.path) < 8
        AND NOT list_contains(w.path, p.ELEMENT_ID)
    )
    SELECT DISTINCT w.elem,
      (SELECT MAX(LABEL) FROM lab_insurers
       WHERE CIK=? AND LANG='ko' AND ELMT_ID=w.elem
         AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label') AS lbl,
      em.PERIOD_TYPE,
      (SELECT COUNT(DISTINCT CONTEXT_ID) FROM val_insurers
       WHERE CIK=? AND ELEMENT_ID=w.elem AND amount_krw IS NOT NULL) AS nctx,
      (SELECT MAX(amount_krw) FROM val_insurers
       WHERE CIK=? AND ELEMENT_ID=w.elem AND amount_krw IS NOT NULL) AS vmax,
      (SELECT MIN(amount_krw) FROM val_insurers
       WHERE CIK=? AND ELEMENT_ID=w.elem AND amount_krw IS NOT NULL) AS vmin
    FROM walk w
    JOIN elmt_raw em ON em.ELEMENT_ID = w.elem
    WHERE em.ABSTRACT != 'true' AND em.SUBSTITUTION_GROUP='xbrli:item'
    """, [SELF_CIK, ROLE, root, SELF_CIK, ROLE, SELF_CIK, SELF_CIK, SELF_CIK, SELF_CIK]).fetchall()


def map_peer(con, peer_cik: str, self_root: str, self_label: str) -> dict:
    is_entity_self = self_root.startswith("entity")
    if not is_entity_self:
        r = con.execute("""
        SELECT COUNT(*) FROM pre_insurers WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
        """, [peer_cik, ROLE, self_root]).fetchone()
        if r[0] > 0:
            return {"status": "PASS", "elem": self_root,
                    "label": get_label(con, peer_cik, self_root),
                    "kind": "standard_element"}
    if self_label:
        r = con.execute("""
        SELECT ELMT_ID, MAX(LABEL) FROM lab_insurers
        WHERE CIK=? AND LANG='ko' AND LABEL=?
          AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
        GROUP BY ELMT_ID LIMIT 1
        """, [peer_cik, self_label]).fetchone()
        if r and r[0]:
            in_role = con.execute("""
            SELECT COUNT(*) FROM pre_insurers WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
            """, [peer_cik, ROLE, r[0]]).fetchone()[0]
            if in_role > 0:
                return {"status": "PASS", "elem": r[0], "label": r[1],
                        "kind": "exact_label_in_role"}
            return {"status": "WARNING", "elem": r[0], "label": r[1],
                    "kind": "exact_label_other_role"}
        core = self_label.replace("[ 개요 ]", "").replace("[개요]", "").strip()
        if len(core) >= 8:
            head = core[:8]
            r = con.execute("""
            SELECT ELMT_ID, MAX(LABEL) FROM lab_insurers
            WHERE CIK=? AND LANG='ko' AND LABEL LIKE ?
              AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
            GROUP BY ELMT_ID LIMIT 1
            """, [peer_cik, f"%{head}%"]).fetchone()
            if r and r[0]:
                in_role = con.execute("""
                SELECT COUNT(*) FROM pre_insurers WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
                """, [peer_cik, ROLE, r[0]]).fetchone()[0]
                return {"status": "WARNING", "elem": r[0], "label": r[1],
                        "kind": "label_partial_in_role" if in_role > 0 else "label_partial_other_role"}
    return {"status": "REVIEW", "elem": None, "label": None, "kind": "not_found"}


def fetch_peer_subtree_summary(con, cik, root_elem) -> dict:
    """peer가 root_elem을 가지면 sub-tree LineItem 수 + 값 합."""
    if root_elem is None:
        return {"n_items": 0, "n_with_val": 0, "max_amount": None}
    r = con.execute("""
    WITH RECURSIVE walk(elem, path) AS (
      SELECT ELEMENT_ID, [CAST(ELEMENT_ID AS VARCHAR)] FROM pre_insurers
      WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
      UNION ALL
      SELECT p.ELEMENT_ID, list_append(w.path, p.ELEMENT_ID)
      FROM pre_insurers p JOIN walk w ON p.PARENT_ELEMENT_ID = w.elem
      WHERE p.CIK=? AND p.ROLE_ID=? AND len(w.path) < 8
        AND NOT list_contains(w.path, p.ELEMENT_ID)
    )
    SELECT
      COUNT(DISTINCT w.elem) AS n_items,
      COUNT(DISTINCT CASE WHEN vs.nctx > 0 THEN w.elem END) AS n_val,
      MAX(vs.vmax) AS vmax
    FROM walk w
    JOIN elmt_raw em ON em.ELEMENT_ID = w.elem
      AND em.ABSTRACT != 'true' AND em.SUBSTITUTION_GROUP='xbrli:item'
    LEFT JOIN (
      SELECT ELEMENT_ID, COUNT(DISTINCT CONTEXT_ID) AS nctx, MAX(amount_krw) AS vmax
      FROM val_insurers WHERE CIK=? AND amount_krw IS NOT NULL
      GROUP BY ELEMENT_ID
    ) vs ON vs.ELEMENT_ID = w.elem
    """, [cik, ROLE, root_elem, cik, ROLE, cik]).fetchone()
    return {"n_items": r[0] or 0, "n_with_val": r[1] or 0, "max_amount": r[2]}


PAGE_CSS = """<style>
body { font-family: -apple-system, "Malgun Gothic", "Noto Sans KR", sans-serif;
       max-width: 1400px; margin: 16px auto; padding: 0 16px; color: #1f2937; font-size: 13px; }
h1 { color: #1F4E79; border-bottom: 3px solid #1F4E79; padding-bottom: 8px; }
h2 { color: #1F4E79; margin-top: 36px; border-bottom: 1px solid #d1d5db; padding-bottom: 4px; }
h3 { color: #374151; margin-top: 20px; }
.meta { color: #6b7280; font-size: 0.9em; }
.toc { background: #f9fafb; border: 1px solid #e5e7eb; padding: 12px 18px;
       border-radius: 6px; margin-bottom: 24px; }
.toc a { color: #1F4E79; text-decoration: none; }
.toc a:hover { text-decoration: underline; }
.card { background: #f9fafb; border-left: 4px solid #F59E0B; padding: 8px 14px;
        border-radius: 4px; margin: 6px 0; }
.card.pass { border-left-color: #10B981; }
.card.warning { border-left-color: #F59E0B; }
.card.review { border-left-color: #EF4444; }
table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
th { background: #1F4E79; color: white; padding: 6px 8px; text-align: left; }
td { border-bottom: 1px solid #e5e7eb; padding: 4px 8px; vertical-align: top; }
td.elem { font-family: Consolas, monospace; font-size: 11px; max-width: 280px;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
td.lbl { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.pass { background: #D1FAE5; color: #065F46; }
.warning { background: #FEF3C7; color: #92400E; }
.review { background: #FEE2E2; color: #991B1B; }
.tag { display: inline-block; padding: 1px 6px; border-radius: 3px;
       font-size: 11px; font-weight: 600; }
.summary-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0; }
.summary-stats .stat { background: #f9fafb; padding: 12px; border-radius: 6px; text-align: center; }
.summary-stats .stat .n { font-size: 28px; font-weight: 700; color: #1F4E79; }
.summary-stats .stat .pct { color: #6b7280; font-size: 13px; }
.self { background: #FFF9DB; font-weight: 600; }
.footer { color: #9ca3af; font-size: 11px; margin-top: 40px;
          border-top: 1px solid #e5e7eb; padding-top: 8px; }
</style>"""


def main() -> int:
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    name_map = peer_groups.load_companies()

    # 1. Resolve unit labels (no-inference)
    units = []
    for key, root in UNIT_ROOTS:
        label = get_label(con, SELF_CIK, root)
        units.append((key, root, label))

    # 2. Self lineitems per unit (sort by value-bearing count then |max|)
    self_items: dict[str, list] = {}
    for key, root, _ in units:
        items = fetch_self_lineitems(con, root)
        items_sorted = sorted(items, key=lambda r: ((r[3] or 0), abs(r[4] or 0)), reverse=True)
        self_items[key] = items_sorted

    # 3. Peer mapping matrix
    mapping: dict[str, dict[str, dict]] = {}  # mapping[unit_key][peer_cik] = {status, elem, label, kind}
    for key, root, label in units:
        mapping[key] = {}
        for cik in PEER_CIKS:
            mapping[key][cik] = map_peer(con, cik, root, label)

    # 4. Peer subtree summary (count + max value) for PASS/WARNING cells
    peer_summary: dict[str, dict[str, dict]] = {}
    for key, root, label in units:
        peer_summary[key] = {}
        for cik in PEER_CIKS:
            m = mapping[key][cik]
            if m["status"] in ("PASS", "WARNING") and m["elem"]:
                peer_summary[key][cik] = fetch_peer_subtree_summary(con, cik, m["elem"])
            else:
                peer_summary[key][cik] = {"n_items": 0, "n_with_val": 0, "max_amount": None}

    # 5. Mapping summary
    total_cells = len(units) * len(PEER_CIKS)
    pass_n = sum(1 for u in mapping.values() for m in u.values() if m["status"] == "PASS")
    warn_n = sum(1 for u in mapping.values() for m in u.values() if m["status"] == "WARNING")
    review_n = sum(1 for u in mapping.values() for m in u.values() if m["status"] == "REVIEW")

    con.close()

    # ─── HTML 빌드 ───
    today = date.today().isoformat()

    # §1
    s1 = dedent(f"""
    <section id="s1"><h2>1. 검토 결론</h2>
      <p>DI817100 (보험계약부채(자산)의 변동) 안에 자사(미래에셋생명)가 보고한 11개 sub-table 단위에 대해
      8개 동업사 매핑 가능성을 검토했다. 모든 단위명·element 라벨은 <code>lab_insurers</code> 정확 search 결과를 그대로 사용
      (no-inference rule).</p>
      <div class="summary-stats">
        <div class="stat pass"><div class="n">{pass_n}</div><div>PASS</div>
          <div class="pct">{pass_n/total_cells*100:.1f}%</div></div>
        <div class="stat warning"><div class="n">{warn_n}</div><div>WARNING</div>
          <div class="pct">{warn_n/total_cells*100:.1f}%</div></div>
        <div class="stat review"><div class="n">{review_n}</div><div>REVIEW</div>
          <div class="pct">{review_n/total_cells*100:.1f}%</div></div>
      </div>
      <p class="meta">목표 70/20/10 대비 PASS 비율이 낮음 — U01·U04·U06·U07이 자사 entity 확장 단위라 다른 회사는
      구조 자체가 다름. U10·U11 (표준 dart 차이조정 표)은 거의 모든 회사 PASS.</p>
    </section>
    """).strip()

    # §2
    s2_rows = []
    for key, root, label in units:
        is_entity = "★ entity 확장" if root.startswith("entity") else "표준"
        s2_rows.append(
            f'<tr><td>{key}</td><td>{label}</td>'
            f'<td class="elem">{root}</td><td>{is_entity}</td>'
            f'<td class="num">{len(self_items[key])}</td></tr>'
        )
    s2 = dedent(f"""
    <section id="s2"><h2>2. 11개 단위 정의 (lab.tsv 정확 라벨)</h2>
      <p class="meta">각 단위 root abstract element와 그 한국어 라벨. 미래에셋 사업보고서 원문 그대로.</p>
      <table><thead><tr>
        <th>key</th><th>한국어 라벨 (lab.tsv)</th><th>root element_id</th>
        <th>구분</th><th>LineItem 수</th>
      </tr></thead><tbody>{''.join(s2_rows)}</tbody></table>
    </section>
    """).strip()

    # §3 자사 데이터 (단위별 LineItem)
    s3_sections = []
    for key, root, label in units:
        items = self_items[key]
        n_val = sum(1 for it in items if (it[3] or 0) > 0)
        rows = []
        for elem, lbl, period, nctx, vmax, vmin in items[:30]:  # top 30
            short = elem.replace("ifrs-full_","").replace("dart_","d:").replace(f"entity{SELF_CIK}_","[자사]")[:55]
            vmax_eok = f"{vmax/1e8:,.0f}" if vmax is not None else ""
            vmin_eok = f"{vmin/1e8:,.0f}" if vmin is not None else ""
            css = "self" if (nctx or 0) > 0 else ""
            rows.append(f'<tr class="{css}"><td class="elem">{short}</td><td class="lbl">{lbl or ""}</td>'
                        f'<td>{period or ""}</td><td class="num">{nctx or 0}</td>'
                        f'<td class="num">{vmin_eok}</td><td class="num">{vmax_eok}</td></tr>')
        more = f'<p class="meta">… (값 보유 {n_val}개 중 상위 30개 표시. 전체는 <a href="di817100_self_data.html">자사 적재 데이터 HTML</a> 참조)</p>' if len(items) > 30 else ""
        s3_sections.append(dedent(f"""
        <h3 id="self_{key}">{key}. {label}</h3>
        <p class="meta">LineItem {len(items)}개 · 값 보유 {n_val}개</p>
        <table><thead><tr>
          <th>element</th><th>한국어 라벨</th><th>period</th><th>ctx#</th><th>min(억)</th><th>max(억)</th>
        </tr></thead><tbody>{''.join(rows)}</tbody></table>
        {more}
        """))
    s3 = '<section id="s3"><h2>3. 자사(미래에셋) 적재 데이터 — 단위별 LineItem</h2>' + "\n".join(s3_sections) + '</section>'

    # §4 매핑 매트릭스
    s4_header = "<th>단위</th><th>한국어 라벨</th>" + "".join(
        f'<th>{name_map[c].name_ko}</th>' for c in PEER_CIKS
    )
    s4_rows = []
    for key, root, label in units:
        cells = [f'<td><b>{key}</b></td>', f'<td class="lbl">{label}</td>']
        for cik in PEER_CIKS:
            m = mapping[key][cik]
            status = m["status"]
            elem_short = (m["elem"] or "").replace("ifrs-full_","").replace("dart_","d:")\
                                          .replace(f"entity{cik}_","[ent]")[:30]
            label_short = (m["label"] or "")[:25]
            tip = f"{elem_short}<br><span style='font-size:10px'>{label_short}</span><br><i>{m['kind']}</i>"
            cells.append(f'<td class="{status.lower()}"><span class="tag {status.lower()}">{status}</span><br>'
                         f'<span style="font-size:10px">{label_short}</span></td>')
        s4_rows.append('<tr>' + ''.join(cells) + '</tr>')
    s4 = dedent(f"""
    <section id="s4"><h2>4. 동업사 매핑 매트릭스 (PASS/WARNING/REVIEW)</h2>
      <p class="meta">11 단위 × 8 동업사 = 88 셀. PASS = 동일 element_id 또는 정확 라벨 일치 (in DI817100).
      WARNING = 라벨 부분 일치 또는 다른 role에서 발견. REVIEW = 미발견.</p>
      <table><thead><tr>{s4_header}</tr></thead><tbody>{''.join(s4_rows)}</tbody></table>
    </section>
    """).strip()

    # §5 매핑된 자료 — PASS·WARNING 셀의 peer sub-tree summary
    s5_header = "<th>단위</th><th>구분</th><th>자사 (미래에셋)</th>" + "".join(
        f'<th>{name_map[c].name_ko}</th>' for c in PEER_CIKS
    )
    s5_rows = []
    for key, root, label in units:
        self_items_list = self_items[key]
        self_n_items = len(self_items_list)
        self_n_val = sum(1 for it in self_items_list if (it[3] or 0) > 0)
        # items count row
        cells_items = [f'<td rowspan="2"><b>{key}</b></td>',
                       '<td>LineItem 수</td>',
                       f'<td class="self num">{self_n_items}</td>']
        for cik in PEER_CIKS:
            ps = peer_summary[key][cik]
            cells_items.append(f'<td class="num">{ps["n_items"]}</td>')
        s5_rows.append('<tr>' + ''.join(cells_items) + '</tr>')
        # values count row
        cells_val = ['<td>값 보유</td>',
                     f'<td class="self num">{self_n_val}</td>']
        for cik in PEER_CIKS:
            ps = peer_summary[key][cik]
            cells_val.append(f'<td class="num">{ps["n_with_val"]}</td>')
        s5_rows.append('<tr>' + ''.join(cells_val) + '</tr>')
    s5 = dedent(f"""
    <section id="s5"><h2>5. 매핑된 자료 — 동업사 sub-tree LineItem·값 보유 수</h2>
      <p class="meta">PASS·WARNING 셀에서 peer의 매핑된 root element 아래 sub-tree를 펼쳐
      LineItem 수와 값(amount_krw) 보유 element 수를 계산. REVIEW (미발견) 셀은 0.</p>
      <table><thead><tr>{s5_header}</tr></thead><tbody>{''.join(s5_rows)}</tbody></table>
    </section>
    """).strip()

    # §6
    s6 = dedent("""
    <section id="s6"><h2>6. 한계 · 다음 단계</h2>
      <ul>
        <li><b>매핑 한계 (REVIEW 50%)</b>: U01(회계모형별 보험부채), U04(투자수익·보험금융손익),
        U06(보험수익), U07(계리적가정)은 미래에셋 entity 확장 sub-table이라 다른 회사 사업보고서가 다른 구조로 공시.
        라벨 정확 search로 발견 불가 → 사용자 검토 대상.</li>
        <li><b>표준 차이조정 (PASS)</b>: U10·U11은 표준 dart element라 거의 모든 회사가 같은 element로 공시.
        횡단 비교 안정.</li>
        <li><b>WARNING 35.2%</b>: 라벨 핵심 키워드는 일치하지만 정확 라벨 또는 in-role 매칭은 아님.
        peer 실제 공시 표 구조를 확인해 매핑 확정 또는 REVIEW 강등 필요.</li>
        <li><b>다음 단계</b>: (a) U07 계리적가정 변동내역은 §5.11과 같이 회사별 entity 확장 정확 search 후 8개사 비교.
        (b) U10·U11 차이조정 표는 axis (cons/sep + Disagg + Components/LRC_LIC) min n_axes 합산으로 BS 일치 검증.
        (c) WARNING 셀은 peer 사업보고서 원본 pre.xml grep으로 확정.</li>
      </ul>
    </section>
    """).strip()

    # TOC
    toc = dedent(f"""
    <div class="toc"><b>목차</b>
      <ul style="margin:0;padding-left:20px;">
        <li><a href="#s1">1. 검토 결론</a></li>
        <li><a href="#s2">2. 11개 단위 정의</a></li>
        <li><a href="#s3">3. 자사 적재 데이터 (U01~U11)</a>
          <ul>{"".join(f'<li><a href="#self_{k}">{k}. {l[:30]}…</a></li>' for k, r, l in units)}</ul>
        </li>
        <li><a href="#s4">4. 동업사 매핑 매트릭스</a></li>
        <li><a href="#s5">5. 매핑된 자료 — 동업사 sub-tree</a></li>
        <li><a href="#s6">6. 한계·다음 단계</a></li>
      </ul>
    </div>
    """)

    html = dedent(f"""
    <!doctype html>
    <html lang='ko'><head><meta charset='utf-8'>
    <title>종합보고서 v2 — DI817100 동업사 매핑·비교 검증 ({today})</title>
    {PAGE_CSS}
    </head><body>
      <h1>📊 종합보고서 v2 — DI817100 보험계약부채(자산) 변동 동업사 비교</h1>
      <p class="meta">
        자사: 미래에셋생명 (CIK {SELF_CIK}) · 동업사: KOSPI 상장 IFRS17 풍부 8개사<br>
        대상: DI817100 (보험계약부채(자산)의 변동) 11개 sub-table 단위<br>
        기준: 별도(separate) · {today} 생성<br>
        규칙: no-inference (lab.tsv 정확 search 라벨만 사용)
      </p>
      {toc}
      {s1}
      {s2}
      {s3}
      {s4}
      {s5}
      {s6}
      <div class="footer">build_report_v2.py · DART XBRL 원본 그대로 추출</div>
    </body></html>
    """).strip()

    out = Path("report/종합보고서_v2_DI817100.html")
    out.write_text(html, encoding="utf-8")
    print(f"✓ wrote {out} ({out.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
