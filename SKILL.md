---
name: windows-proxy-route-manager
description: Diagnose and fix Windows application proxy configuration and local network route bypass issues. Use when development tools or desktop apps cannot reach required services through an approved local or enterprise HTTP proxy, or when VPN/private/internal domains and IP ranges must bypass a local proxy so corporate network resources remain reachable.
---

# Windows Proxy Route Manager

## Overview

Use this skill for Windows proxy diagnostics and private-network route management in development or enterprise environments. It helps decide whether an app should use a configured local/enterprise proxy or whether a private/VPN destination should bypass that proxy.

This skill does not provide proxy servers, credentials, traffic tunnels, remote endpoints, or access-circumvention services. Use it only on networks and systems where you have authorization.

## Decision Tree

1. Identify the failing destination.
   - External development service: package registries, source repositories, API endpoints, artifact repositories.
   - Internal resource: company domains, VPN-only services, private IPs, CIDR ranges, or host mappings such as `internal.example.test=10.0.0.10`.
2. If an external service times out while the organization-approved proxy is running:
   - Run `scripts/diagnose-windows-app-proxy.ps1`.
   - Set user proxy environment variables when needed.
   - Set WinHTTP only when needed and preferably from Administrator PowerShell.
   - Fully restart the affected app or terminal.
3. If an internal/VPN resource fails when a local proxy or TUN mode is enabled:
   - Run `scripts/update_route_whitelist.py`.
   - Add only the internal domain, `domain=ip`, IP, or CIDR to the DIRECT/bypass list.
   - Reload the proxy profile or restart the local proxy app if system proxy bypass changed.
4. If both external services and internal resources are needed:
   - Configure applications to use the approved proxy for external services.
   - Add only internal/VPN destinations to the route bypass list.

## App Proxy Diagnostics

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

## Private Route Bypass

Use this workflow for internal domains, VPN-only services, host-to-IP mappings, private IPs, and CIDR ranges.

Examples:

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
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

After updating route scripts, reload/reapply the local proxy profile. If Windows system proxy bypass changed, toggle system proxy or restart the local proxy app.

## Guardrails

- Do not delete app data, credentials, or authentication files as an early fix.
- Do not add external public destinations to DIRECT/bypass rules unless the user explicitly requests direct access and accepts the network implications.
- Do not route internal VPN/private services through an external proxy unless explicitly required by policy.
- Do not assume a browser working means CLI tools inherit the same proxy settings.
- Do not run unrelated project commands for this skill.

## Success Criteria

For application proxy issues:

- The affected app works after restart.
- Proxied `curl` returns HTTP headers instead of timing out.
- User environment variables and/or WinHTTP show the intended proxy.

For private route bypass issues:

- Generated rules include the requested domain, domain suffix, IP, or CIDR DIRECT/bypass entries.
- Internal domains/IPs open while external development services still use the configured proxy policy.
