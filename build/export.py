#!/usr/bin/env python3
# ===========================================================================
# export.py — find local micropod:* images and export each to a RouterOS-
# loadable .tar.gz via oci2mtk. Per-image jobs run in parallel, throttled with
# a thread pool.
#
#   python build/export.py           # all micropod:* images, auto job count
#
# Output dir: SCRIPT_DIR/out.
# Prereq: docker on PATH.
# oci2mtk: used from PATH if present, else auto-fetched by get-oci2mtk.py.
# ===========================================================================
import functools
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NAME = "micropod"
SCRIPT_DIR = Path(__file__).resolve().parent
OCI2MTK_VER = "v1.2.0"
OUT = SCRIPT_DIR / "out"


# --- per-image worker -------------------------------------------------------
# docker save -> OCI tar, then oci2mtk rewrites it into the format RouterOS
# can import. The .tar.gz output extension makes oci2mtk gzip the result;
# -s strips the docker.io/library/ registry prefix.
def export_one(img, oci2mtk):
    tag = img.split(":", 1)[1]
    oci = OUT / f"{NAME}-{tag}.oci.tar"
    gz = OUT / f"{NAME}-{tag}.tar.gz"
    oci.unlink(missing_ok=True)
    gz.unlink(missing_ok=True)
    saved = subprocess.run(["docker", "save", img, "-o", str(oci)], capture_output=True)
    if saved.returncode != 0:
        print(f"    [{tag}] FAIL: docker save", file=sys.stderr)
        oci.unlink(missing_ok=True)
        return None
    converted = subprocess.run([oci2mtk, str(oci), "-s", "-f", "-o", str(gz)], capture_output=True)
    if converted.returncode != 0:
        print(f"    [{tag}] FAIL: oci2mtk", file=sys.stderr)
        oci.unlink(missing_ok=True)
        gz.unlink(missing_ok=True)
        return None
    oci.unlink(missing_ok=True)
    print(f"    [{tag}] -> {gz.name}")
    return gz


if __name__ == "__main__":
    start = time.perf_counter()

    # --- concurrency: half the online CPU count (>=1) -----------------------
    jobs = max((os.cpu_count() or 4) // 2, 1)

    # --- prereqs: docker must be usable before doing anything else ----------
    if not shutil.which("docker"):
        sys.exit("docker not found in PATH.")
    if subprocess.run(["docker", "version"], capture_output=True).returncode != 0:
        sys.exit("docker not usable (daemon not responding?).")

    # --- resolve oci2mtk: PATH if present, else download a pinned build -----
    oci2mtk = shutil.which("oci2mtk")
    if not oci2mtk:
        got = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "get-oci2mtk.py"), OCI2MTK_VER],
            text=True,
            capture_output=True,
        )
        oci2mtk = got.stdout.strip()
        if got.returncode != 0 or not oci2mtk:
            sys.exit("oci2mtk not found.")

    # --- find images --------------------------------------------------------
    listing = subprocess.run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    images = sorted(ln for ln in listing.splitlines() if ln.startswith(NAME + ":"))
    if not images:
        print(f"no {NAME}:* images found.")
        sys.exit(0)

    print(f"==> found {len(images)} image(s):")
    for img in images:
        print(f"    {img}")

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"==> exporting to {OUT} (up to {jobs} in parallel)...")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(functools.partial(export_one, oci2mtk=oci2mtk), images))
    elapsed = time.perf_counter() - start
    print(f"==> done in {elapsed:.2f}s")
