#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
    echo "Usage: debianize.sh ARCH [VERSION]"
    exit 1
fi

name='voice2json'
arch="$1"
version="$2"

if [[ -z "${verson}" ]]; then
    version="1.0"
fi

package_name="${name}_${version}_${arch}"
package_dir="debian/${package_name}"
output_dir="${package_dir}/usr/lib/${name}"
mkdir -p "${output_dir}"

# Copy PyInstaller-generated files
if [[ -d "dist/${name}" ]]; then
    rsync -av --delete \
          "dist/${name}/" \
          "${output_dir}"

    # Remove all symbols (Liantian warning)
    strip --strip-all "${output_dir}"/*.so* || true

    # Remove executable bit from shared libs (Lintian warning)
    chmod -x "${output_dir}"/*.so* || true
fi

# Actually build the package
cd 'debian' && fakeroot dpkg --build "${package_name}"
