#!/bin/bash
# Agent Engine runtime workaround. See M1 Stage 1 lab for context.
set -e
PYTHON3=$(which python3)
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
mkdir -p /code/.venv/bin
mkdir -p /code/.venv/lib/python${PY_VER}/site-packages
ln -sf "$PYTHON3" /code/.venv/bin/python
ln -sf "$PYTHON3" /code/.venv/bin/python3
cat > /code/.venv/pyvenv.cfg << PYCFG
home = $(dirname $PYTHON3)
include-system-site-packages = true
PYCFG
echo "Created .venv virtualenv (site-packages: /code/.venv/lib/python${PY_VER}/site-packages)"
