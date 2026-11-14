#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$TASK_ROOT/chat-own.sh" --checkpoint "$TASK_ROOT/runs/english-a100-v1/local-diagnostic-step2" "$@"
