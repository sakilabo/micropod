# micropod — notes for Claude

Read `.claude/MEMORY.md` first if present (in-repo project working memory). Overview / architecture / tags / usage live in [README.md](README.md).

Tags: alpine-{arm64,armv7}, debian-{arm64,armv7,armv5}. armv5 is debian-only (Alpine has no armel).

## Build / push / export gotchas

- Multi-arch `--load` is impossible; load one platform at a time to test.
- Build/push with **`provenance: false` and `sbom: false`**. Otherwise buildx attaches SLSA-provenance and SBOM as extra attestation manifests, turning the image into a manifest list RouterOS' picky pull rejects. These flags keep a plain manifest.
- RouterOS can't import a `docker save` tar. The device needs an oci2mtk-converted image: `docker save` to an OCI tar, then `oci2mtk` rewrites it into the RouterOS-importable `.tar.gz` (one single-arch image per device). See [build/export.py](build/export.py).
