#!/bin/bash
set -e

ROLE=${SERVICE_ROLE:-api}

if [ "$ROLE" = "worker" ]; then
    echo "Starting Arena Audio Worker..."
    exec python -m services.arena.workers.audio_worker
else
    echo "Starting Arena API..."
    exec uvicorn services.arena.main:app --host 0.0.0.0 --port 8002
fi
