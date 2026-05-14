"""P1~P9 패턴별 동업사 수치 비교표 HTML.

각 패턴마다:
  - base_name (prefix 제거된 영문 element name) × 9개사 매트릭스
  - 값 = 그 회사가 그 element 보고한 axis-min row의 amount_krw (억원)
  - 같은 base_name이라면 다른 prefix (dart_/ifrs-full_/entity_) 도 동일 라인으로 합쳐 비교
  - 별도 기준, 단위 억원, 정렬: n_companies DESC + |max amount| DESC
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from textwrap import dedent

import duckdb

from peer_benchmarking.domain import peer_groups

SELF_CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"
CIKS = ("00112332", "00126256", "00113058", "00117267",
        "00139214", "00164973", "00159102", "00135917", "00103176")

PATTERNS = [
    ("P1", "LRC/LIC 차이조정",
     "DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByRemainingCoverageAndIncurredClaims"),
    ("P2", "구성요소 차이조정",
     "DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByComponents"),
    ("P3", "계리적 가정 변동",
     "ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptions"),
    ("P4", "CSM 기간별 기대수익",
     "ExpectedRevenueRecognitionAmountByPeriodOfContractualServiceMargin"),
    ("P5", "회계모형·포트폴리오",
     "InsuranceLiabilitiesByAccountingModelAndPortfolio"),
    ("P6", "투자서비스수익·보험금융",
     "InvestmentServiceProfitAndInsuranceRelatedFinancialIncomeAndLoss"),
    ("P7", "보험수익 분해",
     "InsuranceRevenue"),
    ("P8", "직접참가 파생 상쇄",
     "OffsettingEffectOfDerivativesOnFinancialRiskOfInsuranceContractsWithDirectParticipation"),
    ("P9", "직접참가 기초항목",
     "UnderlyingItemsForInsuranceContractsWithDirectParticipationFeatures"),
]


def base_name(eid: str) -> str:
    """prefix(ifrs-full_/dart_*/entity*_) 제거된 base name — cross-company key."""
    s = re.sub(r"^(ifrs-full_|dart-gcd_\d+-\d+-\d+_|dart-gcd_|dart_\d+-\d+-\d+_|dart_|entity\d+_)", "", eid)
    # entity 확장이 OfXxx 또는 LineItems suffix를 가지면 normalize 어렵지만 base는 유지
    return s


def fetch_pattern_values(con, pat: str) -> dict:
    """패턴 LIKE에 매칭되는 9개사 element + axis-min amount_krw 추출.

    Returns:
      {
        base_name: {
          'ko_label': str,  # any peer's lab.tsv label
          'period_type': str,
          'amounts': {cik: float | None},
          'n_companies': int,
        }
      }
    """
    sql = """
    WITH ax_cnt AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
      FROM cntxt_insurers WHERE CIK IN ('00112332','00126256','00113058','00117267',
                                         '00139214','00164973','00159102','00135917','00103176')
        AND REPORT_DATE='20251231'
      GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    ),
    sep_ctx AS (
      SELECT DISTINCT CIK, CONTEXT_ID FROM cntxt_insurers
      WHERE REPORT_DATE='20251231'
        AND AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
        AND MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'
    ),
    candidates AS (
      SELECT v.CIK, v.ELEMENT_ID, v.CONTEXT_ID, v.amount_krw, ax.n_axes,
             em.PERIOD_TYPE, em.ABSTRACT
      FROM val_insurers v
      JOIN ax_cnt ax USING (CIK, REPORT_DATE, CONTEXT_ID)
      JOIN sep_ctx USING (CIK, CONTEXT_ID)
      JOIN elmt_raw em ON em.ELEMENT_ID = v.ELEMENT_ID
      WHERE v.amount_krw IS NOT NULL
        AND v.ELEMENT_ID LIKE ?
        AND em.ABSTRACT != 'true'
        AND em.SUBSTITUTION_GROUP = 'xbrli:item'
        AND v.REPORT_DATE='20251231'
    ),
    ranked AS (
      SELECT *, ROW_NUMBER() OVER (
        PARTITION BY CIK, ELEMENT_ID
        ORDER BY n_axes ASC, ABS(amount_krw) DESC
      ) AS rn FROM candidates
    )
    SELECT r.CIK, r.ELEMENT_ID, r.amount_krw, r.PERIOD_TYPE,
           l.LABEL AS ko_label
    FROM ranked r
    LEFT JOIN (
      SELECT CIK, ELMT_ID, MAX(LABEL) AS LABEL
      FROM lab_insurers WHERE LANG='ko'
        AND LABEL_ROLE_URI='http://www.xbrl.org/2003/role/label'
      GROUP BY CIK, ELMT_ID
    ) l ON l.CIK = r.CIK AND l.ELMT_ID = r.ELEMENT_ID
    WHERE r.rn = 1
    """
    rows = con.execute(sql, [f"%{pat}%"]).fetchall()

    # Cross-key = ko_label (no-inference: 라벨이 같으면 같은 항목)
    # 영문 base_name은 entity 확장 suffix(OfXXXMember/Abstract) 때문에 회사마다 unique
    by_label: dict[str, dict] = {}
    for cik, eid, amt, ptype, ko_label in rows:
        if not ko_label:
            continue  # 라벨 없는 element는 cross-comparison 불가
        # 라벨 normalize: [ 개요 ] / [개요] 차이 흡수
        norm = ko_label.strip().replace("[ 개요 ]", "[개요]")
        key = norm
        if key not in by_label:
            by_label[key] = {"ko_label": ko_label,
                             "period_type": ptype,
                             "amounts": {},
                             "elements": {},
                             "n_companies": 0}
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


def fetch_pattern_company_total(con, pat: str, cik: str) -> dict:
    """패턴 내 모든 element에 대해 axis-min sum (회사별 합계, 별도)."""
    r = con.execute("""
    WITH ax_cnt AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
      FROM cntxt_insurers WHERE CIK=? AND REPORT_DATE='20251231'
      GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    ),
    candidates AS (
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
          SELECT 1 FROM cntxt_insurers c
          WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
            AND c.AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
            AND c.MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'
        )
    )
    SELECT COUNT(DISTINCT ELEMENT_ID) AS n_li,
           SUM(amount_krw) AS total,
           MAX(amount_krw) AS max_amt,
           MIN(amount_krw) AS min_amt
    FROM candidates WHERE rn = 1
    """, [cik, cik, f"%{pat}%"]).fetchone()
    return {"n_li": r[0] or 0, "total": r[1], "max": r[2], "min": r[3]}


def render_pattern_section(pat_id, pat_ko, pat, by_base, name_map):
    if not by_base:
        return f'<h2 id="sec-{pat_id}">{pat_id}. {pat_ko}</h2><p>(매칭 element 없음 / 값 없음)</p>'

    # base sorted: n_companies DESC, then by self|max| DESC
    def _sort_key(item):
        b, d = item
        self_amt = abs(d["amounts"].get(SELF_CIK, 0) or 0)
        max_amt = max(abs(v or 0) for v in d["amounts"].values()) if d["amounts"] else 0
        return (-d["n_companies"], -max(self_amt, max_amt))

    sorted_items = sorted(by_base.items(), key=_sort_key)

    rows = []
    for label, d in sorted_items:
        cells = [
            f'<td style="font-size:0.85em;max-width:340px">{label[:80]}</td>',
            f'<td>{d["period_type"] or ""}</td>',
            f'<td style="text-align:right">{d["n_companies"]}/9</td>',
        ]
        for cik in CIKS:
            amt = d["amounts"].get(cik)
            cls = "self" if cik == SELF_CIK else ""
            if amt is None:
                cells.append(f'<td class="{cls}" style="text-align:right;color:#ccc">—</td>')
            else:
                eok = amt / 1e8
                cells.append(f'<td class="{cls}" style="text-align:right">{eok:+,.0f}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')

    th = ('<th>한국어 라벨 (lab.tsv 정확 일치)</th><th>period</th>'
          '<th>회사수</th>'
          + ''.join(f'<th>{name_map[c].name_ko[:5]}</th>' for c in CIKS))

    n_li = len(by_base)
    n_shared = sum(1 for d in by_base.values() if d["n_companies"] >= 2)
    return dedent(f"""
    <h2 id="sec-{pat_id}">{pat_id}. {pat_ko}</h2>
    <p style="font-family:monospace;font-size:0.78em;color:#555">substring: <code>{pat}</code></p>
    <p>총 base element {n_li}개 · 2개사 이상 공통 {n_shared}개 · 단위 <b>억원</b> · 별도 기준 · axis-min context</p>
    <div class="table-wrap">
    <table>
      <thead><tr>{th}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>
    """).strip()


def main() -> int:
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    name_map = peer_groups.load_companies()

    print(f"=== P1~P9 패턴별 동업사 수치 추출 ===")
    pattern_data = {}
    pattern_totals = {}  # pat_id -> {cik: {n_li, total, max, min}}
    for pat_id, pat_ko, pat in PATTERNS:
        by_base = fetch_pattern_values(con, pat)
        pattern_data[pat_id] = by_base
        # 회사별 합계 (axis-min)
        pattern_totals[pat_id] = {cik: fetch_pattern_company_total(con, pat, cik) for cik in CIKS}
        n_shared = sum(1 for d in by_base.values() if d["n_companies"] >= 2)
        print(f"  {pat_id} {pat_ko}: {len(by_base)} unique 라벨, "
              f"{n_shared}개 2개사 이상 공통")

    con.close()

    css = extract_css(Path("report/종합보고서_FY2025.html"))
    today = date.today().isoformat()

    # ─── §1 결론 ───
    total_unique = sum(len(d) for d in pattern_data.values())
    total_shared = sum(1 for d in pattern_data.values()
                       for _ in d.values() if _["n_companies"] >= 2)
    s1 = dedent(f"""
    <h2 id="sec-1-결론">1. 검토 결론 — 패턴별 수치 비교</h2>
    <div class="cards">
      <div class="card info">
        <div class="label">분석 패턴</div>
        <div class="num">{len(PATTERNS)}</div>
        <div class="sub">P1~P9 영문 element substring</div>
      </div>
      <div class="card pass">
        <div class="label">총 base element</div>
        <div class="num">{total_unique}</div>
        <div class="sub">prefix 제거된 unique element 합</div>
      </div>
      <div class="card warn">
        <div class="label">2개사 이상 공통</div>
        <div class="num">{total_shared}</div>
        <div class="sub">횡단 비교 가능 라인</div>
      </div>
      <div class="card review">
        <div class="label">자사 단독</div>
        <div class="num">{total_unique - total_shared}</div>
        <div class="sub">미래에셋 또는 1개사만</div>
      </div>
    </div>
    <div class="conclusion">
      <h4>방법</h4>
      <ul>
        <li>매핑 키: <b>element_id에서 prefix(dart_/ifrs-full_/entity{{CIK}}_) 제거된 영문 base_name</b>.
            같은 base는 회사마다 dart 표준 또는 entity 확장이라도 한 라인으로 합쳐 비교.</li>
        <li>분해 깊이 흡수: 회사가 풀어서 보고하면 같은 element_id의 row 중 axis가 가장 적은 것
            (가장 집계된 row)의 amount만 사용. 묶어서 보고하면 그 row 그대로.</li>
        <li>기준: <b>별도(separate)</b> · 단위 <b>억원</b> · 부호 그대로 표시 (양수 = 부채증가, 음수 = 부채감소).</li>
      </ul>
    </div>
    """).strip()

    # ─── §2~§10 패턴별 ───
    sections = [s1]
    for pat_id, pat_ko, pat in PATTERNS:
        # 회사 합계 표 (먼저)
        totals = pattern_totals[pat_id]
        totals_th = "<th></th>" + "".join(f'<th>{name_map[c].name_ko[:5]}</th>' for c in CIKS)
        n_li_row = "<td><b>LineItem (값보유)</b></td>" + "".join(
            f'<td class="{"self" if c == SELF_CIK else ""}" style="text-align:right">'
            f'{totals[c]["n_li"]}</td>' for c in CIKS
        )

        def _fmt(amt):
            return f"{amt/1e8:+,.0f}" if amt is not None else "—"

        total_row = "<td><b>합계 (sum, 억원)</b></td>" + "".join(
            f'<td class="{"self" if c == SELF_CIK else ""}" style="text-align:right">'
            f'{_fmt(totals[c]["total"])}</td>' for c in CIKS
        )
        max_row = "<td>최대 라인 (max)</td>" + "".join(
            f'<td class="{"self" if c == SELF_CIK else ""}" style="text-align:right;color:#888;font-size:0.85em">'
            f'{_fmt(totals[c]["max"])}</td>' for c in CIKS
        )
        min_row = "<td>최소 라인 (min)</td>" + "".join(
            f'<td class="{"self" if c == SELF_CIK else ""}" style="text-align:right;color:#888;font-size:0.85em">'
            f'{_fmt(totals[c]["min"])}</td>' for c in CIKS
        )
        total_summary_html = dedent(f"""
        <p style="margin-top:18px;font-weight:600;color:#1F4E79">회사별 합계 (axis-min 합산, 단위 억원)</p>
        <div class="table-wrap"><table>
          <thead><tr>{totals_th}</tr></thead>
          <tbody>
            <tr>{n_li_row}</tr>
            <tr>{total_row}</tr>
            <tr>{max_row}</tr>
            <tr>{min_row}</tr>
          </tbody>
        </table></div>
        """)

        # 라인별 cross-table (라벨 정확 매칭 기반) — 기존
        line_section = render_pattern_section(
            pat_id, pat_ko, pat, pattern_data[pat_id], name_map)
        # combine: title + total + line section
        # render_pattern_section already includes h2; we'll inject total before its body
        # easiest: replace closing of intro p with our total table
        line_section_with_total = line_section.replace(
            "<div class=\"table-wrap\">",
            total_summary_html + '\n<p style="margin-top:18px;font-weight:600;color:#1F4E79">라인별 비교 (한국어 라벨 정확 일치 기준)</p>\n<div class="table-wrap">',
            1)
        sections.append(line_section_with_total)

    # TOC
    toc = '<div class="toc-container"><div class="toc-toggle" onclick="document.getElementById(\'toc-list\').classList.toggle(\'hidden\')">📑 목차 (P1~P9)</div><div id="toc-list" class="toc-list">'
    toc += '<div class="toc-group"><h4 class="toc-group-title">개요</h4>'
    toc += '<a class="toc-item" href="#sec-1-결론">1. 검토 결론</a></div>'
    toc += '<div class="toc-group"><h4 class="toc-group-title">패턴별 수치 (P1~P9)</h4>'
    for pat_id, pat_ko, _ in PATTERNS:
        n = len(pattern_data[pat_id])
        toc += f'<a class="toc-item" href="#sec-{pat_id}">{pat_id}. {pat_ko} ({n})</a>'
    toc += '</div></div></div>'

    html = dedent(f"""
    <!doctype html>
    <html lang='ko'><head><meta charset='utf-8'>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>P1~P9 패턴별 동업사 수치 비교 (별도, 억원)</title>
    {css}
    </head><body>
      <h1>📊 P1~P9 패턴별 동업사 수치 비교</h1>
      <div class="meta">
        <span>자사: 미래에셋생명 (CIK {SELF_CIK})</span>
        <span>동업사: 8개 IFRS17 풍부 KOSPI 상장</span>
        <span>기준: 별도 · 단위: 억원 · {today}</span>
        <span>분해 깊이: axis-min context 흡수</span>
      </div>
      {toc}
      {''.join(sections)}
      <div class="footer-note">
        build_peer_values_v3.py · base_name (prefix 제거 영문)로 cross-company line item 통합 비교
      </div>
    </body></html>
    """).strip()

    out = Path("report/peer_values_P1_P9.html")
    out.write_text(html, encoding="utf-8")
    print(f"\n✓ wrote {out} ({out.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
