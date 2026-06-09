#!/usr/bin/env python3
# ===========================================================================
# cleanup.py — remove ALL micropod:* images.
#
#   python build/cleanup.py
#
# Prereq: docker on PATH.
# ===========================================================================
import shutil
import subprocess
import sys

NAME = "micropod"

if __name__ == "__main__":
    if not shutil.which("docker"):
        sys.exit("docker not found in PATH.")

    listing = subprocess.run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    imgs = [ln for ln in listing.splitlines() if ln.startswith(NAME + ":")]
    if not imgs:
        print(f"==> no {NAME} images to remove.")
        sys.exit(0)

    print(f"==> removing {len(imgs)} image(s)...")
    for img in imgs:
        subprocess.run(["docker", "image", "rm", img], capture_output=True)
        print(f"    rm {img}")
