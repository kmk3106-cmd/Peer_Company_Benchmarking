# Peer Company Benchmarking — 개발 플랜

> **사용자**: 미래에셋생명 계리결산팀 팀장
> **목적**: DART XBRL 주석 데이터를 활용해 동업사(생보사) 부채 항목을 횡단·시계열 비교하여 당사 데이터 산출의 적정성을 검증
> **작성일**: 2026-05-12

---

## 0. 데이터 실측 결과 (2025 4Q 사업연도 보고서 기준 — Decision Point #1 해소)

### 0.1 두 zip의 규모 비교
| 항목 | 2026 1Q | 2025 4Q (사업연도) |
|---|---|---|
| zip 크기 | 54 MB | **546 MB** (10x) |
| 압축 해제 합계 | ~870 MB | **~13 GB** |
| 제출 법인 수 (sub.tsv) | 66개사 | **3,018개사** |
| 상세 주석 (>100 roles) 제출 | 1개사 | **1,134개사** |
| 표준 본문만 (16~19 roles) | 65개사 | 1,312개사 |

→ **사업연도 보고서가 메인 데이터셋**. 분기 보고서는 추세·격차 검증용 보조.

### 0.2 KOSPI 상장 보험사 11개사 (사용자 확정 — 자사 + 동업사 10개)
보험계약부채 관련 표준 role(`DI817xxx`, `DI818xxx`)을 제출한 CIK 11개를 회사명 매핑 완료. 사용자 결정: **KOSPI 상장 보험사 통합 비교** (비상장 7개사 — 교보·신한라이프·농협·KB라이프·흥국생명·KDB·DB생명 — 는 DART XBRL 미제출이므로 제외).

| CIK | 회사 | 분류 | 전체 roles | 보험 roles |
|---|---|---|---|---|
| 00112332 | **미래에셋생명** ★ | 생명 | 403 | 98 |
| 00126256 | 삼성생명 | 생명 | 539 | 150 |
| 00113058 | 한화생명 | 생명 | 570 | 154 |
| 00117267 | 동양생명 | 생명 | 528 | 174 |
| 00139214 | 삼성화재 | 손해 | 499 | 138 |
| 00164973 | 현대해상 | 손해 | 481 | 156 |
| 00159102 | DB손해보험 | 손해 | 463 | 121 |
| 00135917 | 한화손해보험 | 손해 | 435 | 116 |
| 00113562 | 롯데손해보험 | 손해 | 284 | 75 |
| 00103176 | 흥국화재 | 손해 | 199 | 55 |
| 00113191 | 코리안리 | 재보험 | 534 | 178 |

→ `data/ref/companies.csv` 매핑 완료, `data/ref/peer_groups.yml`에 4개 그룹 정의(`all_insurers`, `life`, `non_life`, `reinsurance`).

**분석 전략**:
- **핵심 비교군**: 생명보험 4개사 (자사 포함) — IFRS17 CSM·LRC 중심, 직접 비교
- **시장 컨텍스트**: 11개사 분포에서 자사 percentile — 전체 보험업 시장 위치 파악
- **손보·재보험**: 사업모델 차이로 직접 비교 부적합 — 별도 섹션, 같은 도표 혼합 금지

### 0.3 핵심 IFRS17 보험 role 코드 식별 완료
| 코드 | 한국어 라벨 (대표) |
|---|---|
| `DI817100` | 보험계약부채(자산)의 변동 |
| `DI817105` | 보험계약부채(자산) |
| `DI817200` | 재보험계약자산부채의 변동 |
| `DI817205` | 재보험계약자산부채 |
| `DI817300` | 보험계약의 정보 / 신계약 |
| `DI817305` | 신계약인식효과 / 보험계약마진 만기분석 |
| `DI818100/105` | 보험계약 위험관리 |

→ `liability_items.yml` 초기 사전을 이 role 코드 + 산하 element로 구성.

### 0.4 시급 후속 작업
1. **11개 CIK ↔ 회사명 매핑** (DART Open API `corpCode.xml` 또는 val.tsv의 `dart-gcd_EntityRegistrantName` 추출)
2. **미래에셋생명 CIK 식별** — 11개 안에 있는지 확인
3. **생보 vs 손보 분리** — 11개에 둘 다 섞여 있음. 사용자 관심사(생보)로 좁히기

### Decision Point #1 (재정의 — 데이터 전략)
~~A: XBRL only / B: 수기 fallback~~ → **해소**. 2025 4Q XBRL이 충분히 풍부하므로 **A안 확정**. B안(수기 파싱)은 불필요.

대신 새 결정 필요:
- **D1-a**: 2025 4Q만 우선 처리(빠른 v1) vs 2023 Q3 ~ 2025 Q4 전체 적재(시계열 4년치, 디스크 ~40GB)
- **D1-b**: 분기 보고서(1·2·3분기)는 부실 — 적재 대상에서 제외할지 아니면 본문 재무제표만이라도 적재할지

---

## 1. 데이터 모델 (확인 완료)

### 1.1 11개 TSV 관계 요약
```
sub          ── 제출 메타 (CIK, REPORT_DATE)
  ├─ txn         ── 회사별 taxonomy 정의
  │   └─ txn-dts ── taxonomy 간 import 관계
  ├─ role        ── 주석 섹션 목차 (예: D827580 우발부채와 약정사항)
  │   ├─ pre        ── 섹션 내 표시 계층
  │   ├─ def        ── 다차원 정의 (axis/member)
  │   └─ cal        ── 합산 관계 (재무제표 본문에만 적용)
  ├─ elmt        ── 모든 XBRL 개념 정의
  │   └─ lab        ── 한/영 라벨
  └─ val         ── ★ 실제 값 (CIK + ELEMENT + CONTEXT + UNIT + DECIMALS + VALUE)
      └─ cntxt   ── 컨텍스트 = 기간 + 회사 + dimension 조합
```

### 1.2 핵심 결합 키
- **(CIK, REPORT_DATE)**: 한 회사·한 결산일 식별
- **(ELEMENT_ID, TAXONOMY_ID)**: 한 개념(계정과목/항목)
- **CONTEXT_ID**: 한 사실의 기간 + dimension 조합 (보고서 본 칸/주석 표의 한 셀에 해당)
- 단위 처리: `UNIT_ID=KRW`, `DECIMALS=-3` → 천원 단위. `DECIMALS=-6` → 백만원. 계산 시 정규화 필수.

### 1.3 표준 vs 회사 확장 (Cross-company 비교의 핵심 제약)
- 표준 prefix: `ifrs-full_*`, `dart_*`, `dart-gcd_*`, `ias_*` → **횡단 비교 가능**
- 회사 확장: `entity{CIK}_*` → 회사별 사용자 정의 → **횡단 비교 불가**
- **분석 우선순위**: 항상 표준 element부터 보고, 회사 확장은 따로 라벨 매핑해야 함.

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 6  Reporting / UI                                    │
│  - Streamlit dashboard or Excel exporter or Jupyter         │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  Layer 5  Analysis Engine                                   │
│  - Cross-section (peers × same item × same period)          │
│  - Time-series (one item × one company × quarters)          │
│  - Ratio (부채/자본, 부채/자산 등)                            │
│  - Anomaly: 당사 값의 peer 분포상 percentile                  │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  Layer 4  Domain Mapping                                    │
│  - liability_items.yml: 관심 부채 항목 사전 (k-ifrs 기준)     │
│  - peer_groups.yml: 동업사 그룹 정의                         │
│  - companies.csv: CIK ↔ 회사명 ↔ 업종                       │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  Layer 3  Database (DuckDB 단일 파일)                       │
│  - 11개 TSV를 분기별로 적재, REPORT_DATE 키로 union          │
│  - Materialized view: peer × item × period                  │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  Layer 2  Ingestion                                         │
│  - zip → unzip → TSV → DuckDB COPY                          │
│  - 인코딩(UTF-8), DECIMALS 정규화                            │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  Layer 1  Raw Storage                                       │
│  - data/raw/{YEAR}Q{Q}/*.tsv                                │
│  - data/ref/companies.csv (DART Open API)                   │
│  - data/user/my_company_{YYYY}Q{Q}.xlsx (자사 내부 산출)    │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 기술 스택 (확정)
| 영역 | 선택 |
|---|---|
| DB | **DuckDB** (단일 파일, 무서버, GB급 TSV COPY 빠름) |
| 처리 | **polars** (대용량 stream/lazy, val.tsv 2.93GB 처리) |
| 시각화 | **plotly** (HTML interactive, 향후 웹 임베드 용이) |
| 리포트 출력 | **openpyxl** (Excel) + **plotly.io.write_html** |
| 패키지 관리 | **uv** (빠르고 Windows 친화적) |
| 향후 통합 후보 | FastAPI/Flask (계리포탈 REST endpoint) |

### **Decision Point #2 (확정)**: Excel + plotly HTML + **library-first 아키텍처**

향후 **계리포탈 연동 목적**이 있으므로 단순 스크립트가 아닌 **재사용 가능한 라이브러리 구조**로 작성:

```
src/
├── analysis/          # 핵심 비즈니스 로직 — UI 종속 X
│   ├── cross_section.py    # 함수 입력=인자/DataFrame, 출력=DataFrame/dict
│   ├── time_series.py
│   ├── ratios.py
│   └── measurement_model.py  # IFRS17 GMM/VFA/PAA 분해
├── domain/            # 도메인 매핑
│   ├── peer_groups.py
│   └── liability_mapping.py
├── render/            # ★ View layer — 비즈니스 로직 절대 금지
│   ├── excel.py            # openpyxl 출력
│   └── plotly_html.py      # plotly HTML 출력
└── api/               # (선택) 향후 계리포탈 endpoint
    └── endpoints.py        # FastAPI router (v2)
```

**원칙**:
- 모든 `analysis/*` 함수는 **pure function** — 입력 인자(또는 DataFrame), 출력 DataFrame/dict
- 직렬화 가능한 형태로만 반환 (JSON-serializable) — REST 노출 시 wrapper만 추가하면 됨
- Excel/plotly는 **마지막 단계의 변환** — 그 안에서 새 계산 금지

---

## 3. Claude Code Agent/Skill/MD 설계

> 사용자가 "에이전트/skill/md 설계까지 면밀히 보고 싶다"고 했으므로, 각 자산의 목적·트리거·도구·인터페이스를 분리해 설계.

### 3.1 Agent 설계 (`.claude/agents/*.md`)

Agent는 **단일 책임**을 가진 sub-agent. 메인 컨텍스트를 보호하면서 특정 도메인 작업을 위임.

| Agent | 책임 | 도구 | 트리거 |
|---|---|---|---|
| **xbrl-ingester** | zip 파일 한 개를 DuckDB로 적재 + 무결성 체크 | Bash, Read, Write, Grep | "분기 데이터 적재", "새 zip 받음" |
| **element-mapper** | 한국어 키워드 → XBRL element_id 후보 풀이 (lab.tsv 검색) | Grep, Read | "보험계약부채에 해당하는 element 찾아줘" |
| **peer-resolver** | CIK 리스트 → 회사명/업종/peer group 매핑 | Read, Grep | "이 분기 제출자 중 생보사만" |
| **benchmark-analyst** | SQL/polars로 cross-section + time-series 계산하고 결과 해석 | Bash, Read, Write | "보험계약부채 5개사 비교" |
| **report-builder** | 분석 결과를 Excel/Markdown/HTML로 합성 | Write, Bash | "결과 리포트 만들어" |

각 agent는 `.claude/agents/{name}.md` 파일로 정의:
- frontmatter: `name`, `description`, `tools`, `model`
- body: 시스템 프롬프트 (역할, 입출력 규약, 도메인 지식 요약)

### 3.2 Skill 설계 (`.claude/skills/*.md`)

Skill은 **사용자가 슬래시 명령으로 호출하는 워크플로**.

| Skill | 명령 예시 | 동작 |
|---|---|---|
| **ingest-quarter** | `/ingest-quarter 2026 1` | 지정 분기 zip을 DuckDB에 적재 (없으면 다운로드) |
| **list-peers** | `/list-peers 생명보험` | peer group 후보 회사 리스트 출력 |
| **find-item** | `/find-item 보험계약부채` | label에서 검색해 element_id 후보 표시 |
| **peer-snapshot** | `/peer-snapshot life-insurers BondsIssued 2025Q4` | 한 분기 한 항목 횡단 비교 표 + 차트 |
| **peer-trend** | `/peer-trend life-insurers BondsIssued` | 분기별 추이 시계열 차트 |
| **compare-vs-self** | `/compare-vs-self my_q1_2026.xlsx` | 자사 입력값을 peer 분포 대비 위치로 표시 |
| **validate-data** | `/validate-data` | 적재된 분기 데이터의 무결성/중복/단위 점검 |

각 skill은 `.claude/skills/{name}.md` 파일로 정의 — 자연어 instruction + 호출할 agent + 인자 파싱.

### 3.3 CLAUDE.md (프로젝트 메모리)

`./CLAUDE.md`에 다음을 정리:
- 프로젝트 목적·사용자 (한 줄)
- 디렉토리 레이아웃
- 데이터 위치, 핵심 스키마, 자주 쓰는 join 패턴
- 도메인 용어집 (보험계약부채, 책임준비금, IFRS17, 변액보험 등)
- 분석 시 주의사항 (DECIMALS, 정정 가능성, entity_extension 비교 불가)
- 자주 쓰는 명령어/쿼리 예시

**작성 원칙**: Claude가 매 대화마다 이 파일을 컨텍스트로 받으므로 핵심만. 길어지면 별도 `docs/` 하위 파일로 분리하고 CLAUDE.md에서 링크.

### 3.4 디렉토리 레이아웃 (제안)

```
Peer_Company_Benchmarking/
├── CLAUDE.md                       # 프로젝트 운영 매뉴얼 (Claude Code 컨텍스트)
├── PLAN.md                         # 이 파일
├── README.md                       # 사람용 개요 (선택)
│
├── .claude/
│   ├── agents/                     # 5개 sub-agent 정의
│   │   ├── xbrl-ingester.md
│   │   ├── element-mapper.md
│   │   ├── peer-resolver.md
│   │   ├── benchmark-analyst.md
│   │   └── report-builder.md
│   ├── skills/                     # 7개 사용자 명령
│   │   ├── ingest-quarter.md
│   │   ├── list-peers.md
│   │   ├── find-item.md
│   │   ├── peer-snapshot.md
│   │   ├── peer-trend.md
│   │   ├── compare-vs-self.md
│   │   └── validate-data.md
│   └── settings.local.json         # 권한 허용 목록
│
├── data/
│   ├── raw/                        # zip 그대로 보관
│   │   └── 2026Q1/                 # 압축 풀린 TSV들
│   ├── ref/                        # 참조 데이터
│   │   ├── companies.csv           # CIK → 회사명/업종
│   │   ├── peer_groups.yml         # 동업사 그룹 정의
│   │   └── liability_items.yml     # 관심 부채 항목 사전
│   ├── user/                       # 자사 내부 산출 데이터 입력
│   │   └── my_q1_2026.xlsx
│   └── db/
│       └── benchmark.duckdb        # 적재된 DB 단일 파일
│
├── src/
│   ├── ingest.py                   # zip → DuckDB 적재
│   ├── analysis/
│   │   ├── cross_section.py
│   │   ├── time_series.py
│   │   └── ratios.py
│   ├── domain/
│   │   ├── peer_groups.py
│   │   └── liability_mapping.py
│   └── report/
│       ├── excel_builder.py
│       └── streamlit_app.py        # 선택 시
│
├── notebooks/                      # 탐색/검증용
│   └── 01_data_exploration.ipynb
│
├── tests/                          # 적재·매핑·계산 단위 테스트
│
├── XBRL가이드.pdf
├── 공시정보활용마당_활용가이드.pdf
└── 2026_1Q_20260512034646.zip
```

---

## 4. 분석 우선순위 (사용자 확정) 및 도메인 매핑

### 4.1 분석 우선순위
1. **보험부채 항목** (1순위)
   - 보험계약부채 잔액·변동 (LRC, LIC, CSM, RA 구성요소별)
   - 재보험계약자산부채
   - 발생사고부채(LIC) 변동 — 손보 핵심
2. **보험손익 항목** (2순위)
   - 보험수익 (Insurance revenue)
   - 보험서비스비용 (Insurance service expense)
   - 보험서비스결과 (Insurance service result)
   - 보험금융손익 (Insurance finance income/expense)
3. **회계모형별** (3순위)
   - **GMM** (일반모형) — 생보 주력
   - **VFA** (변동수수료접근법) — 변액·연동상품
   - **PAA** (보험료배분접근법) — 손보·단기 보장
   - 측정모형별 보험계약부채 분해 → 회사별 사업 구성 비교

### 4.2 표준 IFRS17 role / element (실측 확인됨)
**Role 코드**:
- `DI817100/105` — 보험계약부채(자산) [변동/잔액]
- `DI817200/205` — 재보험계약자산부채 [변동/잔액]
- `DI817300/305` — 보험계약 정보 / 신계약·CSM 만기분석
- `DI818100/105` — 보험계약 위험관리

**Element 후보 (탐색 시작점)**:
- `ifrs-full_InsuranceContractLiabilities` — 보험계약부채 합계
- `dart_LiabilityForRemainingCoverage` — LRC 잔여보장부채
- `dart_LiabilityForIncurredClaims` — LIC 발생사고부채
- `dart_ContractualServiceMargin` — CSM
- `dart_RiskAdjustment` — RA 위험조정
- `dart_InsuranceRevenue` — 보험수익
- `dart_InsuranceServiceExpense` — 보험서비스비용
- `dart_InsuranceFinanceIncomeExpense` — 보험금융손익

**측정모형 dimension** (예상):
- `dart_MeasurementModelOfInsuranceContractsAxis` (또는 entity 확장)
- members: `GeneralModelMember`, `VariableFeeApproachMember`, `PremiumAllocationApproachMember`

→ Phase 4(부채 사전)에서 lab.tsv 검색으로 실제 element 풀 확정, `liability_items.yml` 정착.

### 4.3 핵심 분석 지표
| 카테고리 | 지표 | 식 | 인사이트 |
|---|---|---|---|
| 부채 | 보험계약부채 / 총자산 | InsLib / Assets | 보험 사업 의존도 |
| 부채 | CSM / 보험계약부채 | CSM / InsLib | 미실현 미래이익 강도 |
| 부채 | RA / (LRC ex-CSM) | RA / (LRC−CSM) | 위험 인식 수준 |
| 손익 | 보험서비스결과 / 보험수익 | ISR / Rev | 보험 영업 마진 |
| 손익 | 보험금융손익 / 보험계약부채 | IFIE / InsLib | 자산-부채 매칭 효율 |
| 모형 | GMM / 총 보험계약부채 | GMM share | 사업포트폴리오 구성 |
| 모형 | VFA / 총 보험계약부채 | VFA share | 변액 비중 |
| 검증 | 당사 / Peer 중위수 | Self / median(Peers) | **적정성 검증 핵심** |
| 검증 | 당사 percentile | rank(Self) in Peers | 분포상 위치 |

---

## 5. 단계별 로드맵

| Phase | 내용 | 산출물 | 예상기간 |
|---|---|---|---|
| **0. 의사결정** | Decision Points 확정 | 이 문서에 ★표시 결정 |  반나절 |
| **1. 셋업** | uv, DuckDB, polars, plotly 설치 + 디렉토리 골격 | `pyproject.toml`, 디렉토리 트리 | 0.5일 |
| **2. 적재 v1** | **2025 4Q zip → DuckDB 적재** (val 2.93GB, cntxt 2.67GB 스트리밍 COPY) + 무결성 검증 | `src/ingest.py`, `benchmark.duckdb` | 1.5일 |
| **3. Peer 매핑** | 11개 보험 CIK → 회사명/생손보 구분, 미래에셋생명 식별, peer_groups.yml 작성 | `data/ref/companies.csv`, `peer_groups.yml` | 0.5일 |
| **4. 부채 사전** | `DI817xxx`·`DI818xxx` role 산하 element 추출, label 매핑, 표준+entity 확장 분리 | `data/ref/liability_items.yml` + 검토 보고 | 2일 |
| **5. 분석 엔진 v1** | cross-section, time-series, ratio SQL/polars 함수, 단위 테스트 | `src/analysis/*` + tests | 3일 |
| **6. 자사 입력** | Excel 템플릿 정의, 자사값 적재 + peer 분포 대비 percentile | `data/user/template.xlsx` | 1일 |
| **7. 리포트** | Excel + plotly HTML 자동 출력, 핵심 5개 부채항목 리포트 | `report/2025_Annual.xlsx` | 2일 |
| **8. 시계열 확장** | 2023 Q3 ~ 2025 Q3 분기 zip 추가 적재 (D1-a 선택 시) | 4년치 적재 | 2~3일 (선택) |
| **9. Claude 자산** | `.claude/agents/`, `.claude/skills/` 정의 | Claude Code 통합 | 1일 |
| **10. UI 옵션** | Streamlit 대시보드 (선택) | `src/report/streamlit_app.py` | 2일 (선택) |

**총 예상**: 11~14일 (시계열·UI 옵션 포함 시 15~19일). 사업연도 보고서 메인으로 빠른 v1 도달 후 시계열 확장.

---

## 6. 핵심 리스크와 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| **생보사가 주석을 충분히 제출 안 함** | 비교 불가능 → 프로젝트 자체 무력화 | Phase 4에서 먼저 검증, 부족하면 **B안(수기 파싱 보조)** 전환 |
| **회사별 entity_extension 사용** | 횡단 비교 불가 | 표준 element 우선, extension은 라벨로 별도 클러스터링 |
| **결산 후 정정** | 분석 시점에 따라 값 달라짐 | 매 분석에 `as-of {submission_datetime}` 명시, 정정 감지 후 알림 |
| **DECIMALS·UNIT 혼선** | 금액 잘못 비교 | 적재 시 절대값(원 단위 long int)으로 정규화, 표시 시 분기/회사별 변환 |
| **2026 1Q 제출 마감 직후 시점** | 일부 회사 미제출/추가 제출 | 주 1회 재다운로드 자동화 + diff 알림 |
| **자사 산출 데이터 보안** | 미공시 내부 데이터 노출 | `data/user/`는 .gitignore, 외부 전송 금지, 로컬 DuckDB 전용 |
| **CIK ↔ 회사명 매핑 noise** | 잘못된 peer 그룹 | DART Open API + 사용자 확인 단계 |

---

## 7. 사용자 결정이 필요한 항목 (요약 — 2025 4Q 실측 반영)

| # | 항목 | 옵션 | 추천 |
|---|---|---|---|
| # | 항목 | 결정 |
|---|---|---|
| 1 | 데이터 전략 | ✓ XBRL only |
| 1a | 시계열 범위 | ✓ **2025 사업연도(2025 4Q)만**, v2에서 시계열 확장 |
| 1b | 분기 보고서 처리 | ✓ 제외 |
| 2 | UI / 아키텍처 | ✓ **Excel + plotly HTML**, library-first 구조 (계리포탈 연동 대비) |
| 3 | Peer group | ✓ KOSPI 상장 보험사 11개 (생/손/재) |
| 4 | 분석 우선순위 | ✓ 1.부채 항목 → 2.손익 항목 → 3.회계모형(GMM/VFA/PAA) |
| 5 | 자사 입력 방식 | Excel 템플릿 (Phase 6에서 정의) |
| 6 | 자동화 수준 | v1 수동, v2에서 자동 다운로드 |
| 7 | Git | ✓ init + push 완료 (github.com/kmk3106-cmd/Peer_Company_Benchmarking) |

---

## 8. 다음 액션 (실행 가능)

모든 결정 확정. 다음 순서로 진행:

1. **Phase 1 환경 셋업** (반나절):
   - `uv init` + dependencies: duckdb, polars, plotly, openpyxl, pyyaml, pandas
   - `src/`, `tests/`, `notebooks/`, `report/` 디렉토리 골격

2. **Phase 2 적재** (1.5일):
   - 2025 4Q zip → DuckDB 스트리밍 import (val 2.93GB, cntxt 2.67GB는 polars LazyFrame + DuckDB COPY)
   - 무결성 검증 쿼리 (행 수, 키 중복, UNIT/DECIMALS 분포)
   - 11개 보험 CIK 데이터만 별도 materialized view 생성 (성능)

3. **Phase 4 부채 사전** (1~2일):
   - `DI817xxx`·`DI818xxx` role의 lab.tsv·pre.tsv 스캔
   - 보험계약부채 / 손익 / 회계모형(GMM/VFA/PAA) element 풀 확정
   - `data/ref/liability_items.yml` 작성 (한국어 라벨 + element_id + 카테고리)

4. **Phase 5 분석 엔진** (3일):
   - `src/analysis/` library 구축 — 입출력 pure (DataFrame in/out, JSON-serializable)
   - cross-section, time-series, ratio, measurement model 분해
   - pytest 단위 테스트

5. **Phase 7 첫 리포트** (2일):
   - `src/render/excel.py` + `src/render/plotly_html.py`
   - 생보 4개사 보험계약부채 횡단 비교 → 자사 위치 보고

이후 Phase 6(자사 입력)·8(시계열 확장)·9(.claude/agents·skills)·10(Streamlit) 순.

---

## Appendix A. 핵심 SQL 패턴 (참고)

```sql
-- 특정 표준 element의 특정 분기 횡단 비교
SELECT
  s.CIK, c.company_name,
  v.VALUE::DOUBLE * pow(10, -CAST(v.DECIMALS AS INTEGER)) AS amount_krw,
  v.UNIT_ID
FROM val v
JOIN sub s USING (CIK, REPORT_DATE)
JOIN companies c ON c.cik = s.CIK
JOIN cntxt x USING (CIK, REPORT_DATE, CONTEXT_ID)
WHERE v.ELMT_ID = 'ifrs-full_BondsIssued'
  AND v.REPORT_DATE = '20260331'
  AND c.industry = '생명보험'
  AND x.PERIOD_INSTANT = '2026-03-31'
  AND v.UNIT_ID = 'KRW';

-- 한 회사 한 항목 분기별 추이
SELECT
  REPORT_DATE,
  VALUE::DOUBLE * pow(10, -CAST(DECIMALS AS INTEGER)) AS amount_krw
FROM val
WHERE CIK = '0XXXXXXX'  -- 미래에셋생명
  AND ELMT_ID = 'ifrs-full_InsuranceContractLiabilities'
ORDER BY REPORT_DATE;
```

## Appendix B. 참고 링크
- DART Open API: https://opendart.fss.or.kr/
- DART XBRL 주석 다운로드: https://opendart.fss.or.kr/disclosureinfo/fnltt/xbrlnote/main.do
- 한국 K-IFRS 17 적용기준: KASB 발표문 참조
