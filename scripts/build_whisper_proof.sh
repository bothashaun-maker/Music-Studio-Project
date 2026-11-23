#!/usr/bin/env bash
# CPU proof-build of the pinned whisper.cpp commit with the same cmake the
# runtime builder pins. Verifies the new whisper stage will work on Kaggle.
set -x
TOOLS=/home/z/my-project/gh/_pins/build-tools
SRC=/home/z/my-project/gh/_pins/whisper.cpp
BUILD=/home/z/my-project/gh/_pins/whisper-build
rm -rf "$BUILD"
export PATH="$TOOLS/bin:$PATH"
export PYTHONPATH="$TOOLS${PYTHONPATH:+:$PYTHONPATH}"
cmake --version | head -1
cmake -S "$SRC" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=OFF \
  -DCMAKE_BUILD_RPATH='$ORIGIN' \
  -DCMAKE_INSTALL_RPATH='$ORIGIN' \
  -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
  -DGGML_CCACHE=OFF \
  -DGGML_CUDA=OFF \
  -DCMAKE_DISABLE_FIND_PACKAGE_CUDAToolkit=TRUE \
  -DBUILD_SHARED_LIBS=ON \
  -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_SERVER=OFF || exit 1
cmake --build "$BUILD" --target whisper-cli --parallel 2 || exit 2
echo "=== produced binaries/libs ==="
find "$BUILD" -name 'whisper-cli' -o -name 'libwhisper*' -o -name 'libggml*' | grep -v CMakeFiles | sort
BIN=$(find "$BUILD" -name whisper-cli -type f | head -1)
echo "=== ldd $BIN ==="
ldd "$BIN"
echo "=== run --help ==="
"$BIN" --help 2>&1 | head -5
