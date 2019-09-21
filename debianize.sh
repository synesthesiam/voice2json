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
mkdir -p "${output_dir}/${name}"

# Copy PyInstaller-generated files
if [[ -d "dist/${name}" ]]; then
    rsync -av --delete \
          "dist/${name}/" \
          "${output_dir}/${name}"
    # Remove all symbols (Liantian warning)
    strip --strip-all "${output_dir}/${name}"/*.so* || true

    # Remove executable bit from shared libs (Lintian warning)
    chmod -x "${output_dir}/${name}"/*.so* || true
fi

# Copy Kaldi
kaldi_output_dir="${package_dir}/usr/lib/${name}/build/kaldi-master"
rm -rf "${kaldi_output_dir}"
mkdir -p "${kaldi_output_dir}"

rsync -av \
      --files-from 'debian/kaldi_include.txt' \
      "build/kaldi-master/" \
      "${kaldi_output_dir}/"

for kaldi_sync_dir in 'egs/wsj/s5/utils' 'tools/openfst/bin' 'src/lib';
do
    rsync -av \
          --copy-links \
          "build/kaldi-master/${kaldi_sync_dir}/" \
          "${kaldi_output_dir}/${kaldi_sync_dir}/"
done

# Copy bin/etc artifacts
for artifact_dir in 'bin' 'etc';
do
    rsync -av --delete \
          "${artifact_dir}/" \
          "${output_dir}/${artifact_dir}/"
done

# Actually build the package
#cd 'debian' && fakeroot dpkg --build "${package_name}"
