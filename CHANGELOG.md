# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0/).

## [0.1.1] - 2026-06-06

### Changed

- Pinned `latest` to the Debian image (covers all architectures).

## [0.1.0] - 2026-06-06

### Added

- s6-supervised base image for running multiple services in a single MikroTik RouterOS container.
- Alpine variant (arm64, armv7) and Debian variant (arm64, armv7, armv5); armv5 is Debian-only.
- Built-in services: `crond`, `sshd` (dropbear), and `udhcpc`.
- Two startup modes: `s6-svscan` (default) and BusyBox `init` via `/sbin/init` for `inittab` support.
- BusyBox applets available on `PATH` under `/usr/share/busybox/bin`.
- Published to `ghcr.io/sakilabo/micropod` with `alpine`, `debian`, and `latest` tags.

[0.1.1]: https://github.com/sakilabo/micropod/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/sakilabo/micropod/releases/tag/v0.1.0
