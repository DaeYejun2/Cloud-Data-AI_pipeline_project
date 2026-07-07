"""
raw CSV(data/raw/) -> 가공(타입 변환, is_active 파생, 본문 섹션 파싱) -> PostgreSQL 적재

전제조건:
    1. schema2.sql이 이미 실행되어 테이블이 생성되어 있어야 함
       psql -U <role> -d finlife_pipeline -f schema2.sql
    2. pip install pandas sqlalchemy psycopg2-binary --break-system-packages
    3. 아래 환경변수로 DB 접속 정보 지정 (없으면 기본값 사용)
       export PGHOST=localhost PGPORT=5432 PGDATABASE=finlife_pipeline
       export PGUSER=postgres PGPASSWORD=발급받은_비밀번호

사용법:
    python preprocess_and_load.py

주의:
    - 이 스크립트는 재실행 시 기존 데이터를 지우고 다시 적재함(TRUNCATE 후 INSERT).
      스케줄링(cron)으로 주기 실행할 것을 염두에 둔 설계.
"""

import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

import pandas as pd

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("⚠️ sqlalchemy가 설치되어 있지 않습니다.")
    print("   설치: pip install sqlalchemy psycopg2-binary --break-system-packages")
    sys.exit(1)

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": os.environ.get("PGDATABASE", "finlife_pipeline"),
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ.get("PGPASSWORD", ""),
}


def get_engine():
    url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    return create_engine(url)


# ============================================================
# 공통 가공 유틸
# ============================================================

def parse_yyyymmdd(val):
    """YYYYMMDD(문자열 또는 float으로 읽힌 값)를 date로 변환.
    결측치 또는 '99991231'(무기한 센티널)은 None(=열려있음/무기한)으로 처리."""
    if pd.isna(val):
        return None
    s = str(val).split(".")[0]
    if s == "99991231" or len(s) != 8:
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def compute_is_active(end_date):
    """dcls_end_day 파싱 결과 기준 판매중 여부 파생.
    end_date가 None이면(무기한/미기재) 판매중으로 간주."""
    if end_date is None:
        return True
    return end_date >= date.today()


def add_date_and_active_cols(df: pd.DataFrame) -> pd.DataFrame:
    df["dcls_strt_day"] = df["dcls_strt_day"].apply(parse_yyyymmdd)
    df["dcls_end_day"] = df["dcls_end_day"].apply(parse_yyyymmdd)
    df["is_active"] = df["dcls_end_day"].apply(compute_is_active)
    return df


def to_str_cols(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """코드성 컬럼을 문자열화 (float 표기로 읽힌 경우 '.0' 제거)"""
    for c in cols:
        if c in df.columns:
            df[c] = df[c].apply(
                lambda v: None if pd.isna(v) else str(v).split(".")[0] if isinstance(v, float) else str(v)
            )
    return df


# ============================================================
# (A) 금융상품 데이터: 카테고리별 base/option 적재
# ============================================================

# 카테고리별 코드성 컬럼 목록 (문자열화 대상)
CODE_COLS_BASE = ["dcls_month", "fin_co_no", "fin_prdt_cd", "crdt_prdt_type"]
CODE_COLS_OPTION = ["dcls_month", "fin_co_no", "fin_prdt_cd", "crdt_prdt_type",
                    "area_cd", "area_grp_cd"]

# (base_csv, option_csv, base_table, option_table, base에 dcls_strt/end_day 존재 여부)
CATEGORIES = [
    ("finlife_deposit_base.csv", "finlife_deposit_option.csv",
     "product_deposit_base", "product_deposit_option"),
    ("finlife_saving_base.csv", "finlife_saving_option.csv",
     "product_saving_base", "product_saving_option"),
    ("finlife_annuity_base.csv", "finlife_annuity_option.csv",
     "product_annuity_base", "product_annuity_option"),
    ("finlife_mortgage_base.csv", "finlife_mortgage_option.csv",
     "product_mortgage_base", "product_mortgage_option"),
    ("finlife_rent_house_loan_base.csv", "finlife_rent_house_loan_option.csv",
     "product_rent_house_loan_base", "product_rent_house_loan_option"),
    ("finlife_credit_loan_base.csv", "finlife_credit_loan_option.csv",
     "product_credit_loan_base", "product_credit_loan_option"),
]


def load_products(engine):
    print("=" * 60)
    print("(A) 금융상품 데이터 가공 + 적재")
    print("=" * 60)

    with engine.begin() as conn:
        for base_csv, option_csv, base_table, option_table in CATEGORIES:
            base_path = RAW_DIR / base_csv
            option_path = RAW_DIR / option_csv

            if not base_path.exists():
                print(f"  ⚠️ {base_csv} 없음, 건너뜀")
                continue

            base_df = pd.read_csv(base_path, encoding="utf-8-sig")
            base_df = to_str_cols(base_df, CODE_COLS_BASE)
            base_df = add_date_and_active_cols(base_df)

            conn.execute(text(f"TRUNCATE TABLE {base_table} CASCADE"))
            base_df.to_sql(base_table, conn, if_exists="append", index=False)
            print(f"  ✅ {base_table}: {len(base_df)}행 적재")

            if option_path.exists():
                option_df = pd.read_csv(option_path, encoding="utf-8-sig")
                option_df = to_str_cols(option_df, CODE_COLS_OPTION)
                conn.execute(text(f"TRUNCATE TABLE {option_table} CASCADE"))
                option_df.to_sql(option_table, conn, if_exists="append", index=False)
                print(f"  ✅ {option_table}: {len(option_df)}행 적재")
            else:
                print(f"  ⚠️ {option_csv} 없음, {option_table}은 비워둠")


def load_company(engine):
    print("\n" + "=" * 60)
    print("(A-부속) 회사 정보 적재")
    print("=" * 60)

    base_path = RAW_DIR / "finlife_company_base.csv"
    option_path = RAW_DIR / "finlife_company_option.csv"

    with engine.begin() as conn:
        if base_path.exists():
            df = pd.read_csv(base_path, encoding="utf-8-sig")
            df = to_str_cols(df, ["dcls_month", "fin_co_no"])
            conn.execute(text("TRUNCATE TABLE company_base CASCADE"))
            df.to_sql("company_base", conn, if_exists="append", index=False)
            print(f"  ✅ company_base: {len(df)}행 적재")

        if option_path.exists():
            df = pd.read_csv(option_path, encoding="utf-8-sig")
            df = to_str_cols(df, ["dcls_month", "fin_co_no", "area_cd", "area_grp_cd"])
            conn.execute(text("TRUNCATE TABLE company_option CASCADE"))
            df.to_sql("company_option", conn, if_exists="append", index=False)
            print(f"  ✅ company_option: {len(df)}행 적재")


# ============================================================
# (B) 분쟁조정사례 본문 파싱 + 적재
# ============================================================

SECTION_MARKERS = ["민원내용", "쟁점", "처리결과", "소비자 유의사항"]
SECTION_KEY_MAP = {
    "민원내용": "complaint_text",
    "쟁점": "issue_text",
    "처리결과": "result_text",
    "소비자 유의사항": "consumer_note_text",
}


def parse_case_body(raw_text: str) -> dict:
    """본문 텍스트에서 ▣ 마커 기준 4개 섹션을 분리.
    마커 뒤 '목록' 푸터(정보관리 담당부서 안내 등) 이전까지를 마지막 섹션 범위로 봄."""
    result = {v: None for v in SECTION_KEY_MAP.values()}

    if not isinstance(raw_text, str) or not raw_text.strip():
        result["parse_status"] = "empty"
        return result

    positions = []
    for marker in SECTION_MARKERS:
        # 마커 내부 띄어쓰기(예: '소비자 유의사항' vs '소비자유의사항')가 케이스마다 달라
        # 마커 단어 사이에는 공백 유무 상관없이, '▣'와 마커 사이도 줄바꿈/공백 상관없이 매칭
        marker_pattern = r"\s*".join(re.escape(part) for part in marker.split())
        m = re.search(r"▣\s*" + marker_pattern, raw_text)
        if m:
            positions.append((marker, m.start(), m.end()))

    if not positions:
        result["parse_status"] = "no_markers_found"
        return result

    positions.sort(key=lambda x: x[1])

    for i, (marker, _, end) in enumerate(positions):
        if i + 1 < len(positions):
            section_end = positions[i + 1][1]
        else:
            footer_match = re.search(r"\n목록\n", raw_text[end:])
            section_end = end + footer_match.start() if footer_match else len(raw_text)
        result[SECTION_KEY_MAP[marker]] = raw_text[end:section_end].strip()

    missing = [k for k, v in result.items() if k != "parse_status" and not v]
    result["parse_status"] = "ok" if not missing else f"missing:{','.join(missing)}"
    return result


def load_disputes(engine):
    print("\n" + "=" * 60)
    print("(B) 분쟁조정사례 가공 + 적재")
    print("=" * 60)

    path = RAW_DIR / "fss_dispute_cases.csv"
    if not path.exists():
        print(f"  ⚠️ {path} 없음, 건너뜀")
        return

    df = pd.read_csv(path, encoding="utf-8-sig")

    parsed = df["본문"].apply(parse_case_body).apply(pd.Series)
    out = pd.DataFrame({
        "case_no": pd.to_numeric(df["번호"], errors="coerce"),
        "area": df["권역"],
        "dispute_type": df["유형"],
        "title": df["제목"],
        "reg_date": pd.to_datetime(df["등록일"], errors="coerce").dt.date,
        "view_count": pd.to_numeric(df["조회수"], errors="coerce"),
        "complaint_text": parsed["complaint_text"],
        "issue_text": parsed["issue_text"],
        "result_text": parsed["result_text"],
        "consumer_note_text": parsed["consumer_note_text"],
        "raw_body": df["본문"],
        "detail_url": df["상세URL"],
        "parse_status": parsed["parse_status"],
    })
    out["reg_year"] = out["reg_date"].apply(lambda d: d.year if pd.notna(d) else None)
    out["body_length"] = df["본문"].apply(lambda t: len(t) if isinstance(t, str) else 0)

    status_counts = out["parse_status"].value_counts()
    print("  본문 파싱 상태 분포:")
    for status, cnt in status_counts.items():
        print(f"    {status}: {cnt}건")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dispute_cases RESTART IDENTITY CASCADE"))
        out.to_sql("dispute_cases", conn, if_exists="append", index=False)
    print(f"  ✅ dispute_cases: {len(out)}행 적재")


# ============================================================
# (C) 분쟁유형 -> 상품카테고리 매핑 적재
#     41건(은행ㆍ중소서민 25 + 금융투자 16) 대상, 실제 6개 유형만 존재.
#     '여ㆍ수신'만 예금/적금/대출 상품군과 개념적 연관 있음(1:N, 단일 카테고리 아님).
#     나머지(신용카드/기타/증권선물/자산운용투자자문/금융투자기타)는
#     수집한 finlife 7개 카테고리에 대응 상품이 없어 명시적으로 미매칭 처리.
# ============================================================

MAPPING_ROWS = [
    # (dispute_type, product_category, match_note)
    ("여ㆍ수신", "deposit", "예금성 상품 관련 가능성 (포괄 유형, 단일 카테고리 확정 불가)"),
    ("여ㆍ수신", "saving", "적금성 상품 관련 가능성 (포괄 유형, 단일 카테고리 확정 불가)"),
    ("여ㆍ수신", "mortgage", "대출성 상품 관련 가능성 (포괄 유형, 단일 카테고리 확정 불가)"),
    ("여ㆍ수신", "rent_house_loan", "대출성 상품 관련 가능성 (포괄 유형, 단일 카테고리 확정 불가)"),
    ("여ㆍ수신", "credit_loan", "대출성 상품 관련 가능성 (포괄 유형, 단일 카테고리 확정 불가)"),
    ("신용카드", None, "finlife API 수집 대상 7개 카테고리에 신용카드 상품 없음"),
    ("기타", None, "포괄적 기타 유형, 특정 상품 카테고리 매칭 불가"),
    ("증권/선물", None, "finlife API 수집 대상 7개 카테고리에 증권/선물 상품 없음"),
    ("자산운용/투자자문", None, "finlife API 수집 대상 7개 카테고리에 해당 상품 없음"),
    ("금융투자기타", None, "포괄적 기타 유형, 특정 상품 카테고리 매칭 불가"),
]


def load_mapping(engine):
    print("\n" + "=" * 60)
    print("(C) 분쟁유형-상품카테고리 매핑 적재")
    print("=" * 60)

    df = pd.DataFrame(MAPPING_ROWS, columns=["dispute_type", "product_category", "match_note"])
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dispute_product_mapping RESTART IDENTITY CASCADE"))
        df.to_sql("dispute_product_mapping", conn, if_exists="append", index=False)
    print(f"  ✅ dispute_product_mapping: {len(df)}행 적재 "
          f"(매칭 {df['product_category'].notna().sum()}행 / 미매칭 {df['product_category'].isna().sum()}행)")


def main():
    if not RAW_DIR.exists():
        print(f"⚠️ raw 데이터 폴더가 없습니다: {RAW_DIR}")
        sys.exit(1)

    print(f"DB 접속 대상: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    engine = get_engine()

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"⚠️ DB 접속 실패: {e}")
        print("   PGUSER/PGPASSWORD/PGHOST 환경변수 및 pg_hba.conf 설정을 확인하세요.")
        sys.exit(1)

    load_products(engine)
    load_company(engine)
    load_disputes(engine)
    load_mapping(engine)

    print("\n전체 가공 + 적재 완료.")


if __name__ == "__main__":
    main()
