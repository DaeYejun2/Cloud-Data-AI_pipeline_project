# Cloud-Data-AI_pipeline_project

# 금융상품 × 분쟁조정사례 교차분석 EDA 서비스

> OCI 기반 Cloud 데이터 파이프라인 구축 과제 (수집 → 저장 → 가공 → 제공)
> 2023086025 문예준

금융감독원이 공개하는 **금융상품 정형 데이터**(통합비교공시 오픈 API)와 **금융분쟁조정사례 비정형 텍스트**(게시판 크롤링)를 수집·가공하여, 상품 스펙과 실제 분쟁 판단 근거를 한 화면에서 대조할 수 있는 인터랙티브 EDA 대시보드를 제공합니다.

**서비스 접속(Public Link):** `http://140.238.29.51/`

---

## 1. 서비스 소개 및 사용 시나리오

### 문제 정의

금융상품의 "공시된 스펙"과 "실제로 발생한 분쟁"은 서로 다른 곳에 흩어져 있습니다. 상품 조건은 finlife 통합비교공시에, 분쟁 선례는 금감원 분쟁조정사례 게시판에 각각 존재해, 소비자·분석자가 두 정보를 함께 보려면 별도의 수작업 대조가 필요합니다.

### 서비스 목표

두 이종 데이터(정형 API + 비정형 텍스트)를 하나의 파이프라인으로 수집·정제·적재하고, 다음 4개 화면으로 제공합니다.

| 탭 | 내용 |
|---|---|
| 홈 대시보드 | 수집 현황 KPI(상품/옵션/분쟁 건수), 파이프라인 요약, 최신·인기 사례 |
| 금융상품 EDA | 권역·상품종류 필터 기반 상품 분포, 금리 박스플롯, 가입기간별 금리 추이, 판매상태 |
| 분쟁사례 EDA | 권역 드릴다운 유형 분석, 연도별 추이, 민원 키워드 빈도, 사례 원문 열람 |
| 교차 인사이트 | 상품카테고리 × 분쟁유형 교차 건수, 평균 금리 vs 분쟁 건수, ML 분석(텍스트 군집화·금리 회귀) |

### 사용 시나리오

1. **금융 소비자**: 정기예금 가입 전 "정기예금" 카테고리의 금리 지형을 확인하고, 예·적금 관련 분쟁조정 선례 원문(민원내용/쟁점/처리결과/소비자 유의사항)을 열람해 유의점을 파악한다.
2. **분석 실무자**: 권역별 분쟁 발생 패턴과 민원 본문 키워드를 통해 반복되는 분쟁 요인을 탐색하고, 교차 인사이트 탭에서 상품 조건과 분쟁의 연관 가능성을 검토한다.

---

## 2. 아키텍처

<img width="2385" height="1335" alt="architecture" src="https://github.com/user-attachments/assets/277bce96-2d75-4f69-9bec-38a38906e523" />


### 사용한 OCI 리소스

| 리소스 | 용도 |
|---|---|
| **Compute VM** (Oracle Linux, Public IP) | 파이프라인 전 단계 실행 환경 (수집 스크립트, PostgreSQL, Streamlit, nginx) |
| **Boot/Block Volume** | 원천 CSV(`data/raw/`) 및 PostgreSQL 데이터 디렉토리 상주 |
| **Object Storage** (`bucket-06-cbnu-lv2`) | 원천 CSV의 날짜별 스냅샷 백업 (`raw/YYYYMMDD/…`) — 수집 이력 추적 및 원천 데이터 유실 대비 |
| **VCN + 보안목록** | 80(웹 서비스)/22(SSH) 포트 인바운드 허용 |

### 구성 요소

- **수집**: `collect_finlife_api.py` (finlife 오픈 API, 재시도 3회 + 백오프), `crawl_fss_cases.py` (BeautifulSoup 크롤러)
- **저장**: Block Volume의 `data/raw/` (원천 CSV 15종) + Object Storage 스냅샷 + PostgreSQL 16 (정형 적재)
- **가공**: `preprocess_and_load.py` — 타입 변환, 파생 컬럼(is_active, reg_year 등), 분쟁 본문 4개 섹션 파싱, 매핑 테이블 적재
- **제공**: Streamlit 대시보드(:8501) ← nginx 리버스 프록시(:80) ← 사용자
- **자동화**: `run_pipeline.sh`를 cron으로 매월 1일 03:00 실행 (수집→백업→적재 원스텝), PostgreSQL은 systemd `enable`로 부팅 시 자동 구동

### 저장소 선택의 타당성

| 데이터 | 저장소 | 선택 이유 |
|---|---|---|
| 원천 CSV (수집 직후) | Block Volume | 가공 스크립트가 로컬 파일로 즉시 접근, 빠른 재처리 |
| 원천 CSV 스냅샷 | Object Storage | 대용량·비정형 보관에 적합, 날짜별 폴더로 수집 이력 추적, VM 장애 시에도 원천 보존 |
| 정형 상품 데이터 / 파싱된 분쟁 텍스트 | PostgreSQL | base/option 조인, 통합 VIEW, 집계 SQL을 DB 단에서 처리해 대시보드는 경량 결과셋만 수신. 정형·텍스트 혼합 스키마와 VIEW 활용에 유리 |

---

## 3. 설치 및 실행 방법

### 3.1 사전 준비

- OCI Compute VM (Oracle Linux 8/9), 보안목록에서 80, 22 포트 인바운드 허용
- 금융감독원 finlife 오픈 API 인증키 발급 (https://finlife.fss.or.kr)
- OCI Object Storage 버킷 생성 + `~/.oci/config` API Key 인증 설정

### 3.2 설치

```bash
# 1) 소스 배치
git clone https://github.com/DaeYejun2/Cloud-Data-AI_pipeline_project.git ~/finlife-pipeline
cd ~/finlife-pipeline

# 2) PostgreSQL 16 설치 및 자동 시작 설정
sudo dnf install -y postgresql16-server
sudo /usr/pgsql-16/bin/postgresql-16-setup initdb
sudo systemctl enable --now postgresql-16

# 3) DB/스키마 생성
sudo -u postgres createdb finlife_pipeline
psql -U postgres -d finlife_pipeline -f db/schema2.sql

# 4) 파이썬 가상환경 및 의존성
python3 -m venv ~/venv && source ~/venv/bin/activate
pip install requests beautifulsoup4 pandas sqlalchemy psycopg2-binary \
            streamlit plotly scikit-learn oci

# 5) 환경변수 파일 작성 (파일 권한 600 권장)
cat > .env << 'ENV'
export FINLIFE_API_KEY="발급받은_인증키"
export PGHOST=localhost PGPORT=5432 PGDATABASE=finlife_pipeline
export PGUSER=postgres PGPASSWORD="비밀번호"
ENV
chmod 600 .env
```

### 3.3 파이프라인 실행 (수집 → 백업 → 가공·적재)

```bash
chmod +x run_pipeline.sh
./run_pipeline.sh          # 전체 원스텝 실행 (약 10~15분)
```

개별 단계 실행도 가능합니다.

```bash
source .env
python scripts/collect_finlife_api.py        # ① API 수집
python scripts/crawl_fss_cases.py            # ① 크롤링 (201건)
python scripts/upload_to_object_storage.py   # ② Object Storage 스냅샷
python scripts/preprocess_and_load.py        # ③ 가공 + DB 적재
```

### 3.4 스케줄링 등록 (자동화)

```bash
crontab -e
# 매월 1일 03:00 전체 파이프라인 자동 실행, 로그 보존
0 3 1 * * /home/opc/finlife-pipeline/run_pipeline.sh >> /home/opc/finlife-pipeline/cron_update.log 2>&1
```

### 3.5 웹 서비스 기동

```bash
source .env
nohup streamlit run webapp/app.py --server.port 8501 --server.address 127.0.0.1 &
```

nginx 리버스 프록시 설정 예시 (`/etc/nginx/conf.d/finlife.conf`):

```nginx
server {
    listen 80;
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;   # Streamlit websocket 필수
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
sudo systemctl enable --now nginx
```

이후 브라우저에서 `http://140.238.29.51/` 접속.

---

## 4. 데이터 흐름 상세 (수집 소스 → 저장 위치 → 가공 로직 → 제공 방식)

### 4.1 금융상품 정형 데이터

| 단계 | 내용 |
|---|---|
| 수집 소스 | finlife 오픈 API — 7개 카테고리(회사/예금/적금/연금/주담대/전세대출/신용대출) × 5개 권역, 페이지네이션 전체 순회. base(상품 기본정보)와 option(금리·조건)이 API 구조상 분리되어 있어 각각 수집 |
| 예외 처리 | 요청 실패 시 최대 3회 재시도(2초/4초 백오프), 최종 실패 시 해당 조합만 건너뛰고 명시적 오류 로그. 응답 오류 코드(err_cd) 검증 |
| 저장 위치 | `data/raw/finlife_{카테고리}_{base\|option}.csv` (Block Volume) → Object Storage `raw/YYYYMMDD/` 스냅샷 → PostgreSQL 카테고리별 14개 테이블 |
| 가공 로직 | 코드 컬럼 문자열화, 공시일 날짜 타입 변환(무기한 센티널 99991231은 NULL 처리), 공시종료일 기준 판매중 여부 `is_active` 파생, base/option 조인키(공시월+금융회사번호+상품코드) 유지, 6개 카테고리 통합 조회용 `v_product_summary` VIEW |
| 제공 방식 | 금융상품 EDA 탭 — 권역·상품종류 필터, 상품 분포/금리 박스플롯/가입기간별 금리 추이/판매상태 도넛 |

### 4.2 분쟁조정사례 비정형 텍스트

| 단계 | 내용 |
|---|---|
| 수집 소스 | 금감원 분쟁조정사례 게시판 — 목록 21페이지 순회로 메타데이터(번호/권역/유형/제목/등록일/조회수) 확보 후 상세페이지 201건 본문 크롤링 (요청 간 0.5초 대기로 서버 부하 방지) |
| 예외 처리 | 상세 페이지 실패 시 빈 본문으로 계속 진행, 이후 가공 단계에서 `parse_status`로 품질 플래그 기록 (실패 은닉 방지) |
| 저장 위치 | `data/raw/fss_dispute_cases.csv` → Object Storage 스냅샷 → PostgreSQL `dispute_cases` 테이블 (원문 `raw_body` 보존 + 파싱 결과 병행 저장) |
| 가공 로직 | ▣ 마커 기준 4개 섹션(민원내용/쟁점/처리결과/소비자 유의사항) 분리, 마커 띄어쓰기 변형 대응 정규식, 푸터 제거, `reg_year`·`body_length` 파생, 파싱 상태(`ok`/`missing:…`/`empty`) 기록. 분쟁유형→상품카테고리 매핑 테이블 적재(대응 상품이 없는 유형은 억지 매칭 대신 명시적 미매칭 처리) |
| 제공 방식 | 분쟁사례 EDA 탭 — 권역 드릴다운(27개 유형의 가독성 확보), 키워드 빈도, 사례 원문 섹션별 열람. 교차 인사이트 탭 — `v_dispute_product_cross` VIEW 기반 교차 건수, ML 분석 |

### 4.3 자동화 흐름

```
cron (매월 1일 03:00)
  └─ run_pipeline.sh
       ├─ collect_finlife_api.py    # API 수집
       ├─ crawl_fss_cases.py        # 크롤링
       ├─ upload_to_object_storage.py  # 날짜별 스냅샷 백업
       └─ preprocess_and_load.py    # 가공 + TRUNCATE 후 재적재
```

`set -e`로 중간 단계 실패 시 즉시 중단하여 오염된 데이터가 후속 단계로 전파되는 것을 방지하고, 실행 결과는 `cron_update.log`에 기록되어 운영 추적이 가능합니다.

---

## 5. 한계점 및 향후 개선 방향

1. **saving×저축은행 간헐적 timeout** — 해당 조합은 서버 응답 생성이 느려 timeout이 간헐 발생. 재시도(3회+백오프)로 대부분 복구되나 일부 페이지가 누락될 수 있음. timeout 상향(15→30초) 및 실패 조합 자동 재수집이 개선 과제.
2. **스냅샷 방식 적재** — `preprocess_and_load.py`는 재실행 시 TRUNCATE 후 전체 재적재하는 스냅샷 방식으로, 시계열 누적(예: 금리 변동 추이)은 불가. Object Storage의 날짜별 스냅샷이 이력을 보완하나, 증분 적재 구조로의 전환이 향후 과제.
3. **텍스트 분석 고도화 필요** — 키워드 빈도·군집화가 단순 어절/TF-IDF 기반(형태소 분석 미적용)이라 조사 결합 형태가 섞이고, 범용 어휘를 공유하는 은행권 사례는 단일 군집으로 혼재. 금융 도메인 사전 + 형태소 분석기(예: Mecab) 도입이 다음 단계.
4. **교차분석 표본 한계** — 상품-분쟁 교차 대상은 은행ㆍ중소서민·금융투자 41건에 한정되고, 원본에 공유 코드가 없어 '여ㆍ수신' 포괄 유형은 5개 카테고리에 1:N 매핑되어 건수가 중복 집계됨. 통계적 결론이 아닌 탐색적 지표로 제공하며, 화면에도 동일하게 명시.
5. **보험 권역(160건, 80%)** — 대응하는 finlife 상품 데이터가 없어 교차확인에서 제외되나, 표본이 크고 유형이 세분화되어 있어 독립적인 텍스트 분석 대상으로 활용.

---

## 6. 외부 오픈소스 및 데이터 출처

| 구분 | 이름 | 용도 | 출처 |
|---|---|---|---|
| 데이터 | 금융상품 통합비교공시 오픈 API | 금융상품 정형 데이터 | https://finlife.fss.or.kr |
| 데이터 | 금융감독원 분쟁조정사례 게시판 | 분쟁사례 비정형 텍스트 | https://www.fss.or.kr |
| 라이브러리 | requests, BeautifulSoup4 | API 호출·크롤링 | PyPI (Apache-2.0 / MIT) |
| 라이브러리 | pandas, numpy | 데이터 가공 | PyPI (BSD) |
| 라이브러리 | SQLAlchemy, psycopg2-binary | PostgreSQL 연동 | PyPI (MIT / LGPL) |
| 라이브러리 | Streamlit | 웹 대시보드 | PyPI (Apache-2.0) |
| 라이브러리 | Plotly | 인터랙티브 차트 | PyPI (MIT) |
| 라이브러리 | scikit-learn | TF-IDF·SVD·선형회귀 | PyPI (BSD) |
| 라이브러리 | oci (OCI Python SDK) | Object Storage 업로드 | PyPI (UPL/Apache-2.0) |
| 소프트웨어 | PostgreSQL 16, nginx | DB·리버스 프록시 | postgresql.org / nginx.org |
| 폰트 | Pretendard | 대시보드 웹폰트 | https://github.com/orioncactus/pretendard (SIL OFL) |

---

## 저장소 구조

```
finlife-pipeline/
├── run_pipeline.sh              # 전체 파이프라인 원스텝 실행 (cron 등록 대상)
├── .env                         # 환경변수 (API 키·DB 접속, 커밋 제외)
├── data/
│   └── raw/                     # 원천 CSV 15종 (Block Volume)
├── db/
│   └── schema2.sql              # PostgreSQL 스키마 (테이블 17종 + VIEW 2종)
├── scripts/
│   ├── collect_finlife_api.py   # ① finlife API 수집 (재시도·백오프)
│   ├── crawl_fss_cases.py       # ① 분쟁사례 크롤러
│   ├── upload_to_object_storage.py  # ② Object Storage 날짜별 스냅샷
│   └── preprocess_and_load.py   # ③ 가공 + DB 적재
└── webapp/
    └── app.py                   # ④ Streamlit EDA 대시보드 (4탭)
```
