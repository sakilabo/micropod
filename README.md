# micropod

[日本語](README.ja.md)

A base image for running multiple services in a single container on MikroTik RouterOS.

- Manages multiple services with s6.
  Consolidating multiple services into a single container avoids the per-container overhead.
- Various commands are available through BusyBox applets.
  Services can be built without a container development environment.
- Supports Alpine (arm64 / armv7) and Debian (arm64 / armv7 / armv5).

### Distribution

micropod images are published on GHCR (GitHub Container Registry).

[https://ghcr.io/sakilabo/micropod](https://ghcr.io/sakilabo/micropod)

## Usage

For details on the RouterOS container feature, see the [MikroTik documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/84901929/Container).

### 1. Enable container mode

The first time you use the container feature, you need to enable container mode.

```
/system/device-mode/update container=yes
```

### 2. Configure the container registry

micropod is published on GHCR (GitHub Container Registry). Configure RouterOS to use GHCR as follows.

```
/container/config/set registry-url=https://ghcr.io
```

### 3. Prepare a VETH

Adding a container requires a VETH interface. Prepare one.

As an example, the following creates an interface named `veth-local` and connects it to the LAN through an existing local bridge `bridge-local`.

```
/interface/veth/add name=veth-local
/interface/bridge/port/add bridge=bridge-local interface=veth-local
```

By default, micropod runs a DHCP client. You do not need to assign an IP address to the VETH.

### 4. Add the container

An example command to add the container is shown below.

```
/container/add name=CONTAINER_NAME remote-image=sakilabo/micropod:alpine interface=veth-local root-dir=ROOT_DIR
```

Adjust the parameters to your environment using the notes below.

- `name=CONTAINER_NAME` — The container name. Set any name you like.
- `remote-image=sakilabo/micropod:alpine` — The image to pull from GHCR. Here `sakilabo/micropod:alpine` is specified. Note that the Alpine image does not support armv5 environments such as the hEX. If you need armv5 support, use `sakilabo/micropod:debian`.
- `interface=veth-local` — Specify the VETH interface prepared in step 3.
- `root-dir=ROOT_DIR` — The container root directory. This parameter is optional, but setting it is **strongly recommended**. If omitted, the container's configuration cannot be changed after the container is created. Set any directory that suits your environment.

### 5. Verify operation

Connect to the container console and verify operation.

Check the container status. This step is required.

```
/container/print
```

You will get output like the following.

```
Flags: S - STOPPED
Columns: NAME, ROOT-DIR, INTERFACE, CPU-USAGE, TAG
#   NAME            ROOT-DIR   INTERFACE   CPU-USAGE  TAG                             
0 S CONTAINER_NAME  /ROOT_DIR  veth-local          0  ghcr.io/sakilabo/micropod:alpine
```

Confirm that Flags shows `S (stopped)`, then start the container with the following command.

```
/container/start 0
```

The container starts in a few seconds. Once Flags shows `R (running)`, the container is running. Connect to the console with the following command.

```
/container/shell 0
```

Once connected, check that the services are running. `crond`, `sshd (dropbear)`, and `udhcpc` should be running.

```
/ # ps aux
PID   USER     TIME  COMMAND
    1 root      0:00 /usr/bin/s6-svscan /etc/s6/sv
    2 root      0:00 s6-supervise udhcpc
    3 root      0:00 s6-supervise sshd
    4 root      0:00 s6-supervise crond
    5 root      0:00 udhcpc -i veth-local -f -s /etc/udhcpc/default.script
    6 root      0:00 dropbear -F -E -R
    7 root      0:00 crond -f -c /etc/crontabs -L /dev/stderr
   17 root      0:00 /bin/sh
   18 root      0:00 ps aux
```

## Tags & architectures

| Tag                | Base                 | arm64 | armv7 | armv5 |
| ------------------ | -------------------- | :---: | :---: | :---: |
| `debian`, `latest` | `debian:trixie-slim` |  ✅  |  ✅  |  ✅  |
| `alpine`           | `alpine:3.23`        |  ✅  |  ✅  |  ❌  |

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

### APT (Debian)

`APT::Install-Recommends "false"` is set to keep package installation minimal.

## Building a custom image (TAR file)

### Prerequisites

- Windows / macOS / Linux
- amd64 / arm64
- The `docker buildx` command is available
- `oci2mtk` is available (distributed at the URLs below)
  - Repository: [https://github.com/sakilabo/oci2mtk-go](https://github.com/sakilabo/oci2mtk-go)
  - Release: [https://github.com/sakilabo/oci2mtk-go/releases](https://github.com/sakilabo/oci2mtk-go/releases)

### Example Dockerfile

```
# syntax=docker/dockerfile:1

# micropod — sample: PostgreSQL on the Debian base.
#   Base:     ghcr.io/sakilabo/micropod:debian (arm64 / armv7 / armv5)
#   Adds:     PostgreSQL (Debian trixie ships 17) as an s6 service.
#
# No rootfs files are added — the s6 service is generated entirely by commands.

FROM ghcr.io/sakilabo/micropod:debian

# Data directory (build-time configurable; kept in the env for the run script).
ARG PGDATA_DIR=/var/lib/postgresql/data
ENV PGDATA=${PGDATA_DIR}

RUN <<EOF
set -e

# Install PostgreSQL.
apt-get update
apt-get install -y postgresql-17
rm -rf /var/lib/apt/lists/*

# Generate the s6 service.
mkdir -p /etc/s6/sv/postgresql
cat > /etc/s6/sv/postgresql/run <<'EOF_RUN'
#!/bin/sh
PGBIN=/usr/lib/postgresql/17/bin
# Initialise the cluster on first start.
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    install -d -o postgres -g postgres -m 0700 "$PGDATA"
    su postgres -s /bin/sh -c "$PGBIN/initdb -D $PGDATA"
    echo "listen_addresses = '*'" >> "$PGDATA/postgresql.conf" # Listen on all interfaces.
fi
exec su postgres -s /bin/sh -c "$PGBIN/postgres -D $PGDATA"
EOF_RUN
chmod 0755 /etc/s6/sv/postgresql/run
EOF

EXPOSE 5432
```

### Steps to create the TAR file

```
docker buildx build -f <DOCKER_FILE> --platform <TARGET> -t <TAG> --load
docker save <TAG> -o <TAR_FILE>.tar
oci2mtk <TAR_FILE>.tar -s -o <CONTAINER>.tar.gz
```

Copy `<CONTAINER>.tar.gz` to RouterOS and run `/container add file=<CONTAINER>.tar.gz`.

## License

[UPL-1.0](LICENSE)

## Author

Sakilabo Corporation Ltd.
