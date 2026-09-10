#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$DIR/.venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Virtualenv not found at $DIR/.venv. Please initialize first."
    exit 1
fi

CMD="${1:-status}"
shift || true

case "$CMD" in
    loop)
        echo "Starting AI Flight Radar Autonomous Loop..."
        exec "$VENV_PYTHON" "$DIR/main.py" loop "$@"
        ;;
    scan)
        echo "Running batch scan..."
        exec "$VENV_PYTHON" "$DIR/main.py" scan "$@"
        ;;
    server)
        echo "Starting Web Dashboard and API server..."
        exec "$VENV_PYTHON" "$DIR/main.py" server "$@"
        ;;
    status)
        exec "$VENV_PYTHON" "$DIR/main.py" status "$@"
        ;;
    nlp)
        exec "$VENV_PYTHON" "$DIR/main.py" nlp "$@"
        ;;
    *)
        echo "Usage: $0 {loop|scan|server|status|nlp <query>}"
        exit 1
        ;;
esac
