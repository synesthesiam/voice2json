# -*- mode: python -*-
from pathlib import Path

block_cipher = None

venv = Path.cwd() / ".venv"

a = Analysis(
    [os.path.join(os.getcwd(), "voice2json/__main__.py")],
    pathex=["."],
    binaries=[
        (
            venv
            / "lib/python3.6/site-packages/pywrapfst.cpython-36m-x86_64-linux-gnu.so",
            ".",
        ),
        (venv / "lib" / "libfstfarscript.so.13", "."),
        (venv / "lib" / "libfstscript.so.13", "."),
        (venv / "lib" / "libfstfar.so.13", "."),
        (venv / "lib" / "libfst.so.13", "."),
        (venv / "lib" / "libngram.so.134", "."),
        (venv / "bin" / "ngramread", "."),
        (venv / "bin" / "ngramcount", "."),
        (venv / "bin" / "ngrammake", "."),
        (venv / "bin" / "ngrammerge", "."),
        (venv / "bin" / "ngramprint", "."),
        (venv / "bin" / "phonetisaurus-apply", "."),
    ],
    datas=[],
    hiddenimports=["doit", "dbm.gnu", "antlr4-python3-runtime", "networkx", "numbers"],
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
