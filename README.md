# micropod

A base image for running multiple services in a single container on MikroTik RouterOS.

- Manages multiple services with s6.
  Consolidating multiple services into a single container avoids the per-container overhead.
- Various commands are available through BusyBox applets.
  Services can be built without a container development environment.
- Supports Alpine (arm64 / armv7) and Debian (arm64 / armv7 / armv5).

## Tags & architectures

The images are published at `ghcr.io/sakilabo/micropod`.

| Tag                | Base                 | arm64 | armv7 | armv5 |
| ------------------ | -------------------- | :---: | :---: | :---: |
| `alpine`           | `alpine:3.23`        |  ✅  |  ✅  |  ❌  |
| `debian`, `latest` | `debian:trixie-slim` |  ✅  |  ✅  |  ✅  |

## Startup

micropod has two startup methods.

### `ENTRYPOINT ["/usr/bin/s6-svscan", "/etc/s6/sv"]` (default)

- Runs with minimal resources.
- `inittab` is not available.

### `ENTRYPOINT ["/sbin/init"]`

- Starts BusyBox `init`.
- `inittab` becomes available.

## Services

### Built-in services

Three services run out of the box.

| Service  | Implementation | Directory           | Notes                                                       |
| -------- | -------------- | ------------------- | ----------------------------------------------------------- |
| `crond`  | `BusyBox`      | `/etc/s6/sv/crond`  | Place crontabs at `/etc/crontabs/<user>`.                   |
| `sshd`   | `dropbear`     | `/etc/s6/sv/sshd`   | To enable it, set a password or `authorized_keys`.          |
| `udhcpc` | `BusyBox`      | `/etc/s6/sv/udhcpc` | DHCP client. Overwrites `/etc/resolv.conf`.                 |

`udhcpc` targets the first non-loopback interface discovered in lexical order.

### Managing services

- To add a service, create an `/etc/s6/sv/<name>/run` file.
- Make the run file `#!/bin/sh` + `exec <daemon>`, with permission 755.
- To **stop a service from auto-starting**, create an empty `down` file in the service directory.

## Networking

The network can be used in two ways.

### Run the DHCP client in the container (default)

- The network can be managed by a DHCP server.
- Do not set `address=` on the VETH.
- Do not set `dns=` on the container.

### Assign the IP address on RouterOS

- Create an `/etc/s6/sv/udhcpc/down` file to stop `udhcpc` from auto-starting.
- Set `address=` on the VETH and `dns=` on the container.

## Commands

### BusyBox applets

All BusyBox applets are placed in `/usr/share/busybox/bin`, which is appended to `PATH`.

## RouterOS notes

- Setting `root-dir=` when creating the container is **strongly recommended**. If `root-dir=` is omitted, the container's configuration cannot be changed after the container is created. Be careful.
- When using a local .tar file as the container image, a docker-archive format container is required. The RouterOS container feature does not support OCI layout .tar files.

## License

[UPL-1.0](LICENSE)

## Author

Sakilabo Corporation Ltd.
