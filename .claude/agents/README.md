# 동업사 비교검증 파이프라인 (10-Agent Chain)

> 100% 정확한 비교는 불가능. 목표는 **70% 자동검증 / 20% WARNING / 10% 수기확인** 3분류.

## 파이프라인 흐름

```
원천공시 (DART XBRL + 사업보고서 원본)
        ↓
   ① full-note-category-scanner          ← 주석 카테고리 전체 영역 스캔 (누락 0)
        ↓
   ② separate-disclosure-filter           ← 별도 vs 연결 필터 (별도만 통과)
        ↓
   ③ reinsurance-exclusion-checker        ← 재보험 제외 (원수만 통과)
        ↓
   ④ xbrl-taxonomy-mapper                 ← element_id·라벨 → 표준 항목 매핑
        ↓
   ⑤ financial-number-extractor           ← 수치 추출 (단위·부호 정규화)
        ↓
   ⑥ movement-table-normalizer            ← 변동표 정규화 + (기시+총변동=기말) 검증
        ↓
   ⑦ product-segmentation-classifier      ← 상품군 5분류 (사망/건강/연금/저축/기타)
        ↓
   ⑧ peer-comparison-validator            ← 회사간 비교 + 검증등급 부여
        ↓
   ⑨ disclosure-gap-analyzer              ← NOT_COMPARABLE/FAIL 원인 분류 + 개선안
        ↓
   ⑩ actuarial-report-writer              ← 계리결산팀 보고서 작성
```

## 70/20/10 목표 분포

각 stage의 출력 fact 또는 비교 단위를 다음 3분류로:

| 분류 | 비율 | 의미 | 처리 |
|---|---|---|---|
| **PASS (auto)** | ~70% | 검증식 통과·매핑 EXACT/SIMILAR·구조 일치 | 자동 비교 결과 채택 |
| **WARNING (semi-auto)** | ~20% | INFERRED 매핑·소소한 단위/round-off 불일치 | caveat 표시 후 비교 |
| **REVIEW (manual)** | ~10% | NOT_COMPARABLE·FAIL·OUT_OF_SCOPE | 별도 예외테이블 → 수기 확인 |

이 비율은 stage별 누적되어 최종 단계(peer-comparison-validator)에서 측정.

## 예외테이블 (Exception Store)

각 에이전트는 PASS 못한 항목을 **공통 예외테이블**에 누적:

| 컬럼 | 의미 |
|---|---|
| `pipeline_stage` | 어느 에이전트에서 발생 (1~10) |
| `company_name` | 회사명 |
| `note_category` | 주석 카테고리 (role_id) |
| `item_name` | 항목명 |
| `exception_type` | WARNING / REVIEW |
| `exception_code` | 세부 코드 (예: `MAPPING_INFERRED`, `UNIT_AMBIGUOUS`, `NO_DISCLOSURE`) |
| `description` | 현상 설명 |
| `suggestion` | 개선 제안 (disclosure-gap-analyzer 산출) |
| `created_at` | 검출 시각 |

저장 위치 (제안): `data/db/benchmark.duckdb` 의 `exceptions` 테이블.

## 단계별 입출력 인터페이스

### Stage 1: full-note-category-scanner
- **In**: 카테고리 식별자 (role_id, 예: DI817100), 회사 list
- **Out**: 영역별 row (section_type, has_number, usable_for_comparison)
- **PASS**: usable=Y / **WARNING**: usable=CHECK / **REVIEW**: usable=N

### Stage 2: separate-disclosure-filter
- **In**: Stage 1 출력
- **Out**: include_yn 부여된 row
- **PASS**: include=Y (별도 확인) / **WARNING**: include=CHECK (연결/별도 모호) / **REVIEW**: include=N

### Stage 3: reinsurance-exclusion-checker
- **In**: Stage 2 통과분
- **Out**: insurance_basis 분류 (ORIGINAL/REINSURANCE_HELD/MIXED)
- **PASS**: ORIGINAL / **WARNING**: MIXED / **REVIEW**: REINSURANCE_HELD 또는 UNKNOWN

### Stage 4: xbrl-taxonomy-mapper
- **In**: Stage 3 통과분 + 표준 사전
- **Out**: standard_item_name + mapping_grade 부여
- **PASS**: EXACT/SIMILAR / **WARNING**: INFERRED / **REVIEW**: UNMAPPED, OUT_OF_SCOPE

### Stage 5: financial-number-extractor
- **In**: Stage 4 매핑 결과
- **Out**: raw amount + normalized + role + product_group + confidence
- **PASS**: confidence=HIGH / **WARNING**: MEDIUM / **REVIEW**: LOW or 단위 모호

### Stage 6: movement-table-normalizer
- **In**: Stage 5 fact 들 (변동표 단위)
- **Out**: 검증식 결과 (기시+총변동=기말)
- **PASS**: |diff| < 1억 / **WARNING**: |diff| < 총변동 5% / **REVIEW**: ≥ 5%

### Stage 7: product-segmentation-classifier
- **In**: Stage 5/6 결과
- **Out**: standardized_product_group + confidence
- **PASS**: confidence=HIGH / **WARNING**: MEDIUM / **REVIEW**: 미분류 또는 LOW

### Stage 8: peer-comparison-validator
- **In**: Stage 6/7 결과 + 회사 list
- **Out**: validation_result (PASS/WARNING/FAIL/NOT_COMPARABLE/OUT_OF_SCOPE)
- **70/20/10 측정 지점**: 여기서 누적 분류율 산출

### Stage 9: disclosure-gap-analyzer
- **In**: Stage 8 의 NOT_COMPARABLE/FAIL 항목
- **Out**: issue_type + impact_level + improvement_suggestion
- 예외테이블에 누적 → 다음 분기에 매핑 사전·전처리 룰 보강 입력

### Stage 10: actuarial-report-writer
- **In**: Stage 8 + 9 결과
- **Out**: 5-섹션 마크다운 보고서 (결론/현황/주요발견/한계/개선방안)
- 70/20/10 분포 수치를 보고서 §1 검토결론에 명시

## 운영 모드

### 모드 A: 신규 동업사 적재 후 (전체 파이프라인 실행)
Stage 1~10 순차 실행. 한 회사씩 또는 batch.

### 모드 B: 분기 정기 비교 (스냅샷)
이전 매핑 사전 재사용 가능. Stage 4 의 매핑은 캐시 활용, Stage 5~10 신규 실행.

### 모드 C: 특정 이슈 진단 (회사 1개 deep-dive)
Stage 1, 8, 9 만 실행. 어느 라인이 왜 다른지 원인 분석에 집중.

## 자동화 정착 후 기대값

- **자동검증 70%** — XBRL element 표준 + axis 표준이 일치하는 fact
- **WARNING 20%** — entity 확장 매핑·단위 round-off·INFERRED 매핑
- **수기확인 10%** — 회사별 disclosure 정책 차이 (예: 미래에셋 보험수익 axis 차이), 비표준 라인

이 비율을 분기마다 측정해서 매핑 사전 보강 효과를 추적.

## 호출 예시

```
Agent(subagent_type="full-note-category-scanner",
      prompt="DI817100 에 대해 11개 KOSPI 보험사 모두 카테고리 전체 영역 스캔. ...")

# → 결과로 section list 받음

Agent(subagent_type="xbrl-taxonomy-mapper",
      prompt="위 section 들 중 standard 매핑 필요한 element_id 만 추려서 ...")

# 단계별 chain ...
```

## 참고
- 표준 사전: `data/ref/liability_items.yml`
- 미래에셋 표준 사례: `memory/mirae_di817100_structure.md`, `memory/product_axis_mapping.md`
- 표시 규칙: `memory/feedback_disclosure_format.md` (LRC/LIC 분리, 손실요소 합산, 5상품군, 기초→기말 순서)
- 별도 룰: `memory/separate_only_rule.md` (사용자 결정 2026-05-13)
