# micropod

[English](README.md)

MikroTik RouterOS 環境で、1つのコンテナに複数サービスを実装するためのベースイメージです。

- s6 で複数のサービスを管理する構成です。
  複数サービスを1コンテナに統合することで、コンテナ毎に発生するオーバーヘッドを回避できます。
- BusyBox アプレットで各種コマンドを実行できます。
  **コンテナ開発環境がなくてもサービスを構築できる**ようになっています。
- Alpine (arm64 / armv7) と Debian (arm64 / armv7 / armv5) に対応しています。

### 配布場所

micropod のイメージは GHCR (GitHub Container registry) で公開されています。

[https://ghcr.io/sakilabo/micropod](https://ghcr.io/sakilabo/micropod)

## 使い方

RouterOS コンテナ機能の詳細については [MikroTik のドキュメント](https://help.mikrotik.com/docs/spaces/ROS/pages/84901929/Container) を参照してください。

### 1. コンテナモードを有効にする

コンテナ機能をはじめて利用する場合には、コンテナモードを有効にする必要があります。

```
/system/device-mode/update container=yes
```

### 2. コンテナの Config を設定する

micropod は GHCR (GitHub Container registry) で公開されています。RouterOS で GHCR を利用できるようにするための設定は以下の通りです。

```
/container/config/set registry-url=https://ghcr.io
```

### 3. VETH を用意する

コンテナを追加するには VETH インターフェースが必要です。VETH インターフェースを用意してください。

例として、`veth-local` というインターフェースを作成し、既存のローカルブリッジ `bridge-local` を介して LAN に接続するケースを示します。

```
/interface/veth/add name=veth-local
/interface/bridge/port/add bridge=bridge-local interface=veth-local
```

micropod は、初期設定で DHCP クライアントが動作します。VETH に IP アドレスを設定する必要はありません。

### 4. コンテナを追加する

コンテナを追加するコマンドの例を以下に示します。

```
/container/add name=CONTAINER_NAME remote-image=sakilabo/micropod:alpine interface=veth-local root-dir=ROOT_DIR
```

コマンドのパラメーターについては以下の説明を参考に、実際の環境に合わせて対応してください。

- `name=CONTAINER_NAME` ― コンテナの名前です。任意の名前を設定してください。
- `remote-image=sakilabo/micropod:alpine` ― GHCR から取得するコンテナの名称です。ここでは `sakilabo/micropod:alpine` を指定しています。なお、Alpine のイメージは hEX などの armv5 環境に対応していません。armv5 への対応が必要な場合には `sakilabo/micropod:debian` を利用してください。
- `interface=veth-local` ― 手順 3 で用意した VETH インターフェースを指定してください。
- `root-dir=ROOT_DIR` ― コンテナの root ディレクトリです。このパラメーターは省略可能ですが、設定することを**強く推奨**します。この設定を省略した場合、コンテナを追加した後にコンテナの設定を変更することができなくなってしまいます。実際の環境に合わせて任意のディレクトリを設定してください。

### 5. 動作を確認する

コンテナのコンソールに接続して、動作を確認します。

コンテナの状態を確認してください。この操作は必須です。

```
/container/print
```

以下のような出力が得られます。

```
Flags: S - STOPPED
Columns: NAME, ROOT-DIR, INTERFACE, CPU-USAGE, TAG
#   NAME            ROOT-DIR   INTERFACE   CPU-USAGE  TAG                             
0 S CONTAINER_NAME  /ROOT_DIR  veth-local          0  ghcr.io/sakilabo/micropod:alpine
```

Flags が `S (stopped)` になっていることを確認し、以下のコマンドでコンテナを起動してください。

```
/container/start 0
```

コンテナは数秒で起動します。Flags が `R (running)` になれば、コンテナは動作しています。以下のコマンドでコンソールに接続してください。

```
/container/shell 0
```

コンテナに接続したら、サービスが動作していることを確認してみましょう。`crond`, `sshd (dropbear)`, `udhcpc` が動作しているはずです。

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

## タグとアーキテクチャ

| タグ               | ベース               | arm64 | armv7 | armv5 |
| ------------------ | -------------------- | :---: | :---: | :---: |
| `debian`, `latest` | `debian:trixie-slim` |  ✅  |  ✅  |  ✅  |
| `alpine`           | `alpine:3.23`        |  ✅  |  ✅  |  ❌  |

## 起動方法

micropod には2つの起動方法があります。

### `ENTRYPOINT ["/usr/bin/s6-svscan", "/etc/s6/sv"]` (初期設定)

- 最小のリソースで動作します。
- `inittab` は使えません。

### `ENTRYPOINT ["/sbin/init"]`

- BusyBox の `init` が起動します。
- `inittab` を利用できます。

## サービス

### 組み込みサービス

初期状態で 3 つのサービスが動作しています。

| サービス | 実装       | ディレクトリ        | 備考                                                         |
| -------- | ---------- | ------------------- | ------------------------------------------------------------ |
| `crond`  | `BusyBox`  | `/etc/s6/sv/crond`  | crontab は `/etc/crontabs/<user>` に置く。                   |
| `sshd`   | `dropbear` | `/etc/s6/sv/sshd`   | 有効化するにはパスワードまたは `authorized_keys` を設定する。 |
| `udhcpc` | `BusyBox`  | `/etc/s6/sv/udhcpc` | DHCP クライアント。`/etc/resolv.conf` を上書きする。         |

`udhcpc` の対象インターフェースは、辞書順で最初に発見された非ループバックインターフェースとなります。

### サービスの管理方法

- サービスを追加する場合は `/etc/s6/sv/<name>/run` ファイルを作成してください。
- run ファイルの内容は `#!/bin/sh` + `exec <daemon>` として、パーミッション 755 としてください。
- **各サービスの自動起動を停止**したい場合は、サービスのディレクトリに空の `down` ファイルを作成してください。

## ネットワーク

2つの方法でネットワークを利用できるようになっています。

### コンテナ側で DHCP クライアントを実行 (初期設定)

- DHCP サーバーでネットワークを管理できます。
- VETH に `address=` を設定しないでください。
- コンテナに `dns=` を設定しないでください。

### RouterOS 側で IP アドレスを設定

- `/etc/s6/sv/udhcpc/down` ファイルを作成して `udhcpc` の自動起動を停止してください。
- VETH に `address=`、コンテナに `dns=` を設定してください。

## コマンド

### BusyBox アプレット

BusyBox の全アプレットが `/usr/share/busybox/bin` に置かれ、`PATH` 末尾に追加されています。

### APT (Debian)

パッケージのインストールを最小限とするため `APT::Install-Recommends "false"` に設定されています。

## カスタムイメージ (TAR ファイル) の作り方

### 前提条件

- Windows / macOS / Linux
- amd64 / arm64
- `docker buildx` コマンドが使える状態になっていること
- `oci2mtk` が使える状態になっていること (以下の URL で配付されています)
  - Repository: [https://github.com/sakilabo/oci2mtk-go](https://github.com/sakilabo/oci2mtk-go)
  - Release: [https://github.com/sakilabo/oci2mtk-go/releases](https://github.com/sakilabo/oci2mtk-go/releases)

### Dockerfile の例

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

### TAR ファイル作成手順

```
docker buildx build -f <DOCKER_FILE> --platform <TARGET> -t <TAG> --load
docker save <TAG> -o <TAR_FILE>.tar
oci2mtk <TAR_FILE>.tar -s -o <CONTAINER>.tar.gz
```

`<CONTAINER>.tar.gz` を RouterOS にコピーして、`/container add file=<CONTAINER>.tar.gz` してください。

## ライセンス

[UPL-1.0](LICENSE)

## 開発者

株式会社さきラボ
