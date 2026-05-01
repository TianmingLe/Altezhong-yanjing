set -eu

export PYTHONPATH="${PYTHONPATH:-/app}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ "${OMI_DEMO:-0}" = "1" ]; then
  exec python -m uvicorn demo_main:app --host "${HOST}" --port "${PORT}"
fi

exec python -m uvicorn main:app --host "${HOST}" --port "${PORT}"
