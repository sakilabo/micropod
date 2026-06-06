# micropod — notes for Claude

> Read `.claude/MEMORY.md` first if present (in-repo project working memory). Public overview / architecture / tags / usage live in [README.md](README.md); settled design rationale and project state live in `.claude/` memory. This file holds only implementation-critical facts that bite when editing the build.

## armv5 is the binding constraint

- armv5 (= `linux/arm/v5` = Debian armel) is **Debian-only**; Alpine ships no armel, so the `debian` tag is the only armv5-capable build.
- **Debian 13 "trixie" is the LAST release with armel** (14 "forky" drops it). A future base bump must pin an older Debian for the armv5 build — not just move the tag forward.

## Build / test gotchas (Windows + Docker Desktop, buildx + QEMU)

- `linux/arm/v5` is **not advertised** by binfmt even after `tonistiigi/binfmt --install all`, but `qemu-arm` executes armv5 anyway — building and running both work (verified end-to-end).
- Multi-arch `--load` is impossible; load one platform at a time to test.
- Build/push with **`provenance: false` and `sbom: false`**. Otherwise buildx attaches SLSA-provenance and SBOM as extra attestation manifests, turning the image into a manifest list RouterOS' picky pull rejects. These flags keep a plain manifest.
- Device testing needs a **docker-archive TAR**: `docker save <image> -o f.tar` (one single-arch tar per device). NOT buildx `--output type=tar` — a different format.
- PowerShell:
  - `docker save -o file.tar`, **never** `docker save > file.tar` (`>` writes UTF-16 and corrupts the tar).
  - Don't pair `$ErrorActionPreference='Stop'` with native-command stderr; pass `--platform` to `docker run` to silence the platform-mismatch warning.
