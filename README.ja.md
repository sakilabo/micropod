# micropod

MikroTik RouterOS 環境で、1つのコンテナに複数サービスを実装するためのベースイメージです。

- s6 で複数のサービスを管理する構成です。
  複数サービスを1コンテナに統合することで、コンテナ毎に発生するオーバーヘッドを回避できます。
- BusyBox アプレットで各種コマンドを実行できます。
  コンテナ開発環境がなくてもサービスを構築できるようになっています。
- Alpine (arm64 / armv7) と Debian (arm64 / armv7 / armv5) に対応しています。

## タグとアーキテクチャ

イメージは `ghcr.io/sakilabo/micropod` で公開されています。

| タグ     | ベース               | arm64 | armv7 | armv5 |
| -------- | -------------------- | :---: | :---: | :---: |
| `alpine` | `alpine:3.23`        |   ✅   |   ✅   |   ❌   |
| `debian` | `debian:trixie-slim` |   ✅   |   ✅   |   ✅   |
| `latest` | → `alpine`           |       |       |       |

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

## RouterOS の注意事項

- コンテナ作成時に `root-dir=` を設定することを **強く推奨** します。`root-dir=` を省略した場合、コンテナ作成後にコンテナの設定が変更出来なくなります。注意してください。
- コンテナイメージとして、ローカル環境で .tar ファイルを利用する場合、docker-archive 形式のコンテナが必要です。RouterOS のコンテナ機能は OCI レイアウトの .tar ファイルに対応していません。

## ライセンス

[UPL-1.0](LICENSE)

## 著者

Sakilabo Corporation Ltd.
