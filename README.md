# Windows Proxy Route Manager

A Codex skill for diagnosing Windows application proxy settings and managing private-network route bypass rules.

## Scope

- Check local HTTP proxy ports.
- Compare direct and proxied connectivity with `curl`.
- Set user-level `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY`.
- Inspect or set WinHTTP proxy settings.
- Add internal/private domain, host mapping, IP, or CIDR bypass rules for authorized networks.

This project does not provide proxy servers, credentials, traffic tunnels, remote endpoints, or access-circumvention services. Use it only on networks and systems where you have authorization.

## Example

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-windows-app-proxy.ps1 -ProxyPort 7897 -AppName Git -TestUrl https://example.com/
```

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
```
