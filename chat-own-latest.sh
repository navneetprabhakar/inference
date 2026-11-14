#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$TASK_ROOT/chat-own.sh" --checkpoint "$TASK_ROOT/runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs" "$@"
