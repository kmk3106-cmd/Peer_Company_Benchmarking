"""8개 role × 자사 [개요] 단위 자동 추출 + 영문 element name 기준 9개사 cross-tab.

대상 role:
  DI817100  보험계약부채(자산) 변동 (원수 변동표) ✓ 메인
  DI817105  보험계약부채(자산) 잔액 (원수 잔액표) ✓ 보조
  DI817300  보험계약 정보 (CSM 만기) ✓ 진단
  DI817305  보험계약 정보 잔액 ✓ 진단
  DI818100  위험관리 정성 (연결)
  DI818105  위험관리 정성 (별도)
  DI818200  위험관리 상세 (연결)
  DI818205  위험관리 상세 (별도)

각 role 별:
  1) 자사 [개요] abstract sub-table 단위 자동 추출 (lab.tsv 정확 search)
  2) 각 단위의 영문 element name = pattern key
  3) 9개사 LIKE search: element 수, 값 보유, 합계 (axis-min, 별도, 억원)
  4) 한국어 라벨 정확 매칭 기반 라인별 cross-tab

출력: report/all_roles_v4.html
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from textwrap import dedent

import duckdb

from peer_benchmarking.domain import peer_groups

SELF_CIK = "00112332"
CIKS = ("00112332", "00126256", "00113058", "00117267",
        "00139214", "00164973", "00159102", "00135917", "00103176")

# 사용자 요청 8개 role
ROLES = [
    ("DI817100", "보험계약부채(자산) 변동", "원수, 변동표", "메인"),
    ("DI817105", "보험계약부채(자산) 잔액", "원수, 잔액표", "보조"),
    ("DI817300", "보험계약 정보 (CSM 만기분석)", "원수, CSM 만기", "진단"),
    ("DI817305", "보험계약 정보 잔액", "원수, 잔액", "진단"),
    ("DI818100", "보험계약 위험관리 (연결)", "위험관리 정성", "2차"),
    ("DI818105", "보험계약 위험관리 (별도)", "위험관리 정성", "2차"),
    ("DI818200", "위험관리 상세 (연결)", "위험관리 상세", "2차"),
    ("DI818205", "위험관리 상세 (별도)", "위험관리 상세", "2차"),
]


def role_id_pattern(role_code: str) -> str:
    return f"dart_2024-06-30_role-{role_code}"


def find_self_outline_abstracts(con, role_id: str):
    """자사 role 안에서 [개요] 라벨 가진 abstract element 추출 (sub-table 단위)."""
    sql = """
    SELECT DISTINCT p.ELEMENT_ID, l.LABEL
    FROM pre_insurers p
    JOIN lab_insurers l ON l.CIK=p.CIK AND l.ELMT_ID=p.ELEMENT_ID
      AND l.LANG='ko' AND l.LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
    JOIN elmt_raw em ON em.ELEMENT_ID = p.ELEMENT_ID
    WHERE p.CIK=? AND p.ROLE_ID=?
      AND em.ABSTRACT='true'
      AND l.LABEL LIKE '%개요%'
    ORDER BY l.LABEL
    """
    return con.execute(sql, [SELF_CIK, role_id]).fetchall()


def english_base(eid: str) -> str:
    """element_id의 prefix 제거 → 영문 본질."""
    return re.sub(r"^(ifrs-full_|dart-gcd_\d+-\d+-\d+_|dart-gcd_|dart_\d+-\d+-\d+_|dart_|entity\d+_)", "", eid)


def fetch_pattern_company_total(con, role_id: str, pat: str, cik: str) -> dict:
    """패턴 LIKE에 매칭되는 element들의 axis-min 합계 (별도)."""
    sql = """
    WITH ax_cnt AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
      FROM cntxt_insurers WHERE CIK=? AND REPORT_DATE='20251231'
      GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    ),
    cands AS (
      SELECT v.ELEMENT_ID, v.amount_krw, ax.n_axes,
             ROW_NUMBER() OVER (PARTITION BY v.ELEMENT_ID
                                ORDER BY ax.n_axes, ABS(v.amount_krw) DESC) AS rn
      FROM val_insurers v
      JOIN ax_cnt ax USING (CIK, REPORT_DATE, CONTEXT_ID)
      JOIN elmt_raw em ON em.ELEMENT_ID = v.ELEMENT_ID
      WHERE v.CIK=? AND v.REPORT_DATE='20251231'
        AND v.amount_krw IS NOT NULL
        AND v.ELEMENT_ID LIKE ?
        AND em.ABSTRACT != 'true' AND em.SUBSTITUTION_GROUP='xbrli:item'
        AND EXISTS (
          SELECT 1 FROM pre_insurers p
          WHERE p.CIK=v.CIK AND p.ROLE_ID=? AND p.ELEMENT_ID=v.ELEMENT_ID
        )
        AND EXISTS (
          SELECT 1 FROM cntxt_insurers c
          WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
            AND c.AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
            AND c.MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'
        )
    )
    SELECT COUNT(DISTINCT ELEMENT_ID), SUM(amount_krw), MAX(amount_krw), MIN(amount_krw)
    FROM cands WHERE rn = 1
    """
    r = con.execute(sql, [cik, cik, f"%{pat}%", role_id]).fetchone()
    return {"n_li": r[0] or 0, "total": r[1], "max": r[2], "min": r[3]}


def fetch_pattern_line_values(con, role_id: str, pat: str) -> dict:
    """한국어 라벨 정확 매칭 cross-tab — pat substring + role_id 한정."""
    sql = """
    WITH ax_cnt AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
      FROM cntxt_insurers WHERE CIK IN ('00112332','00126256','00113058','00117267',
                                         '00139214','00164973','00159102','00135917','00103176')
        AND REPORT_DATE='20251231'
      GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    ),
    sep AS (
      SELECT DISTINCT CIK, CONTEXT_ID FROM cntxt_insurers
      WHERE REPORT_DATE='20251231'
        AND AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
        AND MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'
    ),
    cands AS (
      SELECT v.CIK, v.ELEMENT_ID, v.amount_krw, ax.n_axes, em.PERIOD_TYPE,
             ROW_NUMBER() OVER (PARTITION BY v.CIK, v.ELEMENT_ID
                                ORDER BY ax.n_axes, ABS(v.amount_krw) DESC) AS rn
      FROM val_insurers v
      JOIN ax_cnt ax USING (CIK, REPORT_DATE, CONTEXT_ID)
      JOIN sep USING (CIK, CONTEXT_ID)
      JOIN elmt_raw em ON em.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.REPORT_DATE='20251231' AND v.amount_krw IS NOT NULL
        AND v.ELEMENT_ID LIKE ?
        AND em.ABSTRACT != 'true' AND em.SUBSTITUTION_GROUP='xbrli:item'
        AND EXISTS (
          SELECT 1 FROM pre_insurers p
          WHERE p.CIK=v.CIK AND p.ROLE_ID=? AND p.ELEMENT_ID=v.ELEMENT_ID
        )
    )
    SELECT c.CIK, c.ELEMENT_ID, c.amount_krw, c.PERIOD_TYPE, l.LABEL
    FROM cands c
    LEFT JOIN (SELECT CIK, ELMT_ID, MAX(LABEL) AS LABEL FROM lab_insurers
               WHERE LANG='ko' AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
               GROUP BY CIK, ELMT_ID) l ON l.CIK=c.CIK AND l.ELMT_ID=c.ELEMENT_ID
    WHERE c.rn = 1
    """
    rows = con.execute(sql, [f"%{pat}%", role_id]).fetchall()
    by_label: dict[str, dict] = {}
    for cik, eid, amt, ptype, lbl in rows:
        if not lbl:
            continue
        key = lbl.strip().replace("[ 개요 ]", "[개요]")
        if key not in by_label:
            by_label[key] = {"ko_label": lbl, "period_type": ptype,
                             "amounts": {}, "elements": {}}
        prev = by_label[key]["amounts"].get(cik)
        if prev is None or abs(amt or 0) > abs(prev or 0):
            by_label[key]["amounts"][cik] = amt
            by_label[key]["elements"][cik] = eid
    for k in by_label:
        by_label[k]["n_companies"] = len(by_label[k]["amounts"])
    return by_label


def extract_css(path: Path) -> str:
    m = re.search(r"<style.*?</style>", path.read_text(encoding="utf-8"), re.DOTALL)
    return m.group() if m else ""


def render_company_total_table(name_map, totals: dict) -> str:
    th = "<th></th>" + "".join(f'<th>{name_map[c].name_ko[:5]}</th>' for c in CIKS)

    def _fmt(amt):
        return f"{amt/1e8:+,.0f}" if amt is not None else "—"

    rows = [
        ("LineItem 수", lambda d: d["n_li"]),
        ("합계 sum (억원)", lambda d: _fmt(d["total"])),
        ("최대 라인 max", lambda d: _fmt(d["max"])),
        ("최소 라인 min", lambda d: _fmt(d["min"])),
    ]
    body = ""
    for label, getter in rows:
        body += f'<tr><td><b>{label}</b></td>'
        for cik in CIKS:
            v = getter(totals[cik])
            cls = 'self' if cik == SELF_CIK else ''
            body += f'<td class="{cls}" style="text-align:right">{v}</td>'
        body += "</tr>"
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def render_line_cross_table(name_map, by_label: dict) -> str:
    if not by_label:
        return '<p style="color:#888">(매칭 line item 없음)</p>'

    def _sort_key(item):
        l, d = item
        self_amt = abs(d["amounts"].get(SELF_CIK, 0) or 0)
        max_amt = max(abs(v or 0) for v in d["amounts"].values()) if d["amounts"] else 0
        return (-d["n_companies"], -max(self_amt, max_amt))

    sorted_items = sorted(by_label.items(), key=_sort_key)
    th = ("<th>한국어 라벨 (lab.tsv 정확 일치)</th><th>period</th><th>회사</th>"
          + "".join(f'<th>{name_map[c].name_ko[:5]}</th>' for c in CIKS))
    rows = []
    for lbl, d in sorted_items:
        cells = [
            f'<td style="font-size:0.85em;max-width:320px">{lbl[:80]}</td>',
            f'<td>{d["period_type"] or ""}</td>',
            f'<td style="text-align:right">{d["n_companies"]}/9</td>',
        ]
        for cik in CIKS:
            amt = d["amounts"].get(cik)
            cls = 'self' if cik == SELF_CIK else ''
            if amt is None:
                cells.append(f'<td class="{cls}" style="text-align:right;color:#ccc">—</td>')
            else:
                cells.append(f'<td class="{cls}" style="text-align:right">{amt/1e8:+,.0f}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def render_role_section(con, role_code, role_ko, scope, priority, name_map):
    role_id = role_id_pattern(role_code)

    # 자사 [개요] 단위 추출
    outlines = find_self_outline_abstracts(con, role_id)

    if not outlines:
        return dedent(f"""
        <h2 id="role-{role_code}">{role_code}. {role_ko}</h2>
        <p class="meta">범위: {scope} · 분석 우선도: {priority}</p>
        <p style="color:#888">자사가 보고한 [개요] sub-table 단위 없음.</p>
        """)

    units_html = []
    units_summary = []
    for i, (root_elem, root_label) in enumerate(outlines, 1):
        pat = english_base(root_elem)
        unit_key = f"{role_code}-U{i:02d}"

        # company totals
        totals = {cik: fetch_pattern_company_total(con, role_id, pat, cik) for cik in CIKS}
        line_data = fetch_pattern_line_values(con, role_id, pat)

        n_shared = sum(1 for d in line_data.values() if d["n_companies"] >= 2)
        n_li_self = totals[SELF_CIK]["n_li"]
        units_summary.append((unit_key, root_label, n_li_self, len(line_data), n_shared))

        units_html.append(dedent(f"""
        <h3 id="unit-{unit_key}">{unit_key}. {root_label}</h3>
        <p class="meta">root: <code>{root_elem}</code> · pattern: <code>{pat[:70]}…</code></p>
        <p style="font-weight:600;color:#1F4E79;margin-top:14px">▸ 회사별 합계 (axis-min, 별도, 억원)</p>
        {render_company_total_table(name_map, totals)}
        <p style="font-weight:600;color:#1F4E79;margin-top:18px">▸ 라인별 cross-tab (한국어 라벨 정확 매칭)</p>
        <p class="meta">{len(line_data)} unique 라벨 · {n_shared}개 2개사 이상 공통</p>
        {render_line_cross_table(name_map, line_data)}
        """))

    # role summary
    summary_rows = ""
    for unit_key, lbl, n_li, n_lbl, n_shared in units_summary:
        summary_rows += (f'<tr><td><a href="#unit-{unit_key}">{unit_key}</a></td>'
                         f'<td>{lbl}</td><td style="text-align:right">{n_li}</td>'
                         f'<td style="text-align:right">{n_lbl}</td>'
                         f'<td style="text-align:right">{n_shared}</td></tr>')

    role_html = dedent(f"""
    <h2 id="role-{role_code}">{role_code}. {role_ko}</h2>
    <p class="meta">범위: {scope} · 분석 우선도: {priority} · 자사 [개요] 단위 <b>{len(outlines)}</b>개</p>
    <div class="table-wrap"><table>
      <thead><tr><th>단위</th><th>한국어 라벨 (lab.tsv)</th><th>자사 LineItem</th>
        <th>unique 라벨</th><th>2개사 이상 공통</th></tr></thead>
      <tbody>{summary_rows}</tbody>
    </table></div>
    """) + "\n".join(units_html)
    return role_html


def main() -> int:
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    name_map = peer_groups.load_companies()

    print(f"=== 8개 role × 자사 [개요] 단위 자동 추출 ===")
    role_sections = []
    role_summary = []
    for role_code, role_ko, scope, priority in ROLES:
        role_id = role_id_pattern(role_code)
        outlines = find_self_outline_abstracts(con, role_id)
        print(f"  {role_code} {role_ko}: {len(outlines)} sub-table 단위")
        role_summary.append((role_code, role_ko, scope, priority, len(outlines)))
        role_sections.append(render_role_section(
            con, role_code, role_ko, scope, priority, name_map))

    con.close()

    css = extract_css(Path("report/종합보고서_FY2025.html"))
    today = date.today().isoformat()

    # 결론 카드
    total_units = sum(s[4] for s in role_summary)
    s1 = dedent(f"""
    <h2 id="sec-1-결론">1. 검토 결론</h2>
    <div class="cards">
      <div class="card info">
        <div class="label">분석 role</div>
        <div class="num">{len(ROLES)}</div>
        <div class="sub">재보험(DI817200/205) 제외</div>
      </div>
      <div class="card pass">
        <div class="label">자사 sub-table 단위 (총합)</div>
        <div class="num">{total_units}</div>
        <div class="sub">[개요] abstract 자동 추출</div>
      </div>
      <div class="card warn">
        <div class="label">분석 깊이</div>
        <div class="num">9개사 × 단위</div>
        <div class="sub">회사 합계 + 라인 cross-tab</div>
      </div>
      <div class="card review">
        <div class="label">매핑 키</div>
        <div class="num">영문 element name</div>
        <div class="sub">+ 한국어 라벨 정확 매칭</div>
      </div>
    </div>
    <div class="conclusion">
      <h4>방법</h4>
      <ul>
        <li>각 role 안에서 자사가 보고한 <b>[개요] abstract sub-table 단위</b>를 자동 추출 (lab.tsv 정확 search).</li>
        <li>각 단위의 영문 element name (prefix 제거)을 substring 패턴으로 9개사 LIKE search.</li>
        <li>회사별 합계 = axis-min context 합산 (분해 깊이 흡수, 별도 기준).</li>
        <li>라인 비교 = 한국어 라벨 정확 매칭 cross-tab.</li>
      </ul>
    </div>
    """).strip()

    # role 요약 표
    s2_rows = ""
    for role_code, role_ko, scope, priority, n_units in role_summary:
        s2_rows += (f'<tr><td><a href="#role-{role_code}"><b>{role_code}</b></a></td>'
                    f'<td>{role_ko}</td><td>{scope}</td><td>{priority}</td>'
                    f'<td style="text-align:right">{n_units}</td></tr>')
    s2 = dedent(f"""
    <h2 id="sec-2-role요약">2. role 8개 요약 (자사 [개요] sub-table 단위 수)</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>role 코드</th><th>주석명</th><th>범위</th>
        <th>우선도</th><th>자사 단위 수</th></tr></thead>
      <tbody>{s2_rows}</tbody>
    </table></div>
    """).strip()

    # TOC
    toc_items = "".join(
        f'<a class="toc-item" href="#role-{rc}">{rc}. {ko[:18]}…</a>'
        for rc, ko, _, _, _ in role_summary
    )
    toc = dedent(f"""
    <div class="toc-container">
      <div class="toc-toggle" onclick="document.getElementById('toc-list').classList.toggle('hidden')">📑 목차</div>
      <div id="toc-list" class="toc-list">
        <div class="toc-group">
          <h4 class="toc-group-title">개요</h4>
          <a class="toc-item" href="#sec-1-결론">1. 검토 결론</a>
          <a class="toc-item" href="#sec-2-role요약">2. role 요약</a>
        </div>
        <div class="toc-group">
          <h4 class="toc-group-title">role별 분석 (8개)</h4>
          {toc_items}
        </div>
      </div>
    </div>
    """)

    html = dedent(f"""
    <!doctype html>
    <html lang='ko'><head><meta charset='utf-8'>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>8개 role 동업사 수치 비교 (별도, 억원, 영문 element 기준)</title>
    {css}
    </head><body>
      <h1>📊 8개 role 동업사 수치 비교 v4</h1>
      <div class="meta">
        <span>자사: 미래에셋생명 (CIK {SELF_CIK})</span>
        <span>동업사: 8개 IFRS17 풍부 KOSPI 상장</span>
        <span>기준: 별도 · 단위: 억원 · {today}</span>
        <span>매핑: 영문 element name + 한국어 라벨 정확</span>
      </div>
      {toc}
      {s1}
      {s2}
      {"".join(role_sections)}
      <div class="footer-note">
        build_all_roles_v4.py · 8개 role × 자사 [개요] 자동 추출 × 영문 base substring × axis-min 합산
      </div>
    </body></html>
    """).strip()

    out = Path("report/all_roles_v4.html")
    out.write_text(html, encoding="utf-8")
    print(f"\n✓ wrote {out} ({out.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
