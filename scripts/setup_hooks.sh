#!/usr/bin/env bash
set -euo pipefail

python3.13 -m pip install --break-system-packages --user -r requirements.txt
python3.13 -m pre_commit install --hook-type pre-commit --hook-type pre-push
python3.13 -m pre_commit run --all-files --hook-stage pre-commit
python3.13 -m pre_commit run --all-files --hook-stage pre-push
