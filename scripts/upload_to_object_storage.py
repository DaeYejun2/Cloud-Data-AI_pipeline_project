"""
data/raw/ 폴더의 raw CSV 파일들을 OCI Object Storage에 업로드하는 스크립트

전제조건:
    1. ~/.oci/config 파일 설정 완료 (API Key 인증)
    2. OCI 콘솔에서 버킷 생성 완료
    3. pip install oci --break-system-packages (VM 환경에 따라 옵션 필요할 수 있음)

사용법:
    python upload_to_object_storage.py

동작 방식:
    - data/raw/ 안의 모든 .csv 파일을 스캔
    - 실행 시점 날짜(YYYYMMDD) 폴더 아래에 업로드 -> 실행할 때마다 스냅샷이 남아서
      나중에 "언제 수집된 데이터인지" 추적 가능 (자동화/스케줄링 시 유용)
    - 예: raw/20260706/finlife_saving_base.csv
"""

import sys
from pathlib import Path
from datetime import datetime

try:
    import oci
except ImportError:
    print("⚠️ oci 패키지가 설치되어 있지 않습니다.")
    print("   설치: pip install oci --break-system-packages")
    sys.exit(1)

# ==================== 설정 (본인 환경에 맞게 확인) ====================
BUCKET_NAME = "bucket-06-cbnu-lv2"
RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OBJECT_PREFIX = "raw"  # 버킷 안에서 raw/{날짜}/파일명 형태로 정리
# =====================================================================


def main():
    # ~/.oci/config 파일을 기본 위치에서 읽어옴 (DEFAULT 프로필)
    try:
        config = oci.config.from_file()
    except Exception as e:
        print(f"⚠️ OCI config 로드 실패: {e}")
        print("   ~/.oci/config 파일이 있는지, 형식이 맞는지 확인하세요.")
        sys.exit(1)

    client = oci.object_storage.ObjectStorageClient(config)

    try:
        namespace = client.get_namespace().data
    except Exception as e:
        print(f"⚠️ Object Storage 연결 실패 (인증 문제일 수 있음): {e}")
        sys.exit(1)

    if not RAW_DATA_DIR.exists():
        print(f"⚠️ 폴더가 존재하지 않습니다: {RAW_DATA_DIR}")
        print("   먼저 collect_finlife_api.py / crawl_fss_cases.py를 실행하세요.")
        sys.exit(1)

    files = sorted(RAW_DATA_DIR.glob("*.csv"))
    if not files:
        print(f"⚠️ 업로드할 CSV 파일이 없습니다: {RAW_DATA_DIR}")
        sys.exit(1)

    run_date = datetime.now().strftime("%Y%m%d")
    print(f"네임스페이스: {namespace}")
    print(f"버킷: {BUCKET_NAME}")
    print(f"업로드 대상: {len(files)}개 파일 (실행일 폴더: {OBJECT_PREFIX}/{run_date}/)")
    print("=" * 60)

    success, failed = 0, []

    for f in files:
        object_name = f"{OBJECT_PREFIX}/{run_date}/{f.name}"
        try:
            with open(f, "rb") as fh:
                client.put_object(namespace, BUCKET_NAME, object_name, fh)
            print(f"  ✅ {f.name} -> {object_name}")
            success += 1
        except Exception as e:
            print(f"  ❌ {f.name} 업로드 실패: {e}")
            failed.append(f.name)

    print("=" * 60)
    print(f"완료: 성공 {success}건 / 실패 {len(failed)}건")
    if failed:
        print(f"실패 목록: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
