#!/usr/bin/env bash
# Builds the libraries Moreya needs on Linux (OIS, pybind11, OGRE, CEGUI, SFML) into one prefix.
#
# Usage: install-linux-prereqs.sh <deps-prefix> [<source-dir>]
#
# Versions and patches match the Windows prerequisite scripts in scripts/win32; OGRE and CEGUI
# get the patches from scripts/win32/patches in the same order. A finished library leaves a
# .done-<name> marker in the prefix, so a second run only builds what is missing.
# Set INSTALL_SYSTEM_PACKAGES=1 to install the distribution packages with apt-get first.
# Set PYTHON_ROOT to the Python installation pybind11 and the game use (default: python3's prefix).

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "usage: $0 <deps-prefix> [<source-dir>]" >&2
    exit 2
fi

OIS_TAG=v1.5.1
OGRE_TAG=v14.6.1
CEGUI_REPO=https://github.com/tomluchowski/cegui.git
CEGUI_TAG=scissors_test_disabled
SFML_TAG=3.1.0
PYBIND11_TAG=v3.1.0

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PATCHES="$REPO_DIR/scripts/win32/patches"
mkdir -p "$1"
DEPS="$(cd "$1" && pwd)"
SRC="${2:-$DEPS/src}"
mkdir -p "$SRC"
SRC="$(cd "$SRC" && pwd)"
PYTHON_ROOT="${PYTHON_ROOT:-$(python3 -c 'import sys; print(sys.prefix)')}"

if [ "${INSTALL_SYSTEM_PACKAGES:-0}" = "1" ]; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
        build-essential cmake git ninja-build pkg-config patchelf \
        libx11-dev libxrandr-dev libxcursor-dev libxi-dev libxt-dev libxaw7-dev \
        libgl1-mesa-dev libglu1-mesa-dev libegl1-mesa-dev libudev-dev \
        libfreetype-dev libexpat1-dev zlib1g-dev libglm-dev libpugixml-dev \
        libflac-dev libvorbis-dev libogg-dev \
        libboost-filesystem-dev libboost-locale-dev libboost-program-options-dev \
        libboost-thread-dev libboost-system-dev libboost-chrono-dev
fi

common=(-G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_INSTALL_PREFIX=$DEPS" "-DCMAKE_PREFIX_PATH=$DEPS"
        -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=ON)

if [ ! -e "$DEPS/.done-OIS" ]; then
    rm -rf "$SRC/ois"
    git clone --depth 1 --branch "$OIS_TAG" https://github.com/wgois/OIS.git "$SRC/ois"
    cmake -S "$SRC/ois" -B "$SRC/ois/build" "${common[@]}" -DOIS_BUILD_DEMOS=OFF -DOIS_BUILD_SHARED_LIBS=ON \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    cmake --build "$SRC/ois/build" --target install
    touch "$DEPS/.done-OIS"
fi

if [ ! -e "$DEPS/.done-pybind11" ]; then
    rm -rf "$SRC/pybind11"
    git clone --depth 1 --branch "$PYBIND11_TAG" https://github.com/pybind/pybind11.git "$SRC/pybind11"
    cmake -S "$SRC/pybind11" -B "$SRC/pybind11/build" "${common[@]}" -DPYBIND11_TEST=OFF -DPYBIND11_INSTALL=ON \
        -DPYBIND11_FINDPYTHON=ON "-DPython_ROOT_DIR=$PYTHON_ROOT"
    cmake --build "$SRC/pybind11/build" --target install
    touch "$DEPS/.done-pybind11"
fi

if [ ! -e "$DEPS/.done-OGRE" ]; then
    rm -rf "$SRC/ogre"
    git clone --depth 1 --branch "$OGRE_TAG" https://github.com/OGRECave/ogre.git "$SRC/ogre"
    # Same prerequisite patches and order as scripts/win32/install-ogre-prereq.ps1
    for p in ogre14-multiwindow-settings ogre14-short-emitter ogre14-light-position-cache \
             ogre14-discard-lock-unsynchronized ogre14-gl3plus-program-shutdown \
             ogre14-gl3plus-exact-uniform-cache ogre14-tower-trace; do
        git -C "$SRC/ogre" apply --recount "$PATCHES/$p.patch"
    done
    cmake -S "$SRC/ogre" -B "$SRC/ogre/build" "${common[@]}" \
        -DOGRE_BUILD_DEPENDENCIES=OFF -DOGRE_STATIC=OFF -DOGRE_CONFIG_THREAD_PROVIDER=std -DOGRE_CONFIG_THREADS=3 \
        -DOGRE_BUILD_RENDERSYSTEM_GL3PLUS=ON -DOGRE_BUILD_RENDERSYSTEM_GL=OFF -DOGRE_BUILD_RENDERSYSTEM_GLES2=OFF \
        -DOGRE_BUILD_RENDERSYSTEM_VULKAN=OFF -DOGRE_GLSUPPORT_USE_EGL=OFF \
        -DOGRE_BUILD_PLUGIN_FREEIMAGE=OFF -DOGRE_BUILD_PLUGIN_EXRCODEC=OFF -DOGRE_BUILD_PLUGIN_BSP=OFF \
        -DOGRE_BUILD_PLUGIN_PCZ=OFF -DOGRE_BUILD_PLUGIN_DOT_SCENE=OFF -DOGRE_BUILD_PLUGIN_ASSIMP=OFF \
        -DOGRE_BUILD_COMPONENT_JAVA=OFF -DOGRE_BUILD_COMPONENT_PYTHON=OFF -DOGRE_BUILD_COMPONENT_CSHARP=OFF \
        -DOGRE_BUILD_COMPONENT_VOLUME=OFF -DOGRE_BUILD_COMPONENT_PAGING=OFF -DOGRE_BUILD_COMPONENT_TERRAIN=OFF \
        -DOGRE_BUILD_COMPONENT_PROPERTY=OFF -DOGRE_BUILD_COMPONENT_MESHLODGENERATOR=OFF \
        -DOGRE_BUILD_COMPONENT_OVERLAY_IMGUI=OFF -DOGRE_BUILD_COMPONENT_BULLET=OFF \
        -DOGRE_BUILD_SAMPLES=OFF -DOGRE_BUILD_TOOLS=OFF -DOGRE_BUILD_TESTS=OFF -DOGRE_INSTALL_SAMPLES=OFF \
        -DOGRE_INSTALL_DOCS=OFF -DOGRE_ENABLE_PRECOMPILED_HEADERS=OFF
    cmake --build "$SRC/ogre/build" --target install
    touch "$DEPS/.done-OGRE"
fi

if [ ! -e "$DEPS/.done-CEGUI" ]; then
    rm -rf "$SRC/cegui"
    git clone --depth 1 --branch "$CEGUI_TAG" "$CEGUI_REPO" "$SRC/cegui"
    # Same prerequisite patches and order as scripts/win32/install-cegui-prereq.ps1
    for p in cegui-list-hit-test cegui-msvc-snprintf cegui-ogre-clipping cegui-missing-target-query \
             cegui-current-cmake-policies cegui-ogre-forward-declarations; do
        git -C "$SRC/cegui" apply --recount "$PATCHES/$p.patch"
    done
    # OGRE 14 headers need C++14; CEGUI forces C++03/C++11 on GCC (MSVC defaults to C++14).
    sed -i -e 's/ -std=c++03//' -e 's/set(CMAKE_CXX_STANDARD 11)/set(CMAKE_CXX_STANDARD 14)/' "$SRC/cegui/CMakeLists.txt"
    grep -q 'CMAKE_CXX_STANDARD 14' "$SRC/cegui/CMakeLists.txt"
    cmake -S "$SRC/cegui" -B "$SRC/cegui/build" "${common[@]}" \
        -DCEGUI_BUILD_RENDERER_OGRE=ON -DCEGUI_BUILD_RENDERER_OPENGL=OFF -DCEGUI_BUILD_RENDERER_OPENGL3=OFF \
        -DCEGUI_BUILD_RENDERER_OPENGLES=OFF -DCEGUI_BUILD_RENDERER_OPENGLES2=OFF -DCEGUI_BUILD_RENDERER_OPENGLES3=OFF \
        -DCEGUI_BUILD_XMLPARSER_EXPAT=ON -DCEGUI_BUILD_XMLPARSER_LIBXML2=OFF -DCEGUI_BUILD_XMLPARSER_XERCES=OFF \
        -DCEGUI_BUILD_XMLPARSER_RAPIDXML=OFF -DCEGUI_BUILD_XMLPARSER_TINYXML=OFF \
        -DCEGUI_BUILD_IMAGECODEC_FREEIMAGE=OFF -DCEGUI_BUILD_IMAGECODEC_DEVIL=OFF \
        -DCEGUI_BUILD_IMAGECODEC_SILLY=OFF -DCEGUI_BUILD_IMAGECODEC_CORONA=OFF \
        -DCEGUI_SAMPLES_ENABLED=OFF -DCEGUI_BUILD_APPLICATION_TEMPLATES=OFF -DCEGUI_BUILD_TESTS=OFF \
        -DCEGUI_BUILD_PERFORMANCE_TESTS=OFF -DCEGUI_BUILD_DATAFILES_TEST=OFF -DCEGUI_BUILD_LUA_MODULE=OFF \
        -DCEGUI_BUILD_LUA_GENERATOR=OFF -DCEGUI_BUILD_PYTHON_MODULES=OFF \
        -DCEGUI_LIB_INSTALL_DIR:PATH=lib -DCEGUI_INCLUDE_INSTALL_DIR:PATH=include/cegui-0 \
        -DCMAKE_DISABLE_FIND_PACKAGE_SFML=ON -DCEGUI_HAS_PCRE_REGEX=OFF -DCEGUI_HAS_STD11_REGEX=ON \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    cmake --build "$SRC/cegui/build" --target install
    touch "$DEPS/.done-CEGUI"
fi

if [ ! -e "$DEPS/.done-SFML" ]; then
    rm -rf "$SRC/sfml"
    git clone --depth 1 --branch "$SFML_TAG" https://github.com/SFML/SFML.git "$SRC/sfml"
    cmake -S "$SRC/sfml" -B "$SRC/sfml/build" "${common[@]}" -DSFML_BUILD_EXAMPLES=OFF -DSFML_BUILD_DOC=OFF \
        -DSFML_USE_SYSTEM_DEPS=OFF -DSFML_BUILD_WINDOW=ON -DSFML_BUILD_GRAPHICS=ON -DSFML_BUILD_AUDIO=ON -DSFML_BUILD_NETWORK=ON
    cmake --build "$SRC/sfml/build" --target install
    touch "$DEPS/.done-SFML"
fi

echo "Dependencies installed in $DEPS"
