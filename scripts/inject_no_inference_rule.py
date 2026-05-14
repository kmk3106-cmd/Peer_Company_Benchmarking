"""모든 .claude/agents/*.md 파일에 '유추 금지 룰' 일괄 삽입."""
from __future__ import annotations
from pathlib import Path

RULE_BLOCK = """
## ⚠️ 절대 룰 — 추정·유추 금지

사용자가 명명한 정확한 데이터(예: "계리적가정에 의한 보험부채 변동내역")를 요청하면 **반드시 정확 search** 로 진행:

1. `lab_insurers.LABEL LIKE '%정확한 키워드%'` 또는 원본 `lab-ko.xml` grep 으로 element 찾기
2. 발견된 entity 확장 element (`entity{CIK}_...`) 만 사용
3. **비슷한 element로 유추 매핑 금지** (예: '할인률·금융가정 변경' element로 '계리적가정 변동내역' 대신 보고 X)
4. `pre_insurers.PARENT_ELEMENT_ID` 로 표의 자식 element 트리 walk
5. 미공시 시 "해당 회사 미공시"라 명시 — 유사 element로 대체 보고 절대 금지
6. 보고서·결과물에 사용한 element_id 출처 명시 (감사 추적성)

위반 시: 보고서 신뢰성 훼손 → 즉시 정정 + 메모리 `feedback_no_inference.md` 참조.

"""

for agent_file in sorted(Path(".claude/agents").glob("*.md")):
    if agent_file.name == "README.md":
        continue
    text = agent_file.read_text(encoding="utf-8")
    if "절대 룰 — 추정·유추 금지" in text:
        print(f"  [SKIP] {agent_file.name} — 이미 룰 포함")
        continue
    # frontmatter 끝나는 곳 (다음 ---) 직후에 RULE_BLOCK 삽입
    parts = text.split("---", 2)
    if len(parts) >= 3:
        new_text = "---" + parts[1] + "---\n" + RULE_BLOCK + parts[2]
        agent_file.write_text(new_text, encoding="utf-8")
        print(f"  [INJECT] {agent_file.name}")
    else:
        print(f"  [SKIP] {agent_file.name} — frontmatter 없음")
