# 2026-07-26 — explicit trusted-LAN dashboard binding

## What changed

`watch.py` may now bind to an explicitly selected numeric IPv4 or IPv6 address
and accept an exact allowlist of HTTP Host names/addresses:

```sh
python3 watch.py --target . \
  --bind 0.0.0.0 \
  --allow-host xsm \
  --allow-host 192.168.1.20 \
  --url-host xsm
```

The default is unchanged: without these flags the dashboard binds only to
`127.0.0.1` and accepts the established loopback aliases.

Every request now validates `Host` before target data is read. Browser POSTs
also validate a matching HTTP `Origin` before the body is read or written to
the submission witness. This blocks DNS-rebinding and cross-site browser writes;
it does **not** authenticate another client on the LAN.

Non-loopback startup prints a warning because trusted-LAN mode is deliberately
unauthenticated. Public/WAN exposure remains unsupported.

## How to apply

No target state or file format changes. Existing deployments need no action and
remain loopback-only.

To opt into a trusted LAN, choose one explicit bind address and list every
exact Host token users will enter. Wildcard binds require an allowed navigable
`--url-host`. A concrete bind may default its advertised URL to that address
only when the address is itself allowlisted; otherwise pass an allowed
`--url-host`. Do not expose the port to an untrusted or public network. Later
bearer-token and public Dreamhub authentication are separate features, not
implied by this migration.
