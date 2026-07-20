---
name: windows-proxy-route-manager
description: Diagnose and fix Windows and macOS application proxy configuration and local network route bypass issues. Use when development tools or desktop apps cannot reach required services through an approved local or enterprise HTTP proxy, or when VPN/private/internal domains and IP ranges must bypass a local proxy so corporate network resources remain reachable.
---

# Windows/macOS Proxy Route Manager

## Overview

Use this skill for Windows/macOS proxy diagnostics and private-network route management in development or enterprise environments. It helps decide whether an app should use a configured local/enterprise proxy or whether a private/VPN destination should bypass that proxy.

This skill does not provide proxy servers, credentials, traffic tunnels, remote endpoints, or access-circumvention services. Use it only on networks and systems where you have authorization.

## Decision Tree

1. Identify the failing destination.
   - External development service: package registries, source repositories, API endpoints, artifact repositories.
   - Internal resource: company domains, VPN-only services, private IPs, CIDR ranges, or host mappings such as `internal.example.test=10.0.0.10`.
2. If an external service times out while the organization-approved proxy is running:
   - On Windows, run `scripts/diagnose-windows-app-proxy.ps1`.
   - On macOS, run `scripts/diagnose-macos-app-proxy.sh`.
   - Set user proxy environment variables when needed.
   - On Windows, set WinHTTP only when needed and preferably from Administrator PowerShell.
   - On macOS, use shell profile exports for terminals and `launchctl setenv` for newly launched GUI apps when needed.
   - Fully restart the affected app or terminal.
3. If an internal/VPN resource fails when a local proxy or TUN mode is enabled:
   - If the destination type is unclear, run diagnostics first and do not modify route scripts.
   - Run `scripts/update_route_whitelist.py`.
   - Prefer `--dry-run` first to preview the exact files, entries, and bypass changes.
   - Add only the internal domain, `domain=ip`, IP, or CIDR to the DIRECT/bypass list.
   - Public IP/CIDR and `domain=public-ip` entries are rejected unless the user explicitly approves `--allow-public-direct`.
   - Reload the proxy profile or restart the local proxy app if system proxy bypass changed.
4. If both external services and internal resources are needed:
   - Configure applications to use the approved proxy for external services.
   - Add only internal/VPN destinations to the route bypass list.

## Windows App Proxy Diagnostics

Run a generic check:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-windows-app-proxy.ps1 -ProxyPort 7897 -AppName Git -TestUrl https://example.com/
```

Set user-level proxy environment variables:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-windows-app-proxy.ps1 -ProxyPort 7897 -SetUserEnv
```

Set WinHTTP proxy from Administrator PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-windows-app-proxy.ps1 -ProxyPort 7897 -SetWinHttp
```

Equivalent manual user environment variables:

```powershell
[Environment]::SetEnvironmentVariable('HTTP_PROXY','http://127.0.0.1:7897','User')
[Environment]::SetEnvironmentVariable('HTTPS_PROXY','http://127.0.0.1:7897','User')
[Environment]::SetEnvironmentVariable('ALL_PROXY','http://127.0.0.1:7897','User')
[Environment]::SetEnvironmentVariable('NO_PROXY','localhost,127.0.0.1,::1','User')
```

Fully quit and restart the affected app after changes. Environment variables do not update already-running processes.

## macOS App Proxy Diagnostics

Run a generic check:

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --app-name git --test-url https://example.com/
```

Print suggested shell exports without writing files:

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --print-env
```

Append proxy exports to the current user's shell profile:

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --set-shell-env
```

Set `launchctl` user environment variables for newly launched GUI apps:

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --set-launchctl-env
```

Equivalent manual shell exports:

```bash
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
export ALL_PROXY=http://127.0.0.1:7897
export NO_PROXY=localhost,127.0.0.1,::1
```

For GUI apps on macOS, environment changes normally affect only apps launched after the change. Quit and reopen the affected app.

## Private Route Bypass

Use this workflow for internal domains, VPN-only services, host-to-IP mappings, private IPs, and CIDR ranges.

Examples:

Preview changes without writing files:

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24 --dry-run
```

Apply changes:

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
```

On macOS or Unix shells:

```bash
python3 ./scripts/update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
```

Use VPN-friendly route exclusions when local proxy routing conflicts with private/VPN routes:

```powershell
python .\scripts\update_route_whitelist.py --entry 10.0.0.0/24 --vpn-friendly
```

Use an internal DNS server when internal domains must resolve through company DNS:

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test --internal-dns-server 10.0.0.53
```

Supported entry forms:

- Domain: `internal.example.test`
- Domain with host IP: `internal.example.test=10.0.0.10`
- IP/CIDR route: `10.0.0.0/24`

Public DIRECT/bypass entries are blocked by default. Use `--allow-public-direct` only after the user confirms that a public destination must bypass the proxy.

After updating route scripts, reload/reapply the local proxy profile. If Windows system proxy bypass changed, toggle system proxy or restart the local proxy app.

## Guardrails

- Do not delete app data, credentials, or authentication files as an early fix.
- Do not add external public destinations to DIRECT/bypass rules unless the user explicitly requests direct access and accepts the network implications.
- Do not use `--allow-public-direct` without explicit user approval.
- When unsure whether a destination is internal or public, use `--dry-run` and diagnostics first.
- Do not route internal VPN/private services through an external proxy unless explicitly required by policy.
- Do not assume a browser working means CLI tools inherit the same proxy settings.
- Do not run unrelated project commands for this skill.

## Success Criteria

For application proxy issues:

- The affected app works after restart.
- Proxied `curl` returns HTTP headers instead of timing out.
- User environment variables, WinHTTP on Windows, or `launchctl getenv` on macOS show the intended proxy.

For private route bypass issues:

- Dry-run output shows the intended files, managed entries, and proxy bypass preview before any write.
- Generated rules include the requested domain, domain suffix, IP, or CIDR DIRECT/bypass entries.
- Internal domains/IPs open while external development services still use the configured proxy policy.
