# -*- mode: python -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

block_cipher = None

venv = Path.cwd() / ".venv"
bin_dir = Path(os.environ.get("spec_bin_dir", venv / "bin"))
lib_dir = Path(os.environ.get("spec_lib_dir", venv / "lib"))
site_dir = Path(
    os.environ.get("spec_site_dir", venv / "lib" / "python3.6" / "site-packages")
)

pywrapfst_path = list(site_dir.glob("pywrapfst.*.so"))[0]
webrtcvad_path = list(site_dir.glob("_webrtcvad.*.so"))[0]

a = Analysis(
    [Path.cwd() / "voice2json" "/__main__.py"],
    pathex=["."],
    binaries=[
        (pywrapfst_path, "."),
        (webrtcvad_path, "."),
        (lib_dir / "libfstfarscript.so.13", "."),
        (lib_dir / "libfstscript.so.13", "."),
        (lib_dir / "libfstfar.so.13", "."),
        (lib_dir / "libfst.so.13", "."),
        (lib_dir / "libngram.so.134", "."),
        (bin_dir / "ngramread", "."),
        (bin_dir / "ngramcount", "."),
        (bin_dir / "ngrammake", "."),
        (bin_dir / "ngrammerge", "."),
        (bin_dir / "ngramprint", "."),
        (bin_dir / "ngramsymbols", "."),
        (bin_dir / "ngramperplexity", "."),
        (bin_dir / "farcompilestrings", "."),
        (bin_dir / "phonetisaurus-apply", "."),
    ],
    datas=copy_metadata("webrtcvad"),
    hiddenimports=["doit", "dbm.gnu", "networkx", "numbers"],
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
