# -*- mode: python -*-
import os
import site
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

block_cipher = None

# Use either virtual environment or lib/bin dirs from environment variables
# venv_path = Path.cwd() / ".venv"
# site_dirs = site.getsitepackages()
# venv_lib = venv_path / "lib"
# for venv_python_dir in venv_lib.glob("python*"):
#     venv_site_dir = venv_python_dir / "site-packages"
#     if venv_site_dir.is_dir():
#         site_dirs.append(venv_site_dir)

# kaldi_dir = venv_path / "tools" / "kaldi"
# if kaldi_dir.is_dir():
#     tools_dir = venv_path / "tools"
#     for kaldi_file in kaldi_dir.rglob("*"):
#         if kaldi_file.is_file():
#             binary_tuples.append(
#                 (kaldi_file, str(kaldi_file.parent.relative_to(tools_dir)))
#             )

# Look for compiled artifacts
# for site_dir in site_dirs:
#     site_dir = Path(site_dir)
#     webrtcvad_paths = list(site_dir.glob("_webrtcvad.*.so"))
#     if webrtcvad_paths:
#         webrtcvad_path = webrtcvad_paths[0]
#         break

a = Analysis(
    [Path.cwd() / "voice2json" "/__main__.py"],
    pathex=["."],
    binaries=[
        # (webrtcvad_path, "."),
        # (lib_dir / "libfstfarscript.so.13", "."),
        # (lib_dir / "libfstscript.so.13", "."),
        # (lib_dir / "libfstfar.so.13", "."),
        # (lib_dir / "libfst.so.13", "."),
        # (lib_dir / "libngram.so.134", "."),
        # (bin_dir / "ngramread", "."),
        # (bin_dir / "ngramcount", "."),
        # (bin_dir / "ngrammake", "."),
        # (bin_dir / "ngrammerge", "."),
        # (bin_dir / "ngramprint", "."),
        # (bin_dir / "ngramsymbols", "."),
        # (bin_dir / "ngramperplexity", "."),
        # (bin_dir / "farcompilestrings", "."),
        # (bin_dir / "phonetisaurus-apply", "."),
        # (bin_dir / "phonetisaurus-g2pfst", "."),
        # (bin_dir / "julius", "."),
    ],
    datas=copy_metadata("webrtcvad"),
    hiddenimports=["networkx"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voice2json",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="voice2json"
)
