#!/usr/bin/env bash
# Assembles a self-contained Linux x86_64 game folder from a Release build tree.
#
# Usage: package-linux-release.sh <build-dir> <deps-prefix> <python-prefix> <output-dir>
#
# The layout mirrors the Windows deployment: plugins.cfg, resources.cfg and the game data
# folders sit side by side, so the game finds its data in the current folder. The game binary
# moreya lies in bin/, the launcher script moreya in the top folder.
# Shared libraries go to lib/ (OGRE plugins to lib/OGRE, CEGUI modules to lib/cegui-0.9999,
# the Python standard library to lib/python<ver>). The launcher changes into the folder
# and sets the CEGUI module directory and the Python home before starting the binary.

set -euo pipefail

if [ "$#" -ne 4 ]; then
    echo "usage: $0 <build-dir> <deps-prefix> <python-prefix> <output-dir>" >&2
    exit 2
fi

SRC_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$(cd "$1" && pwd)"
DEPS="$(cd "$2" && pwd)"
PYTHON_PREFIX="$(cd "$3" && pwd)"
OUT="$4"
# Name of the game binary in the build tree and in bin/ of the package
BINARY=moreya

rm -rf "$OUT"
mkdir -p "$OUT/lib/OGRE" "$OUT/bin"
OUT="$(cd "$OUT" && pwd)"
GAME="$OUT/bin/$BINARY"

# Game binary
install -m 755 "$BUILD_DIR/$BINARY" "$GAME"
strip --strip-unneeded "$GAME"

# Game data, the same folders as the Windows install rules in CMakeLists.txt (scripts/ holds developer tools only)
for dir in config gui levels licenses materials models music particles python shaders sounds; do
    cp -a "$SRC_DIR/$dir" "$OUT/$dir"
done
for doc in AUTHORS CREDITS LICENSE.md README.md RELEASE-NOTES.md; do
    cp "$SRC_DIR/$doc" "$OUT/$doc"
done

# OGRE plugins named in plugins.cfg
for plugin in RenderSystem_GL3Plus Plugin_ParticleFX Plugin_OctreeSceneManager Codec_STBI; do
    found="$(find "$DEPS/lib/OGRE" -maxdepth 1 -name "$plugin.so*" | head -n 1)"
    if [ -z "$found" ]; then
        echo "missing OGRE plugin: $plugin" >&2
        exit 1
    fi
    cp -L "$found" "$OUT/lib/OGRE/$plugin.so"
done

# CEGUI modules are loaded at run time and do not show up as binary dependencies
CEGUI_MODULE_SRC="$(dirname "$(find "$DEPS/lib" -name 'libCEGUIExpatParser.so' | head -n 1)")"
if [ -z "$CEGUI_MODULE_SRC" ] || [ "$CEGUI_MODULE_SRC" = "." ]; then
    echo "CEGUI modules not found below $DEPS/lib" >&2
    exit 1
fi
CEGUI_MODULE_DIR_NAME="$(basename "$CEGUI_MODULE_SRC")"
if [ "$CEGUI_MODULE_SRC" = "$DEPS/lib" ]; then
    CEGUI_MODULE_DIR_NAME=cegui-modules
fi
mkdir -p "$OUT/lib/$CEGUI_MODULE_DIR_NAME"
for module in "$CEGUI_MODULE_SRC"/libCEGUI*Parser*.so* "$CEGUI_MODULE_SRC"/libCEGUICoreWindowRendererSet*.so*; do
    [ -e "$module" ] || continue
    cp -a "$module" "$OUT/lib/$CEGUI_MODULE_DIR_NAME/"
done

# Copies every shared library dependency that is not part of the base system
# (our own prefix, the Python runtime, Boost and the X toolkit libraries of the OGRE
# config dialog, which many desktops do not install) next to the game.
bundle_deps() {
    local object="$1"
    ldd "$object" | while read -r name arrow path rest; do
        [ "$arrow" = "=>" ] || continue
        [ "$path" != "not" ] || continue
        case "$path" in
            "$DEPS"/*|"$PYTHON_PREFIX"/*|*/libboost_*|*/libXaw.so*|*/libXmu.so*|*/libXpm.so*|*/libXt.so*)
                if [ ! -e "$OUT/lib/$name" ]; then
                    cp -L "$path" "$OUT/lib/$name"
                    echo "$OUT/lib/$name"
                fi
                ;;
        esac
    done
}

export LD_LIBRARY_PATH="$DEPS/lib:$DEPS/lib/OGRE:$CEGUI_MODULE_SRC:$PYTHON_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
pending=("$GAME" "$OUT"/lib/OGRE/*.so "$OUT/lib/$CEGUI_MODULE_DIR_NAME"/*.so)
while [ "${#pending[@]}" -gt 0 ]; do
    next=()
    for object in "${pending[@]}"; do
        while IFS= read -r added; do
            [ -n "$added" ] && next+=("$added")
        done < <(bundle_deps "$object")
    done
    pending=("${next[@]+"${next[@]}"}")
done

# Search paths relative to each object, so the folder can be moved anywhere
patchelf --set-rpath '$ORIGIN/../lib' "$GAME"
for lib in "$OUT"/lib/*.so*; do
    [ -L "$lib" ] && continue
    patchelf --set-rpath '$ORIGIN' "$lib"
done
for lib in "$OUT"/lib/OGRE/*.so "$OUT/lib/$CEGUI_MODULE_DIR_NAME"/*.so*; do
    [ -L "$lib" ] && continue
    patchelf --set-rpath '$ORIGIN/..' "$lib"
done

# Python standard library for the embedded interpreter
PYTHON_LIB_DIR="$(find "$PYTHON_PREFIX/lib" -maxdepth 1 -type d -name 'python3.*' | head -n 1)"
PYTHON_LIB_NAME="$(basename "$PYTHON_LIB_DIR")"
mkdir -p "$OUT/lib/$PYTHON_LIB_NAME"
tar -C "$PYTHON_LIB_DIR" \
    --exclude='__pycache__' --exclude='./test' --exclude='./idlelib' --exclude='./tkinter' \
    --exclude='./turtledemo' --exclude='./ensurepip' --exclude='./site-packages/*' \
    -cf - . | tar -C "$OUT/lib/$PYTHON_LIB_NAME" -xf -

# OGRE media used by the resource configuration
# The install folder of the media depends on the OGRE version (share/OGRE or share/OGRE-<ver>)
OGRE_MEDIA="$(dirname "$(find "$DEPS/share" -type d -path '*/Media/RTShaderLib' | head -n 1)")"
if [ ! -d "$OGRE_MEDIA/Main" ]; then
    echo "OGRE media not found below $DEPS/share" >&2
    exit 1
fi
mkdir -p "$OUT/ogre-media" "$OUT/ogre-includes"
cp -a "$OGRE_MEDIA/Main" "$OUT/ogre-media/Main"
cp -a "$OGRE_MEDIA/RTShaderLib" "$OUT/ogre-media/RTShaderLib"
# OGRE 14 resolves shader includes only inside the group of the program (see CMakeLists.txt),
# so the shared includes get their own folder in the Graphics group, as on Windows.
for include in OgreUnifiedShader.h GLSL_GL3Support.glsl HLSL_SM4Support.hlsl DefaultShaders.metal; do
    cp "$OGRE_MEDIA/Main/$include" "$OUT/ogre-includes/$include"
done

# plugins.cfg: plugin folder relative to the plugins.cfg file
sed -e 's|^PluginFolder=.*$|PluginFolder=./lib/OGRE|' "$BUILD_DIR/plugins.cfg" > "$OUT/plugins.cfg"

# resources.cfg: OGRE media from the bundled folder; folders that do not exist are left out
: > "$OUT/resources.cfg"
while IFS= read -r line; do
    case "$line" in
        FileSystem=/*/share/OGRE/Media/*)
            rel="ogre-media/${line#*/share/OGRE/Media/}"
            if [ -d "$OUT/$rel" ]; then
                echo "FileSystem=$rel" >> "$OUT/resources.cfg"
                case "$rel" in
                    ogre-media/RTShaderLib) echo "FileSystem=ogre-includes" >> "$OUT/resources.cfg" ;;
                esac
            fi
            ;;
        *)
            echo "$line" >> "$OUT/resources.cfg"
            ;;
    esac
done < "$BUILD_DIR/resources.cfg"
if grep -q '^FileSystem=/' "$OUT/resources.cfg"; then
    echo "absolute path left in resources.cfg" >&2
    exit 1
fi

# Launcher
cat > "$OUT/moreya" <<EOF
#!/bin/sh
# Starts the game from its own folder so it finds plugins.cfg, resources.cfg and its data.
HERE="\$(cd "\$(dirname "\$0")" && pwd)"
cd "\$HERE" || exit 1
CEGUI_MODULE_DIR="\$HERE/lib/$CEGUI_MODULE_DIR_NAME"
PYTHONHOME="\$HERE"
export CEGUI_MODULE_DIR PYTHONHOME
exec "\$HERE/bin/$BINARY" "\$@"
EOF
chmod 755 "$OUT/moreya"

echo "Bundled libraries:"
ls -l "$OUT/lib" "$OUT/lib/OGRE" "$OUT/lib/$CEGUI_MODULE_DIR_NAME"
# Every object must resolve its dependencies from the folder or the base system alone
unset LD_LIBRARY_PATH
missing=0
for object in "$GAME" "$OUT"/lib/*.so* "$OUT"/lib/OGRE/*.so "$OUT/lib/$CEGUI_MODULE_DIR_NAME"/*.so*; do
    if ldd "$object" | grep -q 'not found'; then
        echo "unresolved dependencies of $object:" >&2
        ldd "$object" | grep 'not found' >&2
        missing=1
    fi
done
[ "$missing" -eq 0 ] || exit 1
echo "Remaining system dependencies of the binary:"
ldd "$GAME" | grep -v "$OUT" || true
echo "resources.cfg:"
cat "$OUT/resources.cfg"
echo "plugins.cfg:"
cat "$OUT/plugins.cfg"
