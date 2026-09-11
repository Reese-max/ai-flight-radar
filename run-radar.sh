#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PYTHON="$DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "Create the environment: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
    exit 1
fi
CMD="${1:-status}"
if [[ $# -gt 0 ]]; then shift; fi
case "$CMD" in
    init|loop|scan|server|status|nlp) exec "$PYTHON" "$DIR/main.py" "$CMD" "$@" ;;
    *) echo "Usage: $0 {init|loop|scan|server|status|nlp <query>}" >&2; exit 2 ;;
esac
