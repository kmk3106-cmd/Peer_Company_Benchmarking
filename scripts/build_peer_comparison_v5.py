"""동업사 비교검증 종합 보고서 v5 — 영문 element name 기준.

구조:
  Level 1: role (8개, 재보험 제외)
  Level 2: sub-table 단위 (자사 [개요] abstract 자동 추출)
  Level 3: line item (concrete xbrli:item)

비교 키:
  - 영문 base name (entity{CIK}_/ifrs-full_/dart_ prefix 제거)
  - 회사 간 같은 base name이면 같은 row, 다른 base는 다른 row
  - 한국어 라벨은 참고용으로만 표시 (매핑 키 X)

값 추출:
  - 별도 (SeparateMember) 기준
  - axis-min context 합산 (회사 분해 깊이 차이 흡수)
  - 단위: 억원
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from textwrap import dedent

import duckdb

from peer_benchmarking.domain import peer_groups

SELF_CIK = "00112332"
CIKS = ("00112332", "00126256", "00113058", "00117267",
        "00139214", "00164973", "00159102", "00135917", "00103176")

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


def base_name(eid: str) -> str:
    """element_id에서 prefix(entity/ifrs/dart) 제거 → 영문 본질 substring."""
    return re.sub(
        r"^(ifrs-full_|dart-gcd_\d+-\d+-\d+_|dart-gcd_|dart_\d+-\d+-\d+_|dart_|entity\d+_)",
        "", eid)


def short_eid(eid: str) -> str:
    """디스플레이용 짧은 이름."""
    return (eid.replace("ifrs-full_", "").replace("dart_2024-06-30_", "")
            .replace("dart_", "d:")
            .replace(f"entity{SELF_CIK}_", "[자사]"))


def find_self_outline_abstracts(con, role_id: str):
    """자사 role에서 [개요] sub-table 단위 추출."""
    return con.execute("""
    SELECT DISTINCT p.ELEMENT_ID, l.LABEL
    FROM pre_insurers p
    JOIN lab_insurers l ON l.CIK=p.CIK AND l.ELMT_ID=p.ELEMENT_ID
      AND l.LANG='ko' AND l.LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
    JOIN elmt_raw em ON em.ELEMENT_ID = p.ELEMENT_ID
    WHERE p.CIK=? AND p.ROLE_ID=?
      AND em.ABSTRACT='true'
      AND l.LABEL LIKE '%개요%'
    ORDER BY l.LABEL
    """, [SELF_CIK, role_id]).fetchall()


def fetch_self_unit_lineitems(con, role_id: str, unit_root: str) -> list[str]:
    """자사 sub-tree (unit_root 하위) 안의 concrete LineItem element_id 추출 (cycle-safe)."""
    rows = con.execute("""
    WITH RECURSIVE walk(elem, path) AS (
      SELECT ELEMENT_ID, [CAST(ELEMENT_ID AS VARCHAR)]
      FROM pre_insurers WHERE CIK=? AND ROLE_ID=? AND ELEMENT_ID=?
      UNION ALL
      SELECT p.ELEMENT_ID, list_append(w.path, p.ELEMENT_ID)
      FROM pre_insurers p JOIN walk w ON p.PARENT_ELEMENT_ID = w.elem
      WHERE p.CIK=? AND p.ROLE_ID=? AND len(w.path) < 8
        AND NOT list_contains(w.path, p.ELEMENT_ID)
    )
    SELECT DISTINCT w.elem FROM walk w
    JOIN elmt_raw em ON em.ELEMENT_ID=w.elem
    WHERE em.ABSTRACT != 'true' AND em.SUBSTITUTION_GROUP='xbrli:item'
    """, [SELF_CIK, role_id, unit_root, SELF_CIK, role_id]).fetchall()
    return [r[0] for r in rows]


def fetch_unit_line_values(con, role_id: str, unit_root: str) -> dict:
    """자사 sub-tree LineItem 추출 → 각 line item의 영문 base name으로 9개사 cross-tab.

    매칭 방법:
      1. 자사 sub-tree에서 LineItem 모두 추출
      2. 각 LineItem의 base name 계산
      3. 9개사 동일 ROLE_ID 안에서 같은 base name (LIKE '%base%')을 가진 element search
      4. 그 element의 axis-min 값을 amounts에 배정

    Returns:
      {base_name: {self_label, period_type, amounts: {cik: amount}}}
    """
    self_lineitems = fetch_self_unit_lineitems(con, role_id, unit_root)
    if not self_lineitems:
        return {}

    # 같은 base 가진 self elements 그룹화
    self_by_base: dict[str, str] = {}  # base → representative self element_id
    for eid in self_lineitems:
        b = base_name(eid)
        if b not in self_by_base:
            self_by_base[b] = eid

    by_base: dict[str, dict] = {}
    for b, self_eid in self_by_base.items():
        # 자사 한국어 라벨 + period type
        meta = con.execute("""
        SELECT em.PERIOD_TYPE,
               (SELECT MAX(LABEL) FROM lab_insurers
                WHERE CIK=? AND ELMT_ID=? AND LANG='ko'
                  AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label') AS lbl
        FROM elmt_raw em WHERE em.ELEMENT_ID=?
        """, [SELF_CIK, self_eid, self_eid]).fetchone()
        ptype = meta[0] if meta else None
        ko_label = (meta[1] if meta else None) or ""

        # 9개사 axis-min 값 매핑 — 같은 base substring을 가진 element search
        amounts = {}
        elem_id_per_cik = {}
        rows = con.execute("""
        WITH ax_cnt AS (
          SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
          FROM cntxt_insurers WHERE REPORT_DATE='20251231'
          GROUP BY CIK, REPORT_DATE, CONTEXT_ID
        ),
        cands AS (
          SELECT v.CIK, v.ELEMENT_ID, v.amount_krw, ax.n_axes,
                 ROW_NUMBER() OVER (PARTITION BY v.CIK, v.ELEMENT_ID
                                    ORDER BY ax.n_axes, ABS(v.amount_krw) DESC) AS rn
          FROM val_insurers v
          JOIN ax_cnt ax USING (CIK, REPORT_DATE, CONTEXT_ID)
          JOIN elmt_raw em ON em.ELEMENT_ID=v.ELEMENT_ID
          WHERE v.REPORT_DATE='20251231' AND v.amount_krw IS NOT NULL
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
        SELECT CIK, ELEMENT_ID, amount_krw FROM cands WHERE rn = 1
        """, [f"%{b}%", role_id]).fetchall()
        for cik, eid, amt in rows:
            # base가 정확히 같은 element만
            if base_name(eid) == b:
                amounts[cik] = amt
                elem_id_per_cik[cik] = eid

        by_base[b] = {"self_label": ko_label, "period_type": ptype,
                      "amounts": amounts, "elements": elem_id_per_cik}
    return by_base


def fetch_unit_total(con, role_id: str, unit_pattern: str, cik: str) -> dict:
    """unit 안에서 회사별 합계 (LineItem axis-min sum)."""
    r = con.execute("""
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
      JOIN elmt_raw em ON em.ELEMENT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.amount_krw IS NOT NULL
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
    SELECT COUNT(DISTINCT ELEMENT_ID), SUM(amount_krw)
    FROM cands WHERE rn = 1
    """, [cik, cik, f"%{unit_pattern}%", role_id]).fetchone()
    return {"n_li": r[0] or 0, "total": r[1]}


def render_line_table(by_base: dict, name_map) -> str:
    """영문 element name × 9개사 cross-table."""
    if not by_base:
        return '<p style="color:#888">(line item 없음)</p>'

    # 정렬: 모든 회사 가진 row 먼저, 그 다음 |max amount| DESC
    def _sort_key(item):
        b, d = item
        n_co = sum(1 for v in d["amounts"].values() if v is not None)
        max_abs = max((abs(v) for v in d["amounts"].values() if v is not None), default=0)
        return (-n_co, -max_abs)

    items = sorted(by_base.items(), key=_sort_key)

    th = ('<th>영문 element (base)</th>'
          '<th>참고 라벨</th><th>period</th><th>회사수</th>'
          + ''.join(f'<th>{name_map[c].name_ko[:5]}</th>' for c in CIKS))
    rows = []
    for b, d in items:
        n_co = sum(1 for v in d["amounts"].values() if v is not None)
        cells = [
            f'<td style="font-family:monospace;font-size:0.76em;max-width:400px;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{b}">{b[:90]}</td>',
            f'<td style="font-size:0.78em;color:#666;max-width:200px;overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap">{(d["self_label"] or "")[:40]}</td>',
            f'<td>{d["period_type"] or ""}</td>',
            f'<td style="text-align:right">{n_co}/9</td>',
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


def render_total_table(con, role_id: str, unit_pattern: str, name_map) -> str:
    """unit 내 회사별 합계 표."""
    totals = {cik: fetch_unit_total(con, role_id, unit_pattern, cik) for cik in CIKS}

    def _fmt(amt):
        return f"{amt/1e8:+,.0f}" if amt is not None else "—"

    th = "<th></th>" + "".join(f'<th>{name_map[c].name_ko[:5]}</th>' for c in CIKS)
    n_li_row = "<td><b>LineItem 수 (값보유)</b></td>" + "".join(
        f'<td class="{"self" if c==SELF_CIK else ""}" style="text-align:right">'
        f'{totals[c]["n_li"]}</td>' for c in CIKS
    )
    sum_row = "<td><b>합계 sum (억원, axis-min)</b></td>" + "".join(
        f'<td class="{"self" if c==SELF_CIK else ""}" style="text-align:right">'
        f'{_fmt(totals[c]["total"])}</td>' for c in CIKS
    )
    return (f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead>'
            f'<tbody><tr>{n_li_row}</tr><tr>{sum_row}</tr></tbody></table></div>')


def render_role_section(con, role_code, role_ko, scope, priority, name_map):
    role_id = f"dart_2024-06-30_role-{role_code}"
    outlines = find_self_outline_abstracts(con, role_id)

    if not outlines:
        return dedent(f"""
        <h2 id="role-{role_code}">{role_code}. {role_ko}</h2>
        <p class="meta">범위: {scope} · 우선도: {priority}</p>
        <p style="color:#888">자사 [개요] sub-table 단위 없음.</p>
        """).strip()

    unit_blocks = []
    for i, (root_elem, root_label) in enumerate(outlines, 1):
        unit_id = f"{role_code}-U{i:02d}"
        unit_pattern = base_name(root_elem)

        by_base = fetch_unit_line_values(con, role_id, root_elem)
        total_html = render_total_table(con, role_id, unit_pattern, name_map)
        line_html = render_line_table(by_base, name_map)

        n_li = len(by_base)
        n_shared = sum(1 for d in by_base.values()
                       if sum(1 for v in d["amounts"].values() if v is not None) >= 2)

        unit_blocks.append(dedent(f"""
        <h3 id="unit-{unit_id}">{unit_id}. {root_label}</h3>
        <p class="meta">
          unit pattern: <code style="font-size:0.85em">{unit_pattern[:80]}</code><br>
          line item {n_li}개 · 2개사 이상 공통 (영문 base name 일치) {n_shared}개
        </p>
        <p style="margin-top:14px;font-weight:600;color:#1F4E79">▸ 회사별 합계 (axis-min, 별도, 억원)</p>
        {total_html}
        <p style="margin-top:18px;font-weight:600;color:#1F4E79">▸ line item별 수치 비교 (영문 element name 기준)</p>
        {line_html}
        """))

    return dedent(f"""
    <h2 id="role-{role_code}">{role_code}. {role_ko}</h2>
    <p class="meta">범위: {scope} · 우선도: {priority} · 자사 sub-table 단위 <b>{len(outlines)}</b>개</p>
    """) + "\n".join(unit_blocks)


def extract_css(path: Path) -> str:
    m = re.search(r"<style.*?</style>", path.read_text(encoding="utf-8"), re.DOTALL)
    return m.group() if m else ""


def main() -> int:
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    name_map = peer_groups.load_companies()

    print(f"=== 동업사 비교검증 종합 보고서 v5 — 영문 element name 기준 ===")
    role_sections = []
    role_summary = []
    for role_code, role_ko, scope, priority in ROLES:
        role_id = f"dart_2024-06-30_role-{role_code}"
        outlines = find_self_outline_abstracts(con, role_id)
        n_units = len(outlines)
        print(f"  {role_code} {role_ko}: {n_units} unit")
        role_summary.append((role_code, role_ko, scope, priority, n_units))
        role_sections.append(render_role_section(
            con, role_code, role_ko, scope, priority, name_map))

    con.close()

    css = extract_css(Path("report/종합보고서_FY2025.html"))
    today = date.today().isoformat()

    total_units = sum(s[4] for s in role_summary)

    # §1 개요
    s1 = dedent(f"""
    <h2 id="sec-1-개요">1. 개요</h2>
    <div class="cards">
      <div class="card info">
        <div class="label">role</div><div class="num">{len(ROLES)}</div>
        <div class="sub">재보험(DI817200/205) 제외</div>
      </div>
      <div class="card pass">
        <div class="label">sub-table 단위</div><div class="num">{total_units}</div>
        <div class="sub">자사 [개요] 자동 추출</div>
      </div>
      <div class="card warn">
        <div class="label">동업사</div><div class="num">9개사</div>
        <div class="sub">자사 + 8개 IFRS17 풍부</div>
      </div>
      <div class="card review">
        <div class="label">매핑 키</div><div class="num">영문 element</div>
        <div class="sub">prefix 제거된 base name</div>
      </div>
    </div>
    <div class="conclusion">
      <h4>비교 방법</h4>
      <ul>
        <li><b>3-level 계층</b>: role → sub-table 단위 → line item</li>
        <li><b>매핑 키 = 영문 element base name</b> (entity{{CIK}}_/ifrs-full_/dart_ prefix 제거).
            회사 간 동일 base = 같은 항목, 다른 base = 회사 단독 row.</li>
        <li><b>값</b>: 별도(Separate) 기준, axis-min context 합산, 단위 <b>억원</b>, 부호 그대로.</li>
        <li><b>한국어 라벨</b>은 참고용 (자사 라벨)만 표시 — cross-key 아님.</li>
        <li><b>자동 매칭</b>: 회사가 같은 영문 element name 사용하면 한 행에 모두 정렬.
            다른 이름이면 회사 단독.</li>
      </ul>
    </div>
    """).strip()

    # §2 role 요약
    s2_rows = ""
    for role_code, role_ko, scope, priority, n_units in role_summary:
        s2_rows += (f'<tr><td><a href="#role-{role_code}"><b>{role_code}</b></a></td>'
                    f'<td>{role_ko}</td><td>{scope}</td><td>{priority}</td>'
                    f'<td style="text-align:right">{n_units}</td></tr>')
    s2 = dedent(f"""
    <h2 id="sec-2-role">2. role 8개 (자사 sub-table 단위 수)</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>role</th><th>주석명</th><th>범위</th><th>우선도</th><th>단위</th></tr></thead>
      <tbody>{s2_rows}</tbody>
    </table></div>
    """).strip()

    # TOC
    toc_role_items = "".join(
        f'<a class="toc-item" href="#role-{rc}">{rc}. {ko[:18]}…</a>'
        for rc, ko, _, _, _ in role_summary
    )
    toc = dedent(f"""
    <div class="toc-container">
      <div class="toc-toggle" onclick="document.getElementById('toc-list').classList.toggle('hidden')">📑 목차</div>
      <div id="toc-list" class="toc-list">
        <div class="toc-group">
          <h4 class="toc-group-title">개요</h4>
          <a class="toc-item" href="#sec-1-개요">1. 개요</a>
          <a class="toc-item" href="#sec-2-role">2. role 8개</a>
        </div>
        <div class="toc-group">
          <h4 class="toc-group-title">role별 비교 (8개)</h4>
          {toc_role_items}
        </div>
      </div>
    </div>
    """)

    html = dedent(f"""
    <!doctype html>
    <html lang='ko'><head><meta charset='utf-8'>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>동업사 비교검증 종합 보고서 v5 — 영문 element name 기준</title>
    {css}
    </head><body>
      <h1>📊 동업사 비교검증 종합 보고서 v5</h1>
      <div class="meta">
        <span>자사: 미래에셋생명 (CIK {SELF_CIK})</span>
        <span>동업사: 8개 IFRS17 풍부 KOSPI 상장</span>
        <span>기준: 별도 · 단위: 억원 · {today}</span>
        <span>매핑: 영문 element base name (no inference)</span>
      </div>
      {toc}
      {s1}
      {s2}
      {"".join(role_sections)}
      <div class="footer-note">
        build_peer_comparison_v5.py · 영문 element name 자동 매칭 · role/sub-table/line-item 3-level · axis-min 합산
      </div>
    </body></html>
    """).strip()

    out = Path("report/동업사_비교검증_종합보고서_v5.html")
    out.write_text(html, encoding="utf-8")
    print(f"\n✓ wrote {out} ({out.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
