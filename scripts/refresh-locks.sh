#!/usr/bin/env bash
# Regenerate the committed dependency resolution artifacts from the
# human-edited manifests (requirements.txt, requirements-dev.txt,
# cloudflare/package.json). See docs/DEPENDENCIES.md for the update and
# rollback procedure. The dependency-gate CI job runs this script and fails
# when it changes any tracked file.
set -euo pipefail
cd "$(dirname "$0")/.."

# Resolver versions are pinned here so every machine regenerates the same
# artifacts byte-for-byte. Bump these deliberately, never by accident.
UV_VERSION="0.12.9"
NPM_VERSION="10.9.2"   # Pin the lockfile generator, independent of the runner's npm patch.

uv_compile() {
    # Use an identical resolver version everywhere: ambient uv if it already
    # matches, otherwise an ephemeral pinned copy via uvx (no env mutation).
    if [[ "$(uv --version 2>/dev/null | awk '{print $2}')" == "$UV_VERSION" ]]; then
        uv pip compile "$@"
    else
        uvx --from "uv==${UV_VERSION}" uv pip compile "$@"
    fi
}

uv_compile requirements.txt \
    --output-file requirements-lock.txt \
    --generate-hashes --universal --python-version 3.12

uv_compile requirements-dev.txt \
    --output-file requirements-dev-lock.txt \
    --generate-hashes --universal --python-version 3.12

(cd cloudflare && npx --yes "npm@${NPM_VERSION}" install --package-lock-only \
    --ignore-scripts --no-audit --no-fund)

echo "Regenerated: requirements-lock.txt, requirements-dev-lock.txt, cloudflare/package-lock.json"
