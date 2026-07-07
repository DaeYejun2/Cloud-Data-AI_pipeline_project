"""
금감원 분쟁조정사례 크롤러
사용법: pip install requests beautifulsoup4 && python crawl_fss_cases.py
결과: fss_dispute_cases.csv (목록 + 상세 본문 텍스트)
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import os
from pathlib import Path

BASE_URL = "https://www.fss.or.kr"
LIST_URL = f"{BASE_URL}/fss/job/fncCnflCase/list.do"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# collect_finlife_api.py와 동일한 규칙: scripts/ 폴더 기준 상위의 data/raw/ 에 저장
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "fss_dispute_cases.csv"


def get_list_page(page_index):
    """목록 페이지에서 사례 메타데이터 추출"""
    params = {"menuNo": "201195", "pageIndex": page_index}
    resp = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=15)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = soup.select("div.bd-list table tbody tr")
    cases = []

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 8:
            continue

        # 제목에서 상세 링크 추출
        link_tag = cols[3].find("a")
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        # caseSlno 추출
        case_slno = ""
        if "caseSlno=" in href:
            case_slno = href.split("caseSlno=")[1].split("&")[0]

        case = {
            "번호": cols[0].get_text(strip=True),
            "권역": cols[1].get_text(strip=True),
            "유형": cols[2].get_text(strip=True),
            "제목": link_tag.get_text(strip=True),
            "등록일": cols[4].get_text(strip=True),
            "조회수": cols[7].get_text(strip=True),
            "case_slno": case_slno,
            "상세URL": f"{BASE_URL}/fss/job/fncCnflCase/view.do?caseSlno={case_slno}&menuNo=201195",
        }
        cases.append(case)

    return cases


def get_detail_text(case_slno):
    """상세 페이지에서 본문 텍스트 추출"""
    url = f"{BASE_URL}/fss/job/fncCnflCase/view.do"
    params = {"caseSlno": case_slno, "menuNo": "201195"}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 본문 영역 찾기 (금감원 상세 페이지의 콘텐츠 영역)
        content = soup.select_one("#content")
        if content:
            # 스크립트, 스타일 태그 제거
            for tag in content.find_all(["script", "style", "nav"]):
                tag.decompose()

            text = content.get_text(separator="\n", strip=True)
            # 빈 줄 정리
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines)
        return ""
    except Exception as e:
        print(f"  ⚠️ 상세 페이지 오류 (caseSlno={case_slno}): {e}")
        return ""


def main():
    all_cases = []

    # 1단계: 목록 페이지 크롤링 (21페이지)
    print("=" * 60)
    print("1단계: 목록 페이지 크롤링")
    print("=" * 60)

    for page in range(1, 22):  # 1~21페이지
        print(f"  페이지 {page}/21 크롤링 중...")
        cases = get_list_page(page)
        all_cases.extend(cases)
        print(f"    → {len(cases)}건 수집")
        time.sleep(0.5)  # 서버 부하 방지

    print(f"\n총 {len(all_cases)}건 목록 수집 완료")

    # 2단계: 상세 페이지 본문 크롤링
    print("\n" + "=" * 60)
    print("2단계: 상세 페이지 본문 크롤링")
    print("=" * 60)

    for i, case in enumerate(all_cases):
        print(f"  [{i+1}/{len(all_cases)}] {case['제목'][:40]}...")
        case["본문"] = get_detail_text(case["case_slno"])
        time.sleep(0.5)  # 서버 부하 방지

    # 3단계: CSV 저장
    print("\n" + "=" * 60)
    print("3단계: CSV 저장")
    print("=" * 60)

    fieldnames = ["번호", "권역", "유형", "제목", "등록일", "조회수", "본문", "상세URL"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_cases)

    print(f"저장 완료: {OUTPUT_FILE}")
    print(f"총 {len(all_cases)}건, 파일 크기: {os.path.getsize(OUTPUT_FILE) / 1024:.1f}KB")

    # 샘플 출력
    print("\n" + "=" * 60)
    print("샘플 (첫 번째 사례)")
    print("=" * 60)
    if all_cases:
        sample = all_cases[0]
        print(f"번호: {sample['번호']}")
        print(f"권역: {sample['권역']}")
        print(f"유형: {sample['유형']}")
        print(f"제목: {sample['제목']}")
        print(f"등록일: {sample['등록일']}")
        print(f"본문 길이: {len(sample.get('본문', ''))}자")
        print(f"본문 미리보기: {sample.get('본문', '')[:200]}...")


if __name__ == "__main__":
    main()
