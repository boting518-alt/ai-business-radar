#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
RUNTIME_PROFILE=${RUNTIME_PROFILE:-local}
export RUNTIME_PROFILE

pids=""
stop_all() {
  trap - INT TERM EXIT
  for pid in $pids; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap stop_all INT TERM EXIT

echo "runtime_start component=launcher profile=$RUNTIME_PROFILE project_root=$PROJECT_ROOT"
(cd "$PROJECT_ROOT" && exec uv run --project workers uvicorn ai_business_radar_api.main:app --reload --reload-dir apps/api) &
pids="$pids $!"
(cd "$PROJECT_ROOT" && exec uv run --project workers dramatiq ai_business_radar_workers.worker) &
pids="$pids $!"
(cd "$PROJECT_ROOT" && exec uv run --project workers python -m ai_business_radar_workers.scheduler) &
pids="$pids $!"
(cd "$PROJECT_ROOT/apps/web" && exec npm run dev) &
pids="$pids $!"
while true; do
  for pid in $pids; do
    if ! kill -0 "$pid" 2>/dev/null; then
      status=0
      wait "$pid" || status=$?
      echo "runtime_exit reason=child_process_stopped pid=$pid status=${status:-0}" >&2
      exit "${status:-1}"
    fi
  done
  sleep 1
done
