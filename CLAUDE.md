# Peer Company Benchmarking — Claude Code 운영 매뉴얼

> 이 파일은 Claude Code가 매 작업 시 컨텍스트로 받는 프로젝트 메모입니다.
> 상세 설계·로드맵은 [PLAN.md](PLAN.md)를 참조하세요. 이 파일은 **운영 시 매번 필요한 핵심**만 담습니다.

## 1. 프로젝트 한 줄
미래에셋생명 계리결산팀이 DART XBRL 주석 데이터로 동업사(생보사) **부채 항목**을 횡단·시계열 비교해 자사 산출의 적정성을 검증한다.

## 2. 디렉토리 (요점)
```
data/raw/{YEAR}Q{Q}/        # 11개 TSV (원본)
data/ref/                   # companies.csv, peer_groups.yml, liability_items.yml
data/user/                  # 자사 내부 데이터 (.gitignore — 외부 전송 금지)
data/db/benchmark.duckdb    # 적재된 DuckDB
src/                        # 적재·분석·리포트 코드
.claude/agents,skills/      # Claude Code 자산
```

## 3. 데이터 모델 (반드시 기억)
11개 TSV. 사실 테이블은 **`val.tsv`**, 나머지는 차원/계층/라벨/메타.

| 파일 | 역할 | 키 |
|---|---|---|
| sub | 제출 메타 | (CIK, REPORT_DATE) |
| val | **실제 값** | (CIK, REPORT_DATE, ELMT_ID, CONTEXT_ID) |
| cntxt | 컨텍스트 (기간+회사+dimension) | (CIK, REPORT_DATE, CONTEXT_ID) |
| role | 주석 섹션 (D827580 등) | (CIK, REPORT_DATE, ROLE_ID) |
| elmt | 개념 정의 | (ELEMENT_ID, TAXONOMY_ID) |
| lab | 한/영 라벨 | (CIK, REPORT_DATE, ELMT_ID, LANG) |
| pre/def/cal | 표시/차원/계산 계층 | role 단위로 그룹화 |
| txn, txn-dts | taxonomy 메타 | TAXONOMY_ID |

**자주 쓰는 조인 패턴**
```
val JOIN cntxt ON CIK,REPORT_DATE,CONTEXT_ID    -- 기간/dimension 필터
val JOIN lab   ON CIK,REPORT_DATE,ELMT_ID,LANG  -- 사람이 읽을 항목명
val JOIN sub   USING(CIK, REPORT_DATE)          -- 제출 시점 메타
```

## 4. 단위·정규화 (실수 잦은 곳)
- `VALUE`는 문자열로 옴 → 숫자 캐스팅 필요
- `UNIT_ID ∈ {KRW, SHARES, KRWEPS, PURE, USD}` — 통화 항목은 KRW만 비교
- `DECIMALS = -3` → VALUE는 천원 단위 (실제 원 = VALUE × 10³)
- `DECIMALS = -6` → 백만원, `-9` → 십억원
- **적재 시 모두 원 단위 BIGINT로 정규화 권장**. 표시 단계에서 천원/백만원 변환.

## 5. 횡단 비교 가능 여부 판단
- prefix가 `ifrs-full_`, `dart_`, `dart-gcd_`, `ias_*_` → **표준, 횡단 비교 가능**
- prefix가 `entity{CIK}_` → **회사 확장, 횡단 비교 불가** (라벨 매칭으로 후처리)

## 6. 도메인 용어 (보험사 부채)
| 한국어 | 영문 / XBRL prefix 후보 |
|---|---|
| 보험계약부채 | InsuranceContractLiabilities |
| 책임준비금 | (구 K-IFRS) Policy reserves |
| 잔여보장부채 LRC | LiabilityForRemainingCoverage |
| 발생사고부채 LIC | LiabilityForIncurredClaims |
| 보험계약마진 CSM | ContractualServiceMargin |
| 위험조정 RA | RiskAdjustment |
| 최선추정부채 BEL | DiscountedEstimatedFutureCashFlows |
| 사채 | BondsIssued |
| 차입금 | Borrowings |
| 충당부채 | Provisions |
| 이연법인세부채 | DeferredTaxLiabilities |
| 순확정급여부채 | NetDefinedBenefitLiabilityAsset |

## 7. 분석할 때 항상 의식할 것
1. **결산 후 정정 가능** — 분석에 `as-of {SUBMISSION_DATETIME}` 표기 필수
2. **66개사 중 상세 주석 제출은 소수** — 매 분기 데이터 가용성 먼저 확인 후 분석 (스크립트는 부재 시 명확히 경고)
3. **동일 항목이라도 회사별로 다른 dimension(axis/member)으로 보고** — cntxt 풀 비교 필수
4. **자사 내부 데이터는 절대 원격 전송 금지** — `data/user/`는 로컬 전용, .gitignore

## 8. 자주 쓰는 작업 → 어디로 가야 하나
| 하고 싶은 것 | Skill 또는 코드 | 메모 |
|---|---|---|
| 새 분기 zip 적재 | `/ingest-quarter 2026 1` | 미정의 시 `src/ingest.py` |
| 부채 항목 element 찾기 | `/find-item 보험계약부채` | 라벨 기반 검색 |
| 한 분기 횡단 비교 | `/peer-snapshot life-insurers <ELMT> <YYYYQq>` | 표 + bar chart |
| 시계열 추이 | `/peer-trend life-insurers <ELMT>` | line chart |
| 자사값 위치 확인 | `/compare-vs-self my_q1_2026.xlsx` | percentile + 차트 |
| 무결성 점검 | `/validate-data` | 적재 직후 필수 |

## 9. Claude Code 자산 (`.claude/`)
- **Agents**: xbrl-ingester, element-mapper, peer-resolver, benchmark-analyst, report-builder
- **Skills**: ingest-quarter, list-peers, find-item, peer-snapshot, peer-trend, compare-vs-self, validate-data
- 각 정의 파일은 `.claude/agents/{name}.md`, `.claude/skills/{name}.md`. 상세 책임은 PLAN.md §3 참조.

## 10. 코딩 규약
- 언어: Python 3.11+
- 의존: DuckDB, polars, plotly, openpyxl (Excel), uv (env)
- 스타일: 함수형 우선, 부수효과 최소, 단위 KRW(원) 절대값으로 정규화
- 출력: 사용자가 한국어 결과 선호 — 표/차트 라벨 한국어, 코드 주석은 영문 OK
- 보안: `data/user/` 절대 외부 전송 금지, API 키는 환경변수

## 11. 모를 때 먼저 볼 것
1. [PLAN.md](PLAN.md) §1 데이터 모델 / §3 자산 설계 / §6 리스크
2. `XBRL가이드.pdf` — 11 TSV 필드 정의 (원문 스펙)
3. `공시정보활용마당_활용가이드.pdf` — 공시 활용 가이드 (큰 파일, 인덱싱만)
