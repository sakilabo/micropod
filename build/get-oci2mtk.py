#!/usr/bin/env python3
# ===========================================================================
# get-oci2mtk.py — download a pinned oci2mtk release for THIS OS/arch into
# SCRIPT_DIR/tools/oci2mtk-<ver>/ and print the binary's path. Cached: a later
# run with the same version reuses the downloaded binary.
#
#   python build/get-oci2mtk.py v1.2.0
#
# Progress goes to stderr and only the binary path to stdout, so it composes:
#   oci2mtk=$(python build/get-oci2mtk.py v1.2.0)
# ===========================================================================
import os
import platform
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

SLUG = "sakilabo/oci2mtk-go"
SCRIPT_DIR = Path(__file__).resolve().parent

if len(sys.argv) < 2 or not sys.argv[1]:
    sys.exit(f"usage: {sys.argv[0]} <version>\ne.g. {sys.argv[0]} v1.2.0")
ver = sys.argv[1]

# --- detect OS / arch (mirrors the release asset naming) --------------------
system = platform.system()
if system == "Linux":
    os_name, ext, binname = "linux", "tar.gz", "oci2mtk"
elif system == "Darwin":
    os_name, ext, binname = "darwin", "tar.gz", "oci2mtk"
elif system == "Windows":
    os_name, ext, binname = "windows", "zip", "oci2mtk.exe"
else:
    sys.exit(f"oci2mtk: unsupported OS '{system}'")

machine = platform.machine().lower()
if machine in ("x86_64", "amd64"):
    arch = "amd64"
elif machine in ("aarch64", "arm64"):
    arch = "arm64"
else:
    sys.exit(f"oci2mtk: unsupported CPU arch '{platform.machine()}'")

out_dir = SCRIPT_DIR / "tools" / f"oci2mtk-{ver}"
exe = out_dir / binname
if exe.is_file():  # cache hit
    print(exe)
    sys.exit(0)

# --- download ---------------------------------------------------------------
name = f"oci2mtk-{ver}-{os_name}-{arch}.{ext}"
url = f"https://github.com/{SLUG}/releases/download/{ver}/{name}"
out_dir.mkdir(parents=True, exist_ok=True)
dl = out_dir / name
print(f"==> fetching oci2mtk {ver} ({os_name}/{arch})...", file=sys.stderr)
try:
    urllib.request.urlretrieve(url, dl)
except Exception as e:
    sys.exit(f"oci2mtk: download failed: {url}\n{e}")

# --- extract ----------------------------------------------------------------
if ext == "tar.gz":
    with tarfile.open(dl, "r:gz") as tf:
        tf.extractall(out_dir)
else:
    with zipfile.ZipFile(dl) as zf:
        zf.extractall(out_dir)
dl.unlink(missing_ok=True)

# binary may be nested in a subdir inside the archive
if not exe.is_file():
    found = next(out_dir.rglob(binname), None)
    if found is None:
        sys.exit(f"oci2mtk: binary '{binname}' not found after extracting {name}.")
    exe = found
try:
    os.chmod(exe, os.stat(exe).st_mode | 0o111)
except OSError:
    pass
print(exe)
