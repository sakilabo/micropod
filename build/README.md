# Build

Local build harness for the micropod base images: builds, verifies, and packages MikroTik-loadable tars. (The canonical CI build is `.github/workflows/build.yml`; the root `Dockerfile.*` are the images themselves.)

`run.ps1` has three modes (`-Mode build | tar | cleanup`; running with no `-Mode` does nothing). Targets are tags (`-Tag`), each tag being one output image (`debian-armv5` → `micropod:debian-armv5`).

- **build** — builds each base image and verifies it boots and stops cleanly with a sample `hello` service. Keeps `micropod:<tag>` for `-Mode tar`. For an armv5 tag, first registers full QEMU binfmt (`tonistiigi/binfmt --install all`, privileged) — Docker Desktop drops it on each restart.
- **tar** — packages existing `micropod:<tag>` images into RouterOS-loadable tars in `build/out/`, using `quay.io/podman/stable` (privileged, pulled on first use) to rewrite each into the legacy docker-archive layout RouterOS imports.
- **cleanup** — removes all `micropod:*` images.

## Prerequisites

Docker Desktop running. On Linux/macOS, PowerShell Core (`pwsh`).

## Usage

```powershell
.\build\run.ps1 -Mode build                    # build + verify all tags
.\build\run.ps1 -Mode build -Tag debian-armv5  # a subset
.\build\run.ps1 -Mode tar                      # package built base images
.\build\run.ps1 -Mode cleanup                  # drop all micropod images
```

Tags: `alpine-arm64`, `alpine-armv7`, `debian-arm64`, `debian-armv7`, `debian-armv5`.

VS Code: the same operations are wired as tasks (`.vscode/tasks.json`); the default test task is build + verify.

## TAR files

`-Mode tar` writes `build/out/micropod-<tag>.tar` — one single-architecture image per file, in the legacy docker-archive layout RouterOS imports.

### Testing a tar on a MikroTik device

Each router is one architecture — pick the matching tar (e.g. `debian-armv5` for an EN7562CT / hEX Refresh). Upload it to the router's storage (Files), then:

```
/container/add \
    name=micropod \
    interface=veth1 \
    file=usb1/micropod-debian-armv5.tar \
    root-dir=usb1/micropod \
    start-on-boot=yes

/container/print    # wait for Flags to go from "E" (extracting) to "S" (stopped)
/container/start 0
/container/shell 0  # attach to the container console
```
