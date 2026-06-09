#!/usr/bin/env python3
# ===========================================================================
# build.py — build the micropod base image for every tag, then boot each and
# test (boot, s6 supervision, graceful stop). Base images are kept; nothing
# else is created.
#
#   python build/build.py                    # build + test all tags
#   python build/build.py --tag debian-armv5 # only the given tag
#   python build/build.py --without-test     # build only, skip the test phase
#
# Output dir: SCRIPT_DIR/out (per-tag build logs micropod-<tag>.log).
# Prereq: docker + buildx on PATH (Docker Desktop ships the QEMU emulators).
# ===========================================================================
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NAME = "micropod"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
OUT = SCRIPT_DIR / "out"

# tag -> (dockerfile, buildx platform). The key is the image tag (micropod:<key>).
MAP = {
    "alpine-arm64": ("Dockerfile.alpine", "linux/arm64"),
    "alpine-armv7": ("Dockerfile.alpine", "linux/arm/v7"),
    "debian-arm64": ("Dockerfile.debian", "linux/arm64"),
    "debian-armv7": ("Dockerfile.debian", "linux/arm/v7"),
    "debian-armv5": ("Dockerfile.debian", "linux/arm/v5"),
}

# Parallelism: builds use all cores; tests are load-sensitive (timing the
# graceful stop), so keep them to about half the cores.
BUILD_PARALLEL = os.cpu_count() or 4
TEST_PARALLEL = max((BUILD_PARALLEL + 1) // 2, 1)

# Platforms tonistiigi/binfmt can register a QEMU emulator for — i.e. the ones
# running it could actually make buildable. arm/v5 is included because it runs
# on the same qemu-arm as arm/v7 (binfmt installs it but never advertises v5).
# Source: https://github.com/tonistiigi/binfmt
BINFMT_PLATFORMS = {
    "linux/amd64",
    "linux/386",
    "linux/arm64",
    "linux/arm/v7",
    "linux/arm/v6",
    "linux/arm/v5",
    "linux/riscv64",
    "linux/ppc64le",
    "linux/s390x",
}


# Platforms the current buildx builder can build (from `docker buildx inspect`,
# which reflects the registered QEMU binfmt handlers). Empty set if unknown.
def buildx_platforms():
    info = subprocess.run(["docker", "buildx", "inspect"], capture_output=True, text=True)
    if info.returncode != 0:
        return set()
    plats = set()
    for line in info.stdout.splitlines():
        line = line.strip()
        if line.startswith("Platforms:"):
            plats.update(p.strip() for p in line[len("Platforms:") :].split(",") if p.strip())
    return plats


# --- phase 1: build one base image ------------------------------------------
# Streams buildx output to build/out/micropod-<tag>.log (UTF-8) so a broken
# build is debuggable without interleaving every tag's live log.
def build_one(tag):
    df, plat = MAP[tag]
    base = f"{NAME}:{tag}"
    log = OUT / f"{NAME}-{tag}.log"
    with open(log, "w", encoding="utf-8") as f:
        print(f"==> [{tag}] docker buildx build base ({base})", file=f)
        print(
            f"    docker buildx build --platform {plat} -f {df} --provenance=false --sbom=false --load -t {base}",
            file=f,
        )
        print("", file=f)
        f.flush()
        proc = subprocess.run(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                plat,
                "-f",
                str(REPO / df),
                "-t",
                base,
                "--provenance=false",
                "--sbom=false",
                "--load",
                str(REPO),
            ],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    if proc.returncode != 0:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n!! base build failed (see {log.name})\n")
        return tag, False, f"log={log.name}; base build failed"
    print(f"    [{tag}] built")
    return tag, True, f"log={log.name}"


# --- phase 2: boot one image and test it ------------------------------------
# Boots the base with a generated `hello` service bind-mounted (rw, so s6 can
# write its supervise/event state), then checks boot, supervision and graceful
# stop. Timing is load-sensitive — keep TEST_PARALLEL low for accuracy.
def test_one(tag):
    df, plat = MAP[tag]
    base = f"{NAME}:{tag}"
    cname = f"mptest-{tag}"
    svc = OUT / f"sv-{tag}" / "hello"
    notes = [f"log={NAME}-{tag}.log"]
    ok = True
    try:
        svc.mkdir(parents=True, exist_ok=True)
        run = svc / "run"
        # newline="\n" so Windows doesn't rewrite \n -> \r\n; a CRLF shebang
        # would make the in-container exec of this script fail.
        with open(run, "w", newline="\n") as f:
            print("#!/bin/sh", file=f)
            print(f'echo "{NAME}: hello started"', file=f)
            print("exec tail -f /dev/null", file=f)
        # native Linux/mac bind-mount: s6-supervise execs run, so it must be +x.
        # Docker Desktop mounts are permissive on Windows -> skip there.
        if sys.platform != "win32":
            os.chmod(run, 0o755)

        subprocess.run(["docker", "rm", "-f", cname], capture_output=True)
        started = subprocess.run(
            ["docker", "run", "-d", "--platform", plat, "--name", cname, "-v", f"{svc}:/etc/s6/sv/hello", base],
            capture_output=True,
        )
        if started.returncode != 0:
            raise RuntimeError("docker run failed")
        time.sleep(4)
        logs = subprocess.run(["docker", "logs", cname], capture_output=True, text=True)
        logs_out = logs.stdout + logs.stderr
        top = subprocess.run(["docker", "top", cname], capture_output=True, text=True).stdout
        t0 = time.perf_counter()
        subprocess.run(["docker", "stop", "-t", "10", cname], capture_output=True)
        sec = time.perf_counter() - t0
        subprocess.run(["docker", "rm", "-f", cname], capture_output=True)

        if f"{NAME}: hello started" not in logs_out:
            ok = False
            notes.append("no service log")
        if "s6-svscan" not in top:
            ok = False
            notes.append("no s6-svscan")
        if "s6-supervise" not in top:
            ok = False
            notes.append("no s6-supervise")
        if sec >= 9:
            ok = False
            notes.append(f"slow stop {sec:.1f}s (not graceful)")
        else:
            notes.append(f"stop={round(sec, 1)}s")
    except Exception as e:
        ok = False
        notes.append(str(e))
    finally:
        shutil.rmtree(svc.parent, ignore_errors=True)
    return tag, ("PASS" if ok else "FAIL"), "; ".join(notes)


if __name__ == "__main__":
    start = time.perf_counter()
    selected, without_test = list(MAP), False
    argv = iter(sys.argv[1:])
    for a in argv:
        if a == "--without-test":
            without_test = True
            continue
        if a == "--tag":
            tag = next(argv, None)
            if tag is None:
                sys.exit("--tag requires a value")
            if tag not in MAP:
                sys.exit(f"unsupported tag: {tag} (choose from: {', '.join(MAP)})")
            selected = [tag]
            continue
        sys.exit(f"unknown argument: {a}")

    # --- preflight: docker + buildx must be usable --------------------------
    if not shutil.which("docker"):
        sys.exit("docker not found in PATH. Install Docker and start the daemon.")
    if subprocess.run(["docker", "buildx", "version"], capture_output=True).returncode != 0:
        sys.exit("docker buildx unavailable. Install the buildx plugin and ensure Docker is running.")

    OUT.mkdir(parents=True, exist_ok=True)

    # Platforms buildx can't already build. arm/v5 is never advertised even when
    # working — it shares qemu-arm with arm/v7, so treat it as buildable when
    # arm/v7 is.
    supported = buildx_platforms()
    if "linux/arm/v7" in supported:
        supported.add("linux/arm/v5")
    missing = {MAP[t][1] for t in selected} - supported

    # Only run binfmt for the missing platforms it can actually provide; bail if
    # anything is missing that it can't (pulling it would be pointless).
    unfixable = missing - BINFMT_PLATFORMS
    if unfixable:
        sys.exit(f"no binfmt support for: {', '.join(sorted(unfixable))}")
    if missing:
        print(f"==> installing QEMU binfmt for: {', '.join(sorted(missing))}")
        subprocess.run(["docker", "run", "--privileged", "--rm", "tonistiigi/binfmt", "--install", "all"])

    # fresh logs + stale probe dirs
    for t in selected:
        (OUT / f"{NAME}-{t}.log").unlink(missing_ok=True)
        shutil.rmtree(OUT / f"sv-{t}", ignore_errors=True)

    # Barrier between phases (not a pipeline): builds must finish before tests,
    # so build load can't skew the test phase's graceful-stop timing.

    # --- phase 1: build -----------------------------------------------------
    print(f"==> Phase 1: building {len(selected)} image(s), up to {BUILD_PARALLEL} in parallel...")
    with ThreadPoolExecutor(max_workers=BUILD_PARALLEL) as pool:
        built = list(pool.map(build_one, selected))

    # --- phase 2: test (unless --without-test) ------------------------------
    results = []  # (tag, result, notes)
    if without_test:
        for tag, ok, notes in built:
            results.append((tag, "OK" if ok else "FAIL", notes))
    else:
        print(f"==> Phase 2: testing, up to {TEST_PARALLEL} in parallel...")
        to_test = [tag for tag, ok, _ in built if ok]
        result_by_tag = {}
        with ThreadPoolExecutor(max_workers=TEST_PARALLEL) as pool:
            for tag, res, notes in pool.map(test_one, to_test):
                result_by_tag[tag] = (res, notes)
        for tag, ok, notes in built:
            if ok and tag in result_by_tag:
                results.append((tag, *result_by_tag[tag]))
            else:
                results.append((tag, "FAIL", notes))

    # --- summary ------------------------------------------------------------
    print("\n=== Summary ===")
    width = max(len(t) for t in selected)
    for tag, res, notes in results:
        print(f"    {tag:<{width}}  {res:<4}  {notes}")
    elapsed = time.perf_counter() - start
    print(f"logs: {OUT}   (base images kept; run export.py to package, cleanup.py to remove)")
    print(f"==> done in {elapsed:.2f}s")

    sys.exit(1 if any(res == "FAIL" for _, res, _ in results) else 0)
