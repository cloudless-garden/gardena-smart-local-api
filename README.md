<!--
SPDX-FileCopyrightText: 2026 GARDENA GmbH

SPDX-License-Identifier: LGPL-3.0-or-later
-->

# Python library for GARDENA smart local API

Enables controlling and monitoring GARDENA smart devices in the local network, without going through the cloud.

## Supported Devices

| Device                             | Article Number                             | Model (EAN suffix) |
| ---------------------------------- | ------------------------------------------ | ------------------ |
| smart Sensor                       | 19030-20                                   | 18845              |
| smart Sensor II                    | 19040-20                                   | 19040              |
| smart Water Control                | 19031-20                                   | 18869              |
| smart Water Control                | 19033-20                                   | 2812               |
| smart Dual Water Control           | 19034-20                                   | 2814               |
| smart Pipeline Water Control       | 19050-20                                   | 2826               |
| smart Automatic Home & Garden Pump | 19080-20                                   | 22538              |
| smart Irrigation Control           | 19032-20                                   | 31653              |
| smart Irrigation Control           | 19035-20                                   | 469                |
| smart Power Adapter                | 19095-20                                   | 35279              |
| smart SILENO                       | 19060-20, 19060-60                         | 6146               |
| smart SILENO+                      | 19061-20, 19061-60, 19064-60, 19065-60     | 6146               |
| smart SILENO city                  | 19066-20, 19069-20                         | 29694              |
| smart SILENO life                  | 19113-20, 19114-20, 19115-20               | 29694              |
| smart SILENO city (with LONA)      | 19602-66, 19603-60, 19605-60               | 53988              |
| smart SILENO life (with LONA)      | 19701-60, 19702-60, 19703-66, 19704-60     | 53988              |
| smart SILENO pro                   | 19802-20, 19802-22                         | 488                |
| smart SILENO max                   | 19901-22                                   | 488                |
| smart SILENO free                  | 19921-22, 19922-22, 19923-22               | 488                |
| Flymo UltraLife                    | 970620501, 970620701, 970715101, 970715201 | 488                |

## Installation

```txt
pip install gardena-smart-local-api
```

## Using the Library

Have a look at our [example code][examples].

You can run the examples from within the repository as follows:

```txt
uv sync --group examples
uv run gardena_smart_local_api/examples/irrigation.py --help
```

[examples]: https://github.com/cloudless-garden/gardena-smart-local-api/tree/main/gardena_smart_local_api/examples

## Contributing

### Debugging

Various strategies exist to figure out why things are not working the way you want them to. This section lists some
common ones.

#### Verbose logging on the gateway

websocketd:

```
mkdir -p /etc/systemd/system/websocketd.service.d
cat << EOF > /etc/systemd/system/websocketd.service.d/debug.conf
[Service]
Environment=RUST_LOG=debug
EOF
systemctl daemon-reload && systemctl restart websocketd.service
```

lemonbeatd:

```
mkdir -p /etc/systemd/system/lemonbeatd.service.d
cat << EOF > /etc/systemd/system/lemonbeatd.service.d/debug.conf
[Service]
Environment=RUST_LOG=debug
EOF
systemctl daemon-reload && systemctl restart lemonbeatd.service
```

lwm2mserver (add `--log-level=lwm2mserver.event=DEBUG` as a argument to lwm2mserver):

```
mkdir -p /etc/systemd/system/lwm2mserver.service.d
cat << EOF > /etc/systemd/system/lwm2mserver.service.d/debug.conf
[Service]
ExecStart=
ExecStart=/usr/bin/lwm2mserver ppp0 --bind-to-device \\
                                    --server-uri "coap://[fc00::6:100:0:0]" \\
                                    --port 20017 \\
                                    --lemonbeat-dongle-connection \\
                                    --state-storage /var/lib/lwm2mserver \\
                                    --lb-key-file /var/lib/lemonbeatd/Network_management/Network_key.json \\
                                    --ipso-directories "\${IPSO_REGISTRY_DIR}/base" "\${IPSO_REGISTRY_DIR}/fwrolloutd" "\${IPSO_REGISTRY_DIR}/dev" \\
                                    --log-level=lwm2mserver.event=DEBUG \\
EOF
systemctl daemon-reload && systemctl restart lwm2mserver.service
```

cloudadapter:

```
mkdir -p /etc/systemd/system/cloudadapter.service.d
cat << EOF > /etc/systemd/system/cloudadapter.service.d/debug.conf
[Service]
ExecStart=
ExecStart=/usr/bin/cloudadapter --verbosity --debug
EOF
systemctl daemon-reload && systemctl restart cloudadapter.service
```

> [!TIP]
> Cloudadapter is not needed for local usage and disabling the service saves resources. However, for reverse-engineering
> how the services react to actions in the app, keeping the cloudadapter running and increasing its verbosity is helpful.

### Commits

Try to keep commits reviewable, i.e. they should only contain one logical change and generally not be too big.

As we use rebase to integrate pull requests, clean commits matter. Use commands like `git commit --amend`,
`git commit --fixup ...` and `git rebase --interactive ...` to rework your commits. Should this be too advanced for you,
just push temporary commits and when review is done, run e.g.:

```txt
git fetch
git rebase origin/main
git reset origin/main
git commit --all
git push --force-with-lease
```

For the commit message(s), follow [these guidelines][commits]. If you are unsure how to formulate your commit messages,
look at `git log` for inspiration.

[commits]: https://cbea.ms/git-commit/

### Linting

```txt
uv sync --all-groups
uv run ruff check
uv run ruff format --check
uv run ty check
```

### Running Tests

```txt
uv sync --group test
uv run python -m pytest
```

### Licensing Compliance

```txt
uv run reuse lint
```
