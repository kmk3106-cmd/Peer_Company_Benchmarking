"""보고서 마사지 v2 — 안전한 string slicing 기반.

1. §3 요약표 컬럼 교체
2. §4 순서 재배치 (4-3 BEL/RA/CSM → 4-1, 기존 4-1·4-2 → 4-2·4-3)
3. §4-1(새) 의 보험수익/CSM/수익 컬럼 제거 (이제 4-2)
4. 기술 용어 정리
"""
from __future__ import annotations
import re
from pathlib import Path

report = Path("outputs/peer_disclosure_actuarial_analysis_report.html")
html = report.read_text(encoding="utf-8")

# ─── 1. §3 요약표 ───
# 헤더 컬럼 교체 (보험수익·보험서비스결과 → 보험서비스수익·보험서비스비용·당기순이익)
html = html.replace(
    "<th>보험수익</th>\n        <th>보험서비스결과</th>",
    "<th>보험서비스수익</th>\n        <th>보험서비스비용</th>\n        <th>당기순이익</th>"
)

# 9개 회사 data row 교체 — 정확한 회사명 매칭
PL_DATA = {
    "미래에셋생명 (자사)": ("10,804", "8,978", "1,249"),
    "삼성생명":           ("96,181", "84,477", "16,998"),
    "한화생명":           ("51,757", "46,799", "3,133"),
    "동양생명":           ("12,245", "10,943", "658"),
    "삼성화재":           ("183,041", "162,252", "16,909"),
    "현대해상":           ("141,448", "131,415", "5,611"),
    "DB손해보험":         ("152,984", "138,797", "15,349"),
    "한화손해보험":        ("54,960", "52,101", "3,611"),
    "흥국화재":           ("27,010", "25,207", "1,517"),
}

# §3 표는 한 줄에 row 작성됨. 각 회사 row 단순 패턴:
# <tr...><th class="left">회사명</th><td>NUM</td>x4 + <td>NUM</td><td>NUM</td>  </tr>
# 마지막 2개 td(보험수익·보험서비스결과)를 3개 td(보험서비스수익·비용·순이익)으로 교체

for name, (rev, exp, profit) in PL_DATA.items():
    # 패턴: 회사명 다음 4개 td 그대로 + 마지막 2개 td 교체
    pat = re.compile(
        re.escape('<th class="left">' + name + '</th>') +
        r'((?:<td>[\d,]+</td>){4})' +
        r'<td>[\d,]+</td><td>[\d,]+</td>'
    )
    html = pat.sub(
        rf'<th class="left">{name}</th>\1<td>{rev}</td><td>{exp}</td><td>{profit}</td>',
        html
    )

# §3 관찰 박스 텍스트 수정
html = html.replace(
    "2) 자사 보험수익 대비 보험서비스결과 비율 <b>15.6%</b>로 손보 평균(10~12%) 보다 다소 높음. 다만 절대규모는 1,690억으로 작음.",
    "2) 자사 보험서비스비용 8,978억 / 보험서비스수익 10,804억 = <b>83.1%</b>. 동업사 손보 평균 89~91% 대비 낮음 (보수적). 당기순이익 1,249억."
)

# §3 caveat 정리
html = re.sub(
    r'<div class="caveat">출처: <code>04_financial_numbers\.csv</code>[^<]*<code>[^<]+</code>[^<]+</div>',
    '<div class="caveat">출처: DART XBRL 별도재무제표 기준 FY2025 결산값.</div>',
    html
)


# ─── 2. §4 순서 재배치 ───
# anchor 위치 확보
idx_4_h2 = html.find('<h2>4. 보험계약부채 및 CSM 분석</h2>')
idx_4_1 = html.find('<h3>4-1. 회사별 CSM 절대규모', idx_4_h2)
idx_4_2 = html.find('<h3>4-2. CSM 상각률', idx_4_1)
idx_4_3 = html.find('<h3>4-3. 회사별 CSM 변동 구조', idx_4_2)
idx_4_3_end = html.find('</section>', idx_4_3)

block_41 = html[idx_4_1:idx_4_2]
block_42 = html[idx_4_2:idx_4_3]
block_43 = html[idx_4_3:idx_4_3_end]

# 새 §4-1 = 기존 §4-3 (BEL/RA/CSM 변동)
new_41 = (block_43
    .replace("4-3. 회사별 CSM 변동 구조 (실측)", "4-1. 보험계약부채 변동 — 구성요소별 (BEL · RA · CSM)")
    .replace("표 4-3. 보험계약부채 변동 — 컴포넌트별", "표 4-1. 보험계약부채 변동 — 구성요소별")
    .replace("4-3-A. BEL", "4-1-A. BEL")
    .replace("표 4-3-A.", "표 4-1-A.")
    .replace("4-3-B. RA", "4-1-B. RA")
    .replace("표 4-3-B.", "표 4-1-B.")
    .replace("4-3-C. CSM", "4-1-C. CSM")
    .replace("표 4-3-C.", "표 4-1-C.")
    .replace("<b>4-3 관찰</b>", "<b>4-1 관찰</b>"))

# 새 §4-2 = 기존 §4-1 (CSM 절대규모) — 보험수익/CSM/수익 컬럼 제거
new_42 = (block_41
    .replace("4-1. 회사별 CSM 절대규모 및 부채 대비 비율", "4-2. CSM 절대규모 및 보험계약부채 대비 비율")
    .replace("표 4-1.", "표 4-2.")
    .replace("<b>4-1 관찰</b>", "<b>4-2 관찰</b>"))

# 보험수익 / CSM/보험수익 헤더 제거
new_42 = new_42.replace(
    "<th>보험수익</th>\n        <th>CSM / 보험수익</th>",
    ""
).replace(
    "<th>보험수익</th>\n        <th>CSM / 보험수익</th>\n",
    ""
)

# 데이터 행에서 마지막 2개 td 제거 (보험수익·CSM/수익)
new_42 = re.sub(
    r'(<tr[^>]*>\s*<th class="left">[^<]+</th>(?:<td[^>]*>[^<]+</td>){4})\s*<td[^>]*>[^<]+</td>\s*<td[^>]*>[^<]+</td>\s*(</tr>)',
    r'\1\2',
    new_42
)
# 흥국화재 colspan 6 → 4
new_42 = re.sub(
    r'colspan="6"\s+class="na center">DI817300[^<]+',
    'colspan="4" class="na center">측정 불가 (회사 미공시)',
    new_42
)

# 4-2 관찰박스: 3번째 점(CSM/보험수익) 제거
new_42 = re.sub(
    r'<br>\s*3\) 자사 CSM/보험수익 [^<]+회전이 느리게 보임\.',
    '',
    new_42
)

# 새 §4-3 = 기존 §4-2 (CSM 상각률)
new_43 = (block_42
    .replace("4-2. CSM 상각률 (annualized run-off rate)", "4-3. CSM 상각률")
    .replace("표 4-2.", "표 4-3."))

# §4 전체 본문 재구성
sec4_header_end = html.find('<h3>4-1', idx_4_h2)
new_sec4_body = new_41 + new_42 + new_43

# 교체
html = html[:sec4_header_end] + new_sec4_body + html[idx_4_3_end:]


# ─── 3. 기술 용어 정리 ───
TERM_REPLACEMENTS = [
    # caveat 안의 element/role 표시
    ("DI817100/105 IFRS17 §103 변동표 행 × <code>InsuranceContractsByComponentsAxis</code> 컬럼 (BEL/RA/CSM) 셀.", "보험계약부채 변동공시 구성요소별 (BEL/RA/CSM) 합계."),
    ("DI817105 「당기서비스 관련 변동(IncreaseDecreaseThroughChangesThatRelateToCurrentService)」 행 × InsuranceContractsByComponents = CSM 컬럼",
     "「당기서비스 관련 변동」 행 × CSM 컬럼"),
    ("DI817100 변동 line 공시 보유 매트릭스 (생보 4사 + 손보 4사, 흥국화재 제외)",
     "보험계약부채 변동공시 라인 보유 현황 (생보 4사 + 손보 4사, 흥국화재 제외)"),
    ("DI817100", "보험계약부채 변동공시"),
    ("DI817105", "보험계약부채 잔액공시"),
    ("DI817300", "보험계약 정보공시"),
    ("DI820000", "사업비 공시"),
    ("DI859005", "이익잉여금처분 공시"),
    ("DI859100/105", "이익잉여금 잔액공시"),
    ("DI859100", "이익잉여금 공시"),
    ("DI859105", "이익잉여금 잔액공시"),
    # 횡단비교 → 동업사 비교
    ("횡단비교", "동업사 비교"),
    ("횡단 비교", "동업사 비교"),
    ("6대 핵심 BS·IS 수치 횡단 비교", "동업사 BS·IS 핵심 수치 비교"),
    # 기술 용어
    ("axis-min", "별도 합산"),
    ("axis-min context 합산", "별도기준 합산"),
    ("8개 주석 role 보유 매트릭스", "8개 주석 공시 보유 현황"),
    ("10개 핵심 element 보유 매트릭스 (Disclosure Gap)", "핵심 항목 보유 현황 (공시 격차)"),
    ("Disclosure Gap", "공시 격차"),
    # 변동표 분석 → 보험계약부채 변동 검증
    ("<h2>5. 변동표 분석 (DI817100)</h2>", "<h2>5. 보험계약부채 변동 검증·라인 보유 매트릭스</h2>"),
    ("<h2>5. 변동표 분석 (보험계약부채 변동공시)</h2>", "<h2>5. 보험계약부채 변동 검증·라인 보유 매트릭스</h2>"),
    # 영문 표현 한국어
    ("(annualized run-off rate)", ""),
]
for old, new in TERM_REPLACEMENTS:
    html = html.replace(old, new)

# code 태그 안의 element_id (일부 caveat) 정리 — caveat 내 영문 element 노출 줄임
html = re.sub(
    r'<code>ifrs-full_InsuranceContractsIssuedThatAreLiabilities[^<]+</code>',
    '<code>보험계약부채 관련 표준 항목</code>',
    html
)

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
