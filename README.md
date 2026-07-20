# Windows 代理路由管理器

一个用于诊断 Windows 应用代理设置和管理私有网络路由绕过规则的技能。

## 范围

- 检查本地 HTTP 代理端口。  
- 使用 `curl` 比较直连和代理的连接情况。  
- 设置用户级别的 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 和 `NO_PROXY`。  
- 检查或设置 WinHTTP 代理设置。  
- 为授权网络添加内部/私有域名、主机映射、IP 或 CIDR 的绕过规则。

此项目不提供代理服务器、凭证、流量隧道、远程端点或访问规避服务。仅在拥有授权的网络和系统上使用。



# Windows Proxy Route Manager

skill for diagnosing Windows application proxy settings and managing private-network route bypass rules.

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
