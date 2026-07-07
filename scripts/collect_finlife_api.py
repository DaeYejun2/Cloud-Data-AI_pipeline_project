"""
금융감독원 금융상품통합비교공시 오픈API 전체 수집 스크립트

수집 대상: 5개 권역 x 7종 금융상품, 페이지네이션 전체 순회
결과: data/raw/finlife_{endpoint}_base.csv, finlife_{endpoint}_option.csv

사용법:
    export FINLIFE_API_KEY="발급받은_인증키"
    pip install requests pandas
    python collect_finlife_api.py
"""

import os
import time
import json
import requests
import pandas as pd
from pathlib import Path
from typing import Tuple, List

BASE_URL = "http://finlife.fss.or.kr/finlifeapi"
API_KEY = os.environ.get("FINLIFE_API_KEY")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 7종 상품 엔드포인트
ENDPOINTS = {
    "company": "companySearch",
    "deposit": "depositProductsSearch",
    "saving": "savingProductsSearch",
    "annuity": "annuitySavingProductsSearch",
    "mortgage": "mortgageLoanProductsSearch",
    "rent_house_loan": "rentHouseLoanProductsSearch",
    "credit_loan": "creditLoanProductsSearch",
}

# 5개 권역코드
AREA_CODES = {
    "020000": "은행",
    "030200": "여신전문",
    "030300": "저축은행",
    "050000": "보험",
    "060000": "금융투자",
}

REQUEST_DELAY = 0.3  # 서버 부하 방지
MAX_RETRIES = 3

def fetch_all_pages(endpoint: str, area_code: str) -> Tuple[List, List]:
    """한 (엔드포인트, 권역) 조합에 대해 페이지네이션 전체 순회"""
    url = f"{BASE_URL}/{endpoint}.json"
    base_rows, option_rows = [], []
    page = 1

    while True:
        params = {"auth": API_KEY, "topFinGrpNo": area_code, "pageNo": page}
        data = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                break  # 성공했으니 재시도 루프 탈출
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                print(f"    ⚠️ 요청 실패 (page={page} , 시도 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)  # 2초, 4초 대기 후 재시도
        if data is None:
            print(f"    ❌ page={page} 재시도 모두 실패, 이 조합 수집 중단")
            break

        result = data.get("result", {})
        err_cd = result.get("err_cd", "")
        if err_cd != "000":
            print(f"    ⚠️ 응답 오류 (err_cd={err_cd}, msg={result.get('err_msg')})")
            break

        base_list = result.get("baseList", [])
        option_list = result.get("optionList", [])

        if not base_list:
            break  # 더 이상 데이터 없음

        base_rows.extend(base_list)
        option_rows.extend(option_list)

        max_page = result.get("max_page_no", page)
        if page >= int(max_page):
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return base_rows, option_rows


def main():
    if not API_KEY:
        print("⚠️ 환경변수 FINLIFE_API_KEY가 설정되지 않았습니다.")
        print('   실행 전: export FINLIFE_API_KEY="발급받은_인증키"')
        return

    for name, endpoint in ENDPOINTS.items():
        print(f"\n{'='*60}\n[{name}] 수집 시작 (endpoint={endpoint})\n{'='*60}")

        all_base, all_option = [], []

        for area_code, area_name in AREA_CODES.items():
            print(f"  권역: {area_name}({area_code}) 조회 중...")
            base_rows, option_rows = fetch_all_pages(endpoint, area_code)
            for row in base_rows:
                row["area_grp_cd"] = area_code
                row["area_grp_nm"] = area_name
            for row in option_rows:
                row["area_grp_cd"] = area_code
                row["area_grp_nm"] = area_name
            all_base.extend(base_rows)
            all_option.extend(option_rows)
            print(f"    → base {len(base_rows)}건, option {len(option_rows)}건")
            time.sleep(REQUEST_DELAY)

        # CSV 저장
        if all_base:
            pd.DataFrame(all_base).to_csv(
                OUTPUT_DIR / f"finlife_{name}_base.csv", index=False, encoding="utf-8-sig"
            )
        if all_option:
            pd.DataFrame(all_option).to_csv(
                OUTPUT_DIR / f"finlife_{name}_option.csv", index=False, encoding="utf-8-sig"
            )

        print(f"  [{name}] 총 base {len(all_base)}건, option {len(all_option)}건 저장 완료")

    print(f"\n전체 수집 완료. 저장 위치: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
