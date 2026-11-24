#!/usr/bin/env bash
set -euo pipefail

# Cppcheck 2.22.0. Pin the source commit rather than executing a moving installer.
source_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/aule-cppcheck.XXXXXX")
trap 'rm -rf -- "$source_dir"' EXIT
git -C "$source_dir" init --quiet
git -C "$source_dir" remote add origin https://github.com/cppcheck-opensource/cppcheck.git
git -C "$source_dir" fetch --quiet --depth 1 origin a436ca35ed1887bee789765122b65ed2d7a7e045
git -C "$source_dir" checkout --quiet --detach FETCH_HEAD
install_dir="${RUNNER_TEMP:-/tmp}/aule-cppcheck-2.22.0"
cmake -S "$source_dir" -B "$source_dir/build" -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTS=OFF -DCMAKE_INSTALL_PREFIX="$install_dir"
cmake --build "$source_dir/build" --parallel 2
cmake --install "$source_dir/build"
echo "$install_dir/bin" >> "$GITHUB_PATH"
"$install_dir/bin/cppcheck" --version
