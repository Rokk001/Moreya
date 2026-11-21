#!/usr/bin/env bash
# Configures and builds the Moreya game binary on Linux against the libraries in <deps-prefix>
# (see install-linux-prereqs.sh). The build tree goes to <build-dir> (default: build).
#
# Usage: build-linux.sh <deps-prefix> [<build-dir>]
# Set OD_BUILD_NUMBER for the fourth version digit (default 0) and PYTHON_ROOT for the Python
# installation (default: python3's prefix). scripts/unix/package-linux-release.sh assembles a
# runnable game folder from the finished build tree.

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "usage: $0 <deps-prefix> [<build-dir>]" >&2
    exit 2
fi

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DEPS="$(cd "$1" && pwd)"
BUILD_DIR="${2:-$REPO_DIR/build}"
PYTHON_ROOT="${PYTHON_ROOT:-$(python3 -c 'import sys; print(sys.prefix)')}"

cmake -S "$REPO_DIR" -B "$BUILD_DIR" -G Ninja -DCMAKE_BUILD_TYPE=Release "-DOD_BUILD_NUMBER=${OD_BUILD_NUMBER:-0}" \
    "-DCMAKE_PREFIX_PATH=$DEPS" "-DPython_ROOT_DIR=$PYTHON_ROOT" "-DCEGUI_HOME=$DEPS" "-DOIS_HOME=$DEPS" \
    -DOD_TREAT_WARNINGS_AS_ERRORS=OFF
cmake --build "$BUILD_DIR" --target opendungeons-plus
