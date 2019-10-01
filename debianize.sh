#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'architecture' '' 'Debian architecture'
DEFINE_string 'version' '1.0' 'Package version'
DEFINE_boolean 'package' true 'Create debian package (.deb)'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------

architecture="${FLAGS_architecture}"
version="${FLAGS_version}"

set -e

if [[ -z "${architecture}" ]]; then
    # Guess architecture
    architecture="$(dpkg-architecture | grep 'DEB_BUILD_ARCH=' | sed 's/^[^=]\+=//')"
fi

name='voice2json'
CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

package_name="${name}_${version}_${architecture}"
package_dir="debian/${package_name}"
build_dir="build_${CPU_ARCH}"
output_dir="${package_dir}/usr/lib/${name}"
mkdir -p "${output_dir}/${name}"

# Copy PyInstaller-generated files
dist_dir="dist_${CPU_ARCH}/voice2json"
if [[ -d "${dist_dir}" ]]; then
    rsync -av --delete \
          "${dist_dir}/" \
          "${output_dir}/${name}"
    # Remove all symbols (Liantian warning)
    strip --strip-all "${output_dir}/${name}"/*.so* || true

    # Remove executable bit from shared libs (Lintian warning)
    chmod -x "${output_dir}/${name}"/*.so* || true
fi

# Copy Kaldi
kaldi_output_dir="${package_dir}/usr/lib/${name}/build_${CPU_ARCH}/kaldi-master"
rm -rf "${kaldi_output_dir}"
mkdir -p "${kaldi_output_dir}"

rsync -av \
      --files-from 'debian/kaldi_include.txt' \
      "${build_dir}/kaldi-master/" \
      "${kaldi_output_dir}/"

# Avoid link recursion
rm -f '${build_dir}/kaldi-master/egs/wsj/s5/utils/utils'

for kaldi_sync_dir in 'egs/wsj/s5/utils' 'tools/openfst/bin' 'src/lib';
do
    rsync -av \
          --copy-links \
          "${build_dir}/kaldi-master/${kaldi_sync_dir}/" \
          "${kaldi_output_dir}/${kaldi_sync_dir}/"
done

# Copy bin/etc artifacts
for artifact_dir in 'bin' 'etc';
do
    rsync -av --delete \
          "${artifact_dir}/" \
          "${output_dir}/${artifact_dir}/"
done

# -----------------------------------------------------------------------------

if [[ "${FLAGS_package}" -eq "${FLAGS_TRUE}" ]]; then
    # Actually build the package
    cd 'debian' && fakeroot dpkg --build "${package_name}"
fi
