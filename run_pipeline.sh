
#!/bin/bash
# 수집 -> Object Storage 백업 -> 가공/적재 전체 파이프라인
set -e  # 중간 단계 실패 시 즉시 중단 (실패한 채로 다음 단계 진행 방지)

cd /home/opc/finlife-pipeline

# cron은 .bashrc를 안 읽으므로 환경변수 직접 로드
source /home/opc/finlife-pipeline/.env

# PY=/home/opc/finlife-pipeline/venv/bin/python
PY=~/venv/bin/python

echo "=== 파이프라인 시작: $(date) ==="
$PY scripts/collect_finlife_api.py
$PY scripts/crawl_fss_cases.py
$PY scripts/upload_to_object_storage.py
$PY scripts/preprocess_and_load.py
echo "=== 파이프라인 완료: $(date) ==="
