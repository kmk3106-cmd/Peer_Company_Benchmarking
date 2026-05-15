"""사용자 피드백 반영 보고서 마사지.

1. §3 요약표: 보험수익/보험서비스결과 → 보험서비스수익·보험서비스비용·당기순이익
2. §4 순서: 부채 변동 (BEL/RA/CSM) 먼저 → CSM 절대규모·상각률 뒤로
3. §4-1 (CSM 절대규모) 의 "CSM/보험수익" 컬럼 제거
4. 기술 용어 정리 (DI XXX, axis, Member, Issued 등 → 한국어/제거)
"""
from __future__ import annotations
import re
from pathlib import Path

report = Path("outputs/peer_disclosure_actuarial_analysis_report.html")
html = report.read_text(encoding="utf-8")

# ─── 1. §3 요약표 컬럼 교체 ───
PL_DATA = {
    "미래에셋생명 (자사)": {"수익": 10804, "비용": 8978, "순이익": 1249},
    "삼성생명":           {"수익": 96181, "비용": 84477, "순이익": 16998},
    "한화생명":           {"수익": 51757, "비용": 46799, "순이익": 3133},
    "동양생명":           {"수익": 12245, "비용": 10943, "순이익": 658},
    "삼성화재":           {"수익": 183041, "비용": 162252, "순이익": 16909},
    "현대해상":           {"수익": 141448, "비용": 131415, "순이익": 5611},
    "DB손해보험":         {"수익": 152984, "비용": 138797, "순이익": 15349},
    "한화손해보험":        {"수익": 54960, "비용": 52101, "순이익": 3611},
    "흥국화재":           {"수익": 27010, "비용": 25207, "순이익": 1517},
}

# 헤더 컬럼 교체
html = html.replace(
    "<th>보험수익</th>\n        <th>보험서비스결과</th>",
    "<th>보험서비스수익</th>\n        <th>보험서비스비용</th>\n        <th>당기순이익</th>"
)

# 표 §3-1 row별 교체 (보험수익·보험서비스결과 → 수익·비용·순이익 3컬럼)
old_3_pattern = re.compile(
    r'(<tr[^>]*><th class="left">([^<]+)</th><td>[\d,]+</td><td>[\d,]+</td><td>[\d,]+</td><td>[\d,]+</td>)<td>[\d,]+</td><td>[\d,]+</td>(</tr>)'
)


def repl_row(m):
    full_prefix = m.group(1)
    name = m.group(2).strip()
    suffix = m.group(3)
    if name in PL_DATA:
        d = PL_DATA[name]
        return f"{full_prefix}<td>{d['수익']:,}</td><td>{d['비용']:,}</td><td>{d['순이익']:,}</td>{suffix}"
    return m.group(0)


html = old_3_pattern.sub(repl_row, html, count=9)

# §3 요약 관찰 박스 — "보험수익 대비 보험서비스결과 15.6%" 문구 보완
html = html.replace(
    "2) 자사 보험수익 대비 보험서비스결과 비율 <b>15.6%</b>로 손보 평균(10~12%) 보다 다소 높음. 다만 절대규모는 1,690억으로 작음.",
    "2) 자사 보험서비스비용 (8,978억) / 보험서비스수익 (10,804억) = <b>83.1%</b>. 동업사 손보 평균 89~91% 대비 보수적. 당기순이익 1,249억."
)

# caveat 정리 — element 라벨에서 영문 element_id 제거
html = re.sub(
    r'<div class="caveat">출처: <code>04_financial_numbers\.csv</code>[^<]+context: SeparateMember[^<]+</div>',
    '<div class="caveat">출처: DART XBRL 별도재무제표 기준 FY2025 결산값.</div>',
    html
)


# ─── 2. §4 순서 재배치 ───
# 현재: 4-1 (CSM 절대규모) → 4-2 (상각률) → 4-3 (BEL/RA/CSM 변동)
# 변경: 4-1 (부채구성=BEL/RA/CSM 변동) → 4-2 (CSM 절대규모, /수익 컬럼 제거) → 4-3 (상각률)

# 섹션 추출
# §4 시작 ~ §4 끝 (다음 section 시작 전)
m_sec4_start = html.find('<section>\n  <h2>4. 보험계약부채 및 CSM 분석</h2>')
m_sec4_end = html.find('</section>', m_sec4_start)
sec4 = html[m_sec4_start:m_sec4_end]

# 4-1 (CSM 절대규모) 블록 추출
m_41 = re.search(
    r'(<h3>4-1\. 회사별 CSM 절대규모[^<]*</h3>.*?)(?=<h3>4-2)',
    sec4, re.DOTALL
)
sec_41 = m_41.group(1) if m_41 else ""

# 4-2 (상각률) 블록 추출
m_42 = re.search(
    r'(<h3>4-2\. CSM 상각률[^<]*</h3>.*?)(?=<h3>4-3)',
    sec4, re.DOTALL
)
sec_42 = m_42.group(1) if m_42 else ""

# 4-3 (BEL/RA/CSM 변동) 블록 추출
m_43 = re.search(
    r'(<h3>4-3\. 회사별 CSM 변동 구조.*?)(?=</section>)',
    sec4, re.DOTALL
)
sec_43 = m_43.group(1) if m_43 else ""

# 4-1 (CSM 절대규모) 의 "보험수익" / "CSM/보험수익" 컬럼 제거
sec_41_cleaned = re.sub(
    r'<th>보험수익</th>\s*<th>CSM / 보험수익</th>',
    '',
    sec_41
)
# 데이터 행에서도 마지막 2개 td 제거
sec_41_cleaned = re.sub(
    r'(<tr[^>]*><th class="left">[^<]+</th>(?:<td[^>]*>[^<]+</td>){4})<td[^>]*>[^<]+</td><td[^>]*>[^<]+</td>(</tr>)',
    r'\1\2',
    sec_41_cleaned
)
# 흥국화재 colspan 6 → 4
sec_41_cleaned = sec_41_cleaned.replace('colspan="6" class="na center">DI817300 0 element — 측정 불가 (회사 미공시)', 'colspan="4" class="na center">측정 불가 (회사 미공시)')

# 4-1 관찰 박스 텍스트도 손익 비율 부분 제거
sec_41_cleaned = re.sub(
    r'<br>\s*3\) 자사 CSM/보험수익 [^<]+— 보험수익이 작은 회사일수록 CSM 잔액 대비 보험수익 회전이 느리게 보임\.',
    '',
    sec_41_cleaned
)

# 새 순서: 4-1 = 기존 4-3 (BEL/RA/CSM 변동) 으로 번호 갱신
new_41 = sec_43.replace("4-3. 회사별 CSM 변동 구조 (실측)", "4-1. 보험계약부채 변동 구성 — BEL · RA · CSM")
new_41 = new_41.replace("표 4-3. 보험계약부채 변동 — 컴포넌트별", "표 4-1. 보험계약부채 변동 — 구성요소별")
new_41 = new_41.replace("4-3-A. BEL (현금흐름 최선추정치) 변동", "4-1-A. BEL (현금흐름 최선추정치) 변동")
new_41 = new_41.replace("표 4-3-A.", "표 4-1-A.")
new_41 = new_41.replace("4-3-B. RA (위험조정) 변동", "4-1-B. RA (위험조정) 변동")
new_41 = new_41.replace("표 4-3-B.", "표 4-1-B.")
new_41 = new_41.replace("4-3-C. CSM (보험계약마진) 변동", "4-1-C. CSM (보험계약마진) 변동")
new_41 = new_41.replace("표 4-3-C.", "표 4-1-C.")
new_41 = new_41.replace("<b>4-3 관찰</b>", "<b>4-1 관찰</b>")

# 4-2 = 기존 4-1 (CSM 절대규모, /수익 제거)
new_42 = sec_41_cleaned.replace("4-1. 회사별 CSM 절대규모 및 부채 대비 비율", "4-2. CSM 절대규모 및 보험계약부채 대비 비율")
new_42 = new_42.replace("표 4-1.", "표 4-2.")
new_42 = new_42.replace("<b>4-1 관찰</b>", "<b>4-2 관찰</b>")

# 4-3 = 기존 4-2 (CSM 상각률)
new_43 = sec_42.replace("4-2. CSM 상각률", "4-3. CSM 상각률")
new_43 = new_43.replace("표 4-2.", "표 4-3.")

new_sec4_body = new_41 + new_42 + new_43

# §4 본문 교체
sec4_header = '<section>\n  <h2>4. 보험계약부채 및 CSM 분석</h2>\n\n  '
html = html[:m_sec4_start] + sec4_header + new_sec4_body + html[m_sec4_end:]


# ─── 3. 기술 용어 정리 (전역 일괄) ───
TERM_REPLACEMENTS = [
    # DI 코드 → 일반 표현 (caveat 외에는 노출 X)
    ("DI817100/105 IFRS17 §103 변동표 행 × <code>InsuranceContractsByComponentsAxis</code> 컬럼 (BEL/RA/CSM) 셀",
     "보험계약부채 변동공시 구성요소별 (BEL/RA/CSM) 합계"),
    ("DI817100 변동 line 공시 보유 매트릭스 (생보 4사 + 손보 4사, 흥국화재 제외)",
     "보험계약부채 변동공시 라인 보유 현황 (생보 4사 + 손보 4사, 흥국화재 제외)"),
    ("DI817105", "보험계약부채 잔액공시"),
    ("DI817300", "보험계약 정보공시"),
    ("DI817100", "보험계약부채 변동공시"),
    ("DI820000", "사업비 공시"),
    ("DI859005", "이익잉여금처분 공시"),
    ("DI859100", "이익잉여금 공시"),
    ("DI859105", "이익잉여금 잔액공시"),
    # 횡단비교 등
    ("횡단비교", "동업사 비교"),
    ("횡단 비교", "동업사 비교"),
    # axis 용어 본문 내 제거 — caveat 의 code 는 유지
    ("axis-min", "별도기준 합산"),
    ("axis-min context 합산", "별도기준 합산"),
    # Issued / Held 등 (본문)
    (" Issued ", " 발행 "),
    (" Held ", " 보유 "),
]

for old, new in TERM_REPLACEMENTS:
    html = html.replace(old, new)


# 5. 변동표 분석 (DI817100) → 보험계약부채 변동 검증
html = html.replace(
    "<h2>5. 변동표 분석 (DI817100)</h2>",
    "<h2>5. 보험계약부채 변동 검증·매트릭스</h2>"
)

# 표 5-1 caption
html = html.replace(
    "표 5-1. 보험계약부채 변동 검증식 (FY2025 별도, 억원)",
    "표 5-1. 보험계약부채 변동 검증식 (기시 + 변동 = 기말, FY2025 별도, 억원)"
)


report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
