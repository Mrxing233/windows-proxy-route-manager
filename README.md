# Windows/macOS 代理路由管理器

一个用于诊断 Windows/macOS 应用代理设置和管理私有网络路由绕过规则的技能。

## 范围

- 检查本地或企业 HTTP 代理端口。
- 使用 `curl` 比较直连和代理的连接情况。
- Windows：设置用户级别的 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 和 `NO_PROXY`。
- Windows：检查或设置 WinHTTP 代理设置。
- macOS：检查 shell 环境变量、`launchctl` 环境变量和系统代理设置。
- macOS：可写入 shell profile 或设置 `launchctl setenv`，用于新启动的终端/GUI 应用。
- 为授权网络添加内部/私有域名、主机映射、IP 或 CIDR 的绕过规则。

此项目不提供代理服务器、凭证、流量隧道、远程端点或访问规避服务。仅在拥有授权的网络和系统上使用。

## Windows 示例

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-windows-app-proxy.ps1 -ProxyPort 7897 -AppName Git -TestUrl https://example.com/
```

## macOS 示例

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --app-name git --test-url https://example.com/
```

只打印建议的环境变量：

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --print-env
```

写入当前 shell profile：

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --set-shell-env
```

为新启动的 GUI 应用设置环境变量：

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --set-launchctl-env
```

## 路由绕过示例

预览将要修改的内容，不写入文件：

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24 --dry-run
```

正式写入：

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
```

```bash
python3 ./scripts/update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
```

公网 IP/CIDR 或 `domain=公网IP` 默认不会加入 DIRECT/绕过规则。只有在明确确认公网目标也必须绕过代理时，才使用 `--allow-public-direct`。

# Windows/macOS Proxy Route Manager

A skill for diagnosing Windows/macOS application proxy settings and managing private-network route bypass rules.

## Scope

- Check local or enterprise HTTP proxy ports.
- Compare direct and proxied connectivity with `curl`.
- Windows: set user-level `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY`.
- Windows: inspect or set WinHTTP proxy settings.
- macOS: inspect shell environment variables, `launchctl` environment variables, and system proxy settings.
- macOS: optionally write shell profile exports or set `launchctl setenv` for newly launched terminal/GUI apps.
- Add internal/private domain, host mapping, IP, or CIDR bypass rules for authorized networks.

This project does not provide proxy servers, credentials, traffic tunnels, remote endpoints, or access-circumvention services. Use it only on networks and systems where you have authorization.

## Windows Example

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-windows-app-proxy.ps1 -ProxyPort 7897 -AppName Git -TestUrl https://example.com/
```

## macOS Example

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --app-name git --test-url https://example.com/
```

Print suggested exports:

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --print-env
```

Append exports to the current shell profile:

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --set-shell-env
```

Set environment variables for newly launched GUI apps:

```bash
bash ./scripts/diagnose-macos-app-proxy.sh --proxy-port 7897 --set-launchctl-env
```

## Route Bypass Example

Preview changes without writing files:

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24 --dry-run
```

Apply changes:

```powershell
python .\scripts\update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
```

```bash
python3 ./scripts/update_route_whitelist.py --entry internal.example.test=10.0.0.10 --entry 10.0.0.0/24
```

Public IP/CIDR entries and `domain=public-ip` entries are rejected by default. Use `--allow-public-direct` only after confirming the public destination must bypass the proxy.
