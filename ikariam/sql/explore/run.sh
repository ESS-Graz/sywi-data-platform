#!/usr/bin/env bash
# Usage: ./run.sh 01_coverage.sql
# Exports AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from the repo's .env, which
# 00_setup.sql reads with getenv() to create the S3 secret, then runs one SQL file with the DuckDB CLI.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source ../../../.env; set +a
duckdb -f "${1:?give an .sql file}"
