#!/bin/bash
# wait-for-it.sh HOST:PORT [-t TIMEOUT_SECONDS] [-- COMMAND [ARGS]]
# Blocks until a TCP port is accepting connections, then optionally runs a command.
set -e

usage() {
    echo "Usage: $0 host:port [-t timeout] [-- command [args]]"
    exit 1
}

HOST_PORT="${1:?$(usage)}"
HOST="${HOST_PORT%%:*}"
PORT="${HOST_PORT##*:}"
TIMEOUT=60
shift

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -t) TIMEOUT="$2"; shift 2 ;;
        --) shift; break ;;
        *)  break ;;
    esac
done

echo "[wait-for-it] Waiting up to ${TIMEOUT}s for ${HOST}:${PORT}..."

for i in $(seq 1 "$TIMEOUT"); do
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        echo "[wait-for-it] ${HOST}:${PORT} is available after ${i}s"
        if [[ "$#" -gt 0 ]]; then
            exec "$@"
        fi
        exit 0
    fi
    sleep 1
done

echo "[wait-for-it] Timeout: ${HOST}:${PORT} did not become available in ${TIMEOUT}s"
exit 1
