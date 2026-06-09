# Build

Local build harness for the micropod base images: builds, tests, and packages MikroTik-loadable tars. (The canonical CI build is `.github/workflows/test.yml`; the root `Dockerfile.*` are the images themselves.)

Three Python scripts, run directly with `python`. Targets are tags (`--tag`), each tag being one output image (`debian-armv5` → `micropod:debian-armv5`).

- **[build.py](build.py)** — builds each base image with `docker buildx` (`--provenance=false --sbom=false --load`) and tests that it boots, brings up s6 supervision, and stops gracefully with a generated `hello` service. Keeps `micropod:<tag>` for `export.py`. If the current buildx builder is missing a QEMU emulator for a selected platform, it registers full binfmt first (`tonistiigi/binfmt --install all`, privileged). armv5 shares `qemu-arm` with armv7, so it is treated as buildable whenever armv7 is.
- **[export.py](export.py)** — finds local `micropod:*` images and packages each into a RouterOS-loadable `.tar.gz` in `build/out/`. Each image is `docker save`d to an OCI tar, then `oci2mtk` rewrites it into the format RouterOS imports.
- **[cleanup.py](cleanup.py)** — removes all `micropod:*` images.

`oci2mtk` is used from `PATH` if present, otherwise a pinned release is fetched automatically by [get-oci2mtk.py](get-oci2mtk.py) into `build/tools/` (cached).

## Prerequisites

- Python 3.
- Docker:
  - A running Docker daemon, `docker buildx` on `PATH`.
  - QEMU emulators for the target platforms; build.py registers them via `tonistiigi/binfmt` if missing (Docker Desktop already ships them).
- Windows / macOS / Linux on amd64 / arm64.

## Usage

```sh
python build/build.py                     # build + test all tags
python build/build.py --tag debian-armv5  # only the given tag
python build/build.py --without-test      # build only, skip the test phase
python build/export.py                    # package all built micropod:* images
python build/cleanup.py                   # drop all micropod images
```

Tags: `alpine-arm64`, `alpine-armv7`, `debian-arm64`, `debian-armv7`, `debian-armv5`.

Per-tag build logs land in `build/out/micropod-<tag>.log`.

VS Code: the same operations are wired as tasks (`.vscode/tasks.json`); the default test task is build + test, the default build task is build-only.

## Exported files

`export.py` writes `build/out/micropod-<tag>.tar.gz` — one single-architecture image per file, in the format RouterOS imports.

### Testing a tar on a MikroTik device

Each router is one architecture — pick the matching tar (e.g. `debian-armv5` for an EN7562CT / hEX Refresh). Upload it to the router's storage (Files), then:

```
/container/add \
    name=micropod \
    interface=veth1 \
    file=usb1/micropod-debian-armv5.tar.gz \
    root-dir=usb1/micropod \
    start-on-boot=yes

/container/print    # wait for Flags to go from "E" (extracting) to "S" (stopped)
/container/start 0
/container/shell 0  # attach to the container console
```
