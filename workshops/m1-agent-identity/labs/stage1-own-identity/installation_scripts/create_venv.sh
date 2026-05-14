#!/bin/bash
# Agent Engine runtime workaround.
#
# The base image's Dockerfile (step 20/21) runs:
#   .venv/bin/python -m compileall "$(.venv/bin/python -c 'import site; print(site.getsitepackages()[0])')"
#
# Without this script, `.venv/bin/python` is a bare symlink and
# site.getsitepackages()[0] resolves to /usr/local/lib/python3.12/site-packages/
# which is root-owned → PermissionError when running as appuser → container
# exits before health-check → Vertex reports "failed to start and cannot serve traffic".
#
# Fix: create a proper pyvenv.cfg so Python treats .venv/ as a real virtualenv
# with a writable site-packages directory.
#
# Verbatim from:
#   https://github.com/GoogleCloudPlatform/cloud-networking-solutions/blob/main/demos/agent-gateway/src/mortgage-agent/deploy_agent.py
# (the script is generated inline there at deploy time; we vendor it explicitly so
# it ships via extra_packages and runs via build_options.installation_scripts).
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
