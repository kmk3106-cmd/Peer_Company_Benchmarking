"""종합보고서_FY2025.html 마스터 재빌드 orchestrator.

12개 커밋이 누적된 단계를 순서대로 idempotent하게 재실행한다.

순서:
  1. build_final_report.py        — base 보고서 (§1~§5-F)
  2. append_lines_assumptions.py  — §5-G (라인 행렬) + §6 (IFRS17 가정)
  3. update_report_v3.py          — §5-G 잔액 + §5-F 연도 + §5-H 사업비
  4. update_report_v5.py          — §5-I 예실차 + §5-J CSM 무브먼트
  5. add_toc.py                   — TOC + "맨위로" 버튼
  6. tidy_toc.py                  — 5.1~5.10 numbering 통일, 3그룹 그리드
  7. add_assumption_sections.py   — §5.11 계리적 가정 + §5.12 CSM 상각률
  8. replace_section_511.py       — §5.11 정확 데이터 교체 (유추 금지 룰)
  9. update_511_with_tabs.py      — §5.11 8개사 회사 탭 selector

Usage:
  python scripts/rebuild_report.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
STEPS = [
    "scripts/build_final_report.py",
    "scripts/append_lines_assumptions.py",
    "scripts/update_report_v3.py",
    "scripts/update_report_v5.py",
    "scripts/add_toc.py",
    "scripts/tidy_toc.py",
    "scripts/add_assumption_sections.py",
    "scripts/replace_section_511.py",
    "scripts/update_511_with_tabs.py",
]


def main() -> int:
    target = REPO / "report" / "종합보고서_FY2025.html"
    print(f"target: {target}")
    print(f"steps: {len(STEPS)}")
    print()

    for i, step in enumerate(STEPS, 1):
        path = REPO / step
        if not path.exists():
            print(f"[{i}/{len(STEPS)}] SKIP (missing): {step}")
            continue
        print(f"[{i}/{len(STEPS)}] running {step} ...")
        result = subprocess.run(
            [sys.executable, str(path)],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        # Show last 3 lines of stdout
        if result.stdout:
            tail = "\n".join(result.stdout.strip().splitlines()[-3:])
            for line in tail.splitlines():
                print(f"    {line}")
        if result.returncode != 0:
            print(f"    FAILED (exit {result.returncode})")
            if result.stderr:
                err_tail = "\n".join(result.stderr.strip().splitlines()[-5:])
                for line in err_tail.splitlines():
                    print(f"    ERR: {line}")
            return result.returncode

    print()
    if target.exists():
        size_kb = target.stat().st_size / 1024
        print(f"✓ done. {target.relative_to(REPO)} ({size_kb:,.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
