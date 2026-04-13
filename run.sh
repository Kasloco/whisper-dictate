#!/bin/bash
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate
exec python dictate.py
