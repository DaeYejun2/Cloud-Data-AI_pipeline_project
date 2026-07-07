-- ============================================================
-- schema2.sql
-- finlife_pipeline DB용 스키마
-- 실행: psql -U <role> -d finlife_pipeline -f schema2.sql
-- ============================================================

-- ------------------------------------------------------------
-- (A) 금융상품 데이터: 7개 카테고리 x base/option = 14개 테이블
--     * base/option은 (dcls_month, fin_co_no, fin_prdt_cd) 조인키로 연결
--     * is_active: dcls_end_day 기준 파생 컬럼 (company 제외 6개 base에만 존재)
-- ------------------------------------------------------------

-- 회사 정보 (조인키 기준: dcls_month, fin_co_no / product 개념 없음)
CREATE TABLE company_base (
    dcls_month      TEXT,
    fin_co_no       TEXT,
    kor_co_nm       TEXT,
    dcls_chrg_man   TEXT,
    homp_url        TEXT,
    cal_tel         TEXT,
    area_grp_cd     TEXT,
    area_grp_nm     TEXT,
    PRIMARY KEY (dcls_month, fin_co_no)
);

CREATE TABLE company_option (
    dcls_month  TEXT,
    fin_co_no   TEXT,
    area_cd     TEXT,
    area_nm     TEXT,
    exis_yn     TEXT,
    area_grp_cd TEXT,
    area_grp_nm TEXT
);

-- 정기예금
CREATE TABLE product_deposit_base (
    dcls_month      TEXT,
    fin_co_no       TEXT,
    fin_prdt_cd     TEXT,
    kor_co_nm       TEXT,
    fin_prdt_nm     TEXT,
    join_way        TEXT,
    mtrt_int        TEXT,
    spcl_cnd        TEXT,
    join_deny       TEXT,
    join_member     TEXT,
    etc_note        TEXT,
    max_limit       NUMERIC,
    dcls_strt_day   DATE,
    dcls_end_day    DATE,          -- 99991231(무기한)은 NULL로 저장, is_active로 별도 판단
    fin_co_subm_day TEXT,
    area_grp_cd     TEXT,
    area_grp_nm     TEXT,
    is_active       BOOLEAN,
    PRIMARY KEY (dcls_month, fin_co_no, fin_prdt_cd)
);

CREATE TABLE product_deposit_option (
    dcls_month        TEXT,
    fin_co_no         TEXT,
    fin_prdt_cd       TEXT,
    intr_rate_type    TEXT,
    intr_rate_type_nm TEXT,
    save_trm          INTEGER,
    intr_rate         NUMERIC,
    intr_rate2        NUMERIC,
    area_grp_cd       TEXT,
    area_grp_nm       TEXT
);

-- 적금
CREATE TABLE product_saving_base (
    dcls_month      TEXT,
    fin_co_no       TEXT,
    fin_prdt_cd     TEXT,
    kor_co_nm       TEXT,
    fin_prdt_nm     TEXT,
    join_way        TEXT,
    mtrt_int        TEXT,
    spcl_cnd        TEXT,
    join_deny       TEXT,
    join_member     TEXT,
    etc_note        TEXT,
    max_limit       NUMERIC,
    dcls_strt_day   DATE,
    dcls_end_day    DATE,
    fin_co_subm_day TEXT,
    area_grp_cd     TEXT,
    area_grp_nm     TEXT,
    is_active       BOOLEAN,
    PRIMARY KEY (dcls_month, fin_co_no, fin_prdt_cd)
);

CREATE TABLE product_saving_option (
    dcls_month        TEXT,
    fin_co_no         TEXT,
    fin_prdt_cd       TEXT,
    intr_rate_type    TEXT,
    intr_rate_type_nm TEXT,
    rsrv_type         TEXT,
    rsrv_type_nm      TEXT,
    save_trm          INTEGER,
    intr_rate         NUMERIC,
    intr_rate2        NUMERIC,
    area_grp_cd       TEXT,
    area_grp_nm       TEXT
);

-- 연금저축
CREATE TABLE product_annuity_base (
    dcls_month        TEXT,
    fin_co_no         TEXT,
    fin_prdt_cd       TEXT,
    kor_co_nm         TEXT,
    fin_prdt_nm       TEXT,
    join_way          TEXT,
    pnsn_kind         TEXT,
    pnsn_kind_nm      TEXT,
    sale_strt_day     TEXT,   -- YYYYMMDD 형태지만 결측/이상값 많아 TEXT로 보관
    mntn_cnt          INTEGER,
    prdt_type         TEXT,
    prdt_type_nm      TEXT,
    avg_prft_rate     NUMERIC,
    dcls_rate         NUMERIC,
    guar_rate         TEXT,   -- 서술형 텍스트라 숫자화하지 않음
    btrm_prft_rate_1  NUMERIC,
    btrm_prft_rate_2  NUMERIC,
    btrm_prft_rate_3  NUMERIC,
    etc               TEXT,
    sale_co           TEXT,
    dcls_strt_day     DATE,
    dcls_end_day      DATE,
    fin_co_subm_day   TEXT,
    area_grp_cd       TEXT,
    area_grp_nm       TEXT,
    is_active         BOOLEAN,
    PRIMARY KEY (dcls_month, fin_co_no, fin_prdt_cd)
);

CREATE TABLE product_annuity_option (
    dcls_month        TEXT,
    fin_co_no         TEXT,
    fin_prdt_cd       TEXT,
    pnsn_recp_trm     TEXT,
    pnsn_recp_trm_nm  TEXT,
    pnsn_entr_age     INTEGER,
    pnsn_entr_age_nm  TEXT,
    mon_paym_atm      INTEGER,
    mon_paym_atm_nm   TEXT,
    paym_prd          INTEGER,
    paym_prd_nm       TEXT,
    pnsn_strt_age     INTEGER,
    pnsn_strt_age_nm  TEXT,
    pnsn_recp_amt     NUMERIC,
    area_grp_cd       TEXT,
    area_grp_nm       TEXT
);

-- 주택담보대출
CREATE TABLE product_mortgage_base (
    dcls_month      TEXT,
    fin_co_no       TEXT,
    fin_prdt_cd     TEXT,
    kor_co_nm       TEXT,
    fin_prdt_nm     TEXT,
    join_way        TEXT,
    loan_inci_expn  TEXT,
    erly_rpay_fee   TEXT,
    dly_rate        TEXT,
    loan_lmt        TEXT,
    dcls_strt_day   DATE,
    dcls_end_day    DATE,
    fin_co_subm_day TEXT,
    area_grp_cd     TEXT,
    area_grp_nm     TEXT,
    is_active       BOOLEAN,
    PRIMARY KEY (dcls_month, fin_co_no, fin_prdt_cd)
);

CREATE TABLE product_mortgage_option (
    dcls_month        TEXT,
    fin_co_no         TEXT,
    fin_prdt_cd       TEXT,
    mrtg_type         TEXT,
    mrtg_type_nm      TEXT,
    rpay_type         TEXT,
    rpay_type_nm      TEXT,
    lend_rate_type    TEXT,
    lend_rate_type_nm TEXT,
    lend_rate_min     NUMERIC,
    lend_rate_max     NUMERIC,
    lend_rate_avg     NUMERIC,
    area_grp_cd       TEXT,
    area_grp_nm       TEXT
);

-- 전세자금대출
CREATE TABLE product_rent_house_loan_base (
    dcls_month      TEXT,
    fin_co_no       TEXT,
    fin_prdt_cd     TEXT,
    kor_co_nm       TEXT,
    fin_prdt_nm     TEXT,
    join_way        TEXT,
    loan_inci_expn  TEXT,
    erly_rpay_fee   TEXT,
    dly_rate        TEXT,
    loan_lmt        TEXT,
    dcls_strt_day   DATE,
    dcls_end_day    DATE,
    fin_co_subm_day TEXT,
    area_grp_cd     TEXT,
    area_grp_nm     TEXT,
    is_active       BOOLEAN,
    PRIMARY KEY (dcls_month, fin_co_no, fin_prdt_cd)
);

CREATE TABLE product_rent_house_loan_option (
    dcls_month        TEXT,
    fin_co_no         TEXT,
    fin_prdt_cd       TEXT,
    rpay_type         TEXT,
    rpay_type_nm      TEXT,
    lend_rate_type    TEXT,
    lend_rate_type_nm TEXT,
    lend_rate_min     NUMERIC,
    lend_rate_max     NUMERIC,
    lend_rate_avg     NUMERIC,
    area_grp_cd       TEXT,
    area_grp_nm       TEXT
);

-- 개인신용대출
CREATE TABLE product_credit_loan_base (
    dcls_month        TEXT,
    fin_co_no         TEXT,
    fin_prdt_cd       TEXT,
    crdt_prdt_type    TEXT,
    kor_co_nm         TEXT,
    fin_prdt_nm       TEXT,
    join_way          TEXT,
    cb_name           TEXT,
    crdt_prdt_type_nm TEXT,
    dcls_strt_day     DATE,
    dcls_end_day      DATE,
    fin_co_subm_day   TEXT,
    area_grp_cd       TEXT,
    area_grp_nm       TEXT,
    is_active         BOOLEAN,
    PRIMARY KEY (dcls_month, fin_co_no, fin_prdt_cd, crdt_prdt_type)
);

CREATE TABLE product_credit_loan_option (
    dcls_month             TEXT,
    fin_co_no              TEXT,
    fin_prdt_cd            TEXT,
    crdt_prdt_type         TEXT,
    crdt_lend_rate_type    TEXT,
    crdt_lend_rate_type_nm TEXT,
    crdt_grad_1            NUMERIC,
    crdt_grad_4            NUMERIC,
    crdt_grad_5            NUMERIC,
    crdt_grad_6            NUMERIC,
    crdt_grad_10           NUMERIC,
    crdt_grad_11           NUMERIC,
    crdt_grad_12           NUMERIC,
    crdt_grad_13           NUMERIC,
    crdt_grad_avg          NUMERIC,
    area_grp_cd            TEXT,
    area_grp_nm            TEXT
);

-- ------------------------------------------------------------
-- (B) 분쟁조정사례 테이블
--     * 본문(raw_body)에서 4개 섹션 파싱 + 연도/본문길이 파생
--     * parse_status: 섹션 파싱이 온전히 됐는지 플래그 (품질 추적용)
-- ------------------------------------------------------------
CREATE TABLE dispute_cases (
    id                  SERIAL PRIMARY KEY,
    case_no             INTEGER,       -- 번호
    area                TEXT,          -- 권역
    dispute_type        TEXT,          -- 유형
    title               TEXT,          -- 제목
    reg_date            DATE,          -- 등록일
    view_count          INTEGER,       -- 조회수
    complaint_text      TEXT,          -- 민원내용
    issue_text          TEXT,          -- 쟁점
    result_text         TEXT,          -- 처리결과
    consumer_note_text  TEXT,          -- 소비자 유의사항
    raw_body            TEXT,          -- 원본 본문 (백업용, 재처리 대비 보관)
    detail_url          TEXT,          -- 상세URL
    reg_year            INTEGER,       -- 파생: 등록일 연도
    body_length         INTEGER,       -- 파생: 본문 길이(자)
    parse_status        TEXT           -- 'ok' / 'missing:...' / 'empty' / 'no_markers_found'
);

CREATE INDEX idx_dispute_cases_area_type ON dispute_cases (area, dispute_type);
CREATE INDEX idx_dispute_cases_reg_year ON dispute_cases (reg_year);

-- ------------------------------------------------------------
-- (C) 분쟁유형 -> 상품카테고리 매핑 (은행ㆍ중소서민, 금융투자 41건 대상)
--     * 다대다 관계 허용 (하나의 분쟁유형이 여러 상품 카테고리에 걸칠 수 있음)
--     * product_category가 NULL인 행 = "수집한 finlife 카테고리 중 매칭 대상 없음"
--       (억지로 끼워맞추지 않고 명시적으로 미매칭 처리)
-- ------------------------------------------------------------
CREATE TABLE dispute_product_mapping (
    id               SERIAL PRIMARY KEY,
    dispute_type     TEXT NOT NULL,
    product_category TEXT,            -- NULL 허용 = 미매칭
    match_note       TEXT              -- 매칭 근거/미매칭 사유 설명
);

-- ------------------------------------------------------------
-- (D) 통합 view
-- ------------------------------------------------------------

-- (D-1) 6개 상품 카테고리 base 테이블 통합 (company 제외: 상품 개념 없음)
CREATE VIEW v_product_summary AS
SELECT 'deposit' AS category, dcls_month, fin_co_no, fin_prdt_cd, kor_co_nm, fin_prdt_nm,
       area_grp_cd, area_grp_nm, is_active, dcls_strt_day, dcls_end_day
FROM product_deposit_base
UNION ALL
SELECT 'saving', dcls_month, fin_co_no, fin_prdt_cd, kor_co_nm, fin_prdt_nm,
       area_grp_cd, area_grp_nm, is_active, dcls_strt_day, dcls_end_day
FROM product_saving_base
UNION ALL
SELECT 'annuity', dcls_month, fin_co_no, fin_prdt_cd, kor_co_nm, fin_prdt_nm,
       area_grp_cd, area_grp_nm, is_active, dcls_strt_day, dcls_end_day
FROM product_annuity_base
UNION ALL
SELECT 'mortgage', dcls_month, fin_co_no, fin_prdt_cd, kor_co_nm, fin_prdt_nm,
       area_grp_cd, area_grp_nm, is_active, dcls_strt_day, dcls_end_day
FROM product_mortgage_base
UNION ALL
SELECT 'rent_house_loan', dcls_month, fin_co_no, fin_prdt_cd, kor_co_nm, fin_prdt_nm,
       area_grp_cd, area_grp_nm, is_active, dcls_strt_day, dcls_end_day
FROM product_rent_house_loan_base
UNION ALL
SELECT 'credit_loan', dcls_month, fin_co_no, fin_prdt_cd, kor_co_nm, fin_prdt_nm,
       area_grp_cd, area_grp_nm, is_active, dcls_strt_day, dcls_end_day
FROM product_credit_loan_base;

-- (D-2) 분쟁유형 x 상품카테고리 교차 건수
--       미매칭 건도 '미매칭'으로 명시적으로 노출 (숨기지 않음)
CREATE VIEW v_dispute_product_cross AS
SELECT
    COALESCE(m.product_category, '미매칭') AS product_category,
    d.area,
    d.dispute_type,
    COUNT(*) AS dispute_count
FROM dispute_cases d
LEFT JOIN dispute_product_mapping m ON d.dispute_type = m.dispute_type
WHERE d.area IN ('은행ㆍ중소서민', '금융투자')
GROUP BY COALESCE(m.product_category, '미매칭'), d.area, d.dispute_type
ORDER BY product_category, dispute_count DESC;
