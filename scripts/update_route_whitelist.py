#!/usr/bin/env python3
import argparse
import ctypes
import ipaddress
import json
import os
import re
import socket
import sys
from pathlib import Path


def default_app_dir():
    appdata = os.environ.get("APPDATA")
    if appdata:
        windows_app_dir = Path(appdata) / "io.github.clash-verge-rev.clash-verge-rev"
        if windows_app_dir.exists():
            return windows_app_dir
    return Path.home() / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"


APP_DIR = default_app_dir()
PROFILES_DIR = APP_DIR / "profiles"
DEFAULT_SCRIPT = PROFILES_DIR / "Script.js"
PROFILES_CONFIG = APP_DIR / "profiles.yaml"
VERGE_CONFIG = APP_DIR / "verge.yaml"
DEFAULT_OPTIONS = {
    "vpnFriendly": False,
    "systemDnsForDomains": True,
    "writeCurrentProfileScript": True,
    "autoResolvePrivateDomains": True,
    "internalDnsServers": [],
}
PRIVATE_HOST_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]
FAKE_IP_NETWORKS = [
    ipaddress.ip_network("198.18.0.0/15"),
]
VPN_FRIENDLY_ROUTE_EXCLUDES = [
    "10.0.0.0/8",
    "100.64.0.0/10",
    "169.254.0.0/16",
    "192.168.0.0/16",
    "fc00::/7",
    "fe80::/10",
]
STALE_GENERATED_ROUTE_EXCLUDES = [
    "172.16.0.0/12",
]
DEFAULT_WINDOWS_PROXY_BYPASS = [
    "localhost",
    "127.*",
    "192.168.*",
    "10.*",
    "172.16.*",
    "172.17.*",
    "172.18.*",
    "172.19.*",
    "172.20.*",
    "172.21.*",
    "172.22.*",
    "172.23.*",
    "172.24.*",
    "172.25.*",
    "172.26.*",
    "172.27.*",
    "172.28.*",
    "172.29.*",
    "172.30.*",
    "172.31.*",
    "<local>",
]


def read_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def current_profile_script_path():
    text = read_text(PROFILES_CONFIG)
    current_match = re.search(r"^current:\s*([^\s#]+)\s*$", text, re.MULTILINE)
    if not current_match:
        return None
    current_uid = current_match.group(1)
    current_block_match = re.search(
        rf"(?ms)^-\s+uid:\s+{re.escape(current_uid)}\s*$([\s\S]*?)(?=^-\s+uid:|\Z)",
        text,
    )
    if not current_block_match:
        return None
    script_match = re.search(r"^\s+script:\s*([^\s#]+)\s*$", current_block_match.group(1), re.MULTILINE)
    if not script_match:
        return None
    return PROFILES_DIR / f"{script_match.group(1)}.js"


def parse_entry(raw):
    raw = raw.strip()
    if not raw:
        raise ValueError("empty entry")
    host_ip = None
    value = raw
    if "=" in raw:
        value, host_ip = [part.strip() for part in raw.split("=", 1)]
        ipaddress.ip_address(host_ip)
    try:
        network = ipaddress.ip_network(value, strict=False)
        return {"type": "cidr", "value": str(network)}
    except ValueError:
        pass
    if not re.fullmatch(r"[A-Za-z0-9*+_.-]+", value) or "." not in value:
        raise ValueError(f"invalid domain/IP/CIDR entry: {raw}")
    item = {"type": "domain", "value": value.lower()}
    if host_ip:
        item["ip"] = host_ip
    return item


def is_private_host_ip(value):
    ip = ipaddress.ip_address(value)
    if any(ip in network for network in FAKE_IP_NETWORKS):
        return False
    return any(ip in network for network in PRIVATE_HOST_NETWORKS)


def is_private_network(value):
    network = ipaddress.ip_network(value, strict=False)
    if any(network.subnet_of(fake) or fake.subnet_of(network) for fake in FAKE_IP_NETWORKS):
        return False
    return any(
        network.version == private.version and network.subnet_of(private)
        for private in PRIVATE_HOST_NETWORKS
    )


def validate_public_direct_entries(entries, allow_public_direct):
    if allow_public_direct:
        return
    public_items = []
    for item in entries:
        if item.get("type") == "cidr" and not is_private_network(item["value"]):
            public_items.append(item["value"])
        elif item.get("type") == "domain" and item.get("ip") and not is_private_host_ip(item["ip"]):
            public_items.append(f"{item['value']}={item['ip']}")
    if public_items:
        joined = ", ".join(public_items)
        raise ValueError(
            "refuse to add public DIRECT/bypass entries without --allow-public-direct: "
            + joined
        )


def resolve_private_host(domain):
    try:
        infos = socket.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return None
    candidates = []
    seen = set()
    for family, _, _, _, sockaddr in infos:
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        ip = sockaddr[0]
        if ip not in seen and is_private_host_ip(ip):
            candidates.append(ip)
            seen.add(ip)
    if not candidates:
        return None
    candidates.sort(key=lambda ip: (":" in ip, ip))
    return candidates[0]


def apply_auto_resolved_private_hosts(entries, options):
    if not options.get("autoResolvePrivateDomains"):
        return entries
    resolved = []
    for item in entries:
        next_item = dict(item)
        if item.get("type") == "domain" and not item.get("ip"):
            host_ip = resolve_private_host(item["value"])
            if host_ip:
                next_item["ip"] = host_ip
        resolved.append(next_item)
    return resolved


def extract_existing_entries(text):
    match = re.search(
        r"const\s+WHITELIST_ENTRIES\s*=\s*(\[[\s\S]*?\]);", text
    )
    if not match:
        return []
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []


def extract_existing_options(text):
    match = re.search(
        r"const\s+WHITELIST_OPTIONS\s*=\s*(\{[\s\S]*?\});", text
    )
    if not match:
        return dict(DEFAULT_OPTIONS)
    try:
        options = json.loads(match.group(1))
    except json.JSONDecodeError:
        return dict(DEFAULT_OPTIONS)
    merged = dict(DEFAULT_OPTIONS)
    for key, value in options.items():
        if key not in DEFAULT_OPTIONS:
            continue
        if key == "internalDnsServers":
            if isinstance(value, list):
                merged[key] = [str(item) for item in value if str(item).strip()]
        else:
            merged[key] = bool(value)
    return merged


def parse_dns_server(value):
    value = value.strip()
    if not value:
        raise ValueError("empty DNS server")
    if "://" in value:
        return value
    host = value
    if value.startswith("[") and "]" in value:
        host = value[1:value.index("]")]
    elif value.count(":") == 1:
        host = value.split(":", 1)[0]
    try:
        ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(f"invalid DNS server: {value}") from exc
    return value


def merge_entries(existing, new_entries):
    merged = {}
    for item in existing + new_entries:
        key = (item.get("type"), item.get("value"))
        if key not in merged:
            merged[key] = dict(item)
        elif item.get("ip"):
            merged[key]["ip"] = item["ip"]
    return sorted(merged.values(), key=lambda x: (x.get("type", ""), x.get("value", "")))


def windows_bypass_items_for_entries(entries):
    items = []
    for item in entries:
        if item.get("type") == "domain":
            if item.get("ip"):
                domain = domain_suffix_for_python(item["value"])
                if domain and domain not in items:
                    items.append(domain)
                ip_items = windows_bypass_items_for_ip(item["ip"])
                for value in ip_items:
                    if value not in items:
                        items.append(value)
        elif item.get("type") == "cidr":
            for value in windows_bypass_items_for_cidr(item["value"]):
                if value not in items:
                    items.append(value)
    return items


def stale_windows_bypass_items_for_entries(entries):
    items = []
    for item in entries:
        if item.get("type") == "domain" and not item.get("ip"):
            domain = domain_suffix_for_python(item["value"])
            if domain and domain not in items:
                items.append(domain)
    return items


def domain_suffix_for_python(domain):
    return domain.replace("+.", "", 1).replace("*.", "", 1)


def windows_bypass_items_for_ip(value):
    ip = ipaddress.ip_address(value)
    if ip.version != 4:
        return [str(ip)]
    parts = str(ip).split(".")
    if parts[0] == "172" and parts[1] == "88":
        return ["172.88.*", str(ip)]
    return [str(ip)]


def windows_bypass_items_for_cidr(value):
    network = ipaddress.ip_network(value, strict=False)
    if network.version != 4:
        return [str(network.network_address)]
    if network.prefixlen == 32:
        return windows_bypass_items_for_ip(str(network.network_address))
    if network.prefixlen <= 16:
        first, second, *_ = str(network.network_address).split(".")
        return [f"{first}.{second}.*"]
    return [str(network.network_address)]


def parse_bypass_list(value):
    if not value or value.strip().lower() == "null":
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def merge_bypass_items(existing, additions, removals=None):
    removal_set = set(removals or [])
    merged = []
    for item in existing + additions:
        if item in removal_set:
            continue
        if item and item not in merged:
            merged.append(item)
    return merged


def update_verge_system_proxy_bypass(additions, removals=None):
    if not additions:
        return None
    existing_text = read_text(VERGE_CONFIG)
    if not existing_text:
        return None
    match = re.search(r"^system_proxy_bypass:\s*(.*)$", existing_text, re.MULTILINE)
    if match:
        current = match.group(1).strip()
        existing = parse_bypass_list("" if current == "null" else current)
        replacement = "system_proxy_bypass: " + ";".join(
            merge_bypass_items(existing or DEFAULT_WINDOWS_PROXY_BYPASS, additions, removals)
        )
        updated_text = existing_text[: match.start()] + replacement + existing_text[match.end():]
    else:
        replacement = "system_proxy_bypass: " + ";".join(
            merge_bypass_items(DEFAULT_WINDOWS_PROXY_BYPASS, additions, removals)
        )
        updated_text = existing_text.rstrip() + "\n" + replacement + "\n"
    if updated_text != existing_text:
        VERGE_CONFIG.write_text(updated_text, encoding="utf-8")
    return str(VERGE_CONFIG)


def preview_verge_system_proxy_bypass(additions, removals=None):
    if not additions:
        return None
    existing_text = read_text(VERGE_CONFIG)
    if not existing_text:
        return None
    match = re.search(r"^system_proxy_bypass:\s*(.*)$", existing_text, re.MULTILINE)
    if match:
        current = match.group(1).strip()
        existing = parse_bypass_list("" if current == "null" else current)
        merged = merge_bypass_items(existing or DEFAULT_WINDOWS_PROXY_BYPASS, additions, removals)
    else:
        merged = merge_bypass_items(DEFAULT_WINDOWS_PROXY_BYPASS, additions, removals)
    return {
        "file": str(VERGE_CONFIG),
        "systemProxyBypass": merged,
    }


def read_windows_proxy_override():
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "ProxyOverride")
            return str(value)
    except OSError:
        return None


def write_windows_proxy_override(value):
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, value)
        internet_option_settings_changed = 39
        internet_option_refresh = 37
        ctypes.windll.wininet.InternetSetOptionW(0, internet_option_settings_changed, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, internet_option_refresh, 0, 0)
        return True
    except OSError:
        return False


def update_windows_proxy_override(additions, removals=None):
    if sys.platform != "win32" or not additions:
        return None
    current = read_windows_proxy_override()
    if current is None:
        return None
    merged = merge_bypass_items(parse_bypass_list(current), additions, removals)
    new_value = ";".join(merged)
    if new_value == current:
        return "unchanged"
    return "updated" if write_windows_proxy_override(new_value) else None


def preview_windows_proxy_override(additions, removals=None):
    if sys.platform != "win32" or not additions:
        return None
    current = read_windows_proxy_override()
    if current is None:
        return None
    return {
        "current": parse_bypass_list(current),
        "next": merge_bypass_items(parse_bypass_list(current), additions, removals),
    }


def render_script(entries, options):
    entries_json = json.dumps(entries, ensure_ascii=False, indent=2)
    options_json = json.dumps(options, ensure_ascii=False, indent=2)
    vpn_excludes_json = json.dumps(VPN_FRIENDLY_ROUTE_EXCLUDES, ensure_ascii=False, indent=2)
    stale_excludes_json = json.dumps(STALE_GENERATED_ROUTE_EXCLUDES, ensure_ascii=False, indent=2)
    return f"""// Managed by windows-proxy-route-manager
const WHITELIST_ENTRIES = {entries_json};
const WHITELIST_OPTIONS = {options_json};
const VPN_FRIENDLY_ROUTE_EXCLUDES = {vpn_excludes_json};
const STALE_GENERATED_ROUTE_EXCLUDES = {stale_excludes_json};

function addUnique(list, value) {{
  if (!list.includes(value)) list.push(value);
}}

function removeValue(list, value) {{
  let index = list.indexOf(value);
  while (index !== -1) {{
    list.splice(index, 1);
    index = list.indexOf(value);
  }}
}}

function addUniqueRule(list, value) {{
  if (!list.includes(value)) list.push(value);
}}

function domainSuffixFor(domain) {{
  return domain.replace(/^\\+\\./, \"\").replace(/^\\*\\./, \"\");
}}

function dnsPolicyKey(domain) {{
  return `+.${{domainSuffixFor(domain)}}`;
}}

function ipToRouteExclude(ip) {{
  return ip.includes(\":\") ? `${{ip}}/128` : `${{ip}}/32`;
}}

function isIpLiteral(host) {{
  return /^\\d{{1,3}}(?:\\.\\d{{1,3}}){{3}}$/.test(host) || host.includes(\":\");
}}

function dnsServerHost(server) {{
  if (!server || server.includes(\"://\")) return null;
  if (server.startsWith(\"[\") && server.includes(\"]\")) {{
    return server.slice(1, server.indexOf(\"]\"));
  }}
  const colonCount = (server.match(/:/g) || []).length;
  if (colonCount === 1 && server.includes(\".\")) {{
    return server.split(\":\")[0];
  }}
  return server;
}}

function internalDnsRouteExcludes() {{
  const routes = [];
  const servers = WHITELIST_OPTIONS.internalDnsServers || [];
  for (const server of servers) {{
    const host = dnsServerHost(server);
    if (!host || !isIpLiteral(host)) continue;
    addUnique(routes, ipToRouteExclude(host));
  }}
  return routes;
}}

function ensureTunRouteExclude(config, value) {{
  config.tun = config.tun || {{}};
  config.tun[\"route-exclude-address\"] = config.tun[\"route-exclude-address\"] || [];
  addUnique(config.tun[\"route-exclude-address\"], value);
}}

function removeTunRouteExclude(config, value) {{
  if (!config.tun || !config.tun[\"route-exclude-address\"]) return;
  removeValue(config.tun[\"route-exclude-address\"], value);
}}

function dnsPolicyValue() {{
  const servers = WHITELIST_OPTIONS.internalDnsServers || [];
  return servers.length ? servers : "system";
}}

function ensureDomainDnsPolicy(config, domain) {{
  config.dns[\"nameserver-policy\"] = config.dns[\"nameserver-policy\"] || {{}};
  const policyValue = dnsPolicyValue();
  if (policyValue === "system") {{
    config.dns[\"direct-nameserver\"] = config.dns[\"direct-nameserver\"] || [];
    addUnique(config.dns[\"direct-nameserver\"], \"system\");
    config.dns[\"direct-nameserver-follow-policy\"] = true;
  }}
  config.dns[\"nameserver-policy\"][domain] = policyValue;
  config.dns[\"nameserver-policy\"][dnsPolicyKey(domain)] = policyValue;
}}

function main(config, profileName) {{
  config.hosts = config.hosts || {{}};
  config.dns = config.dns || {{}};
  config.dns[\"use-hosts\"] = true;
  config.dns[\"fake-ip-filter\"] = config.dns[\"fake-ip-filter\"] || [];
  config.rules = config.rules || [];

  const managedRules = [];
  for (const route of internalDnsRouteExcludes()) {{
    ensureTunRouteExclude(config, route);
    const ruleType = route.includes(\":\") ? \"IP-CIDR6\" : \"IP-CIDR\";
    addUniqueRule(managedRules, `${{ruleType}},${{route}},DIRECT,no-resolve`);
  }}

  for (const entry of WHITELIST_ENTRIES) {{
    if (entry.type === \"domain\") {{
      const domain = entry.value;
      if (WHITELIST_OPTIONS.systemDnsForDomains) {{
        ensureDomainDnsPolicy(config, domain);
      }}
      if (entry.ip) {{
        config.hosts[domainSuffixFor(domain)] = entry.ip;
        addUnique(config.dns[\"fake-ip-filter\"], domain);
        addUnique(config.dns[\"fake-ip-filter\"], dnsPolicyKey(domain));
        const hostRoute = ipToRouteExclude(entry.ip);
        ensureTunRouteExclude(config, hostRoute);
        const hostRuleType = entry.ip.includes(\":\") ? \"IP-CIDR6\" : \"IP-CIDR\";
        addUniqueRule(managedRules, `${{hostRuleType}},${{hostRoute}},DIRECT,no-resolve`);
      }} else {{
        removeValue(config.dns[\"fake-ip-filter\"], domain);
        removeValue(config.dns[\"fake-ip-filter\"], dnsPolicyKey(domain));
      }}
      if (!domain.startsWith(\"+.\") && !domain.startsWith(\"*.\")) {{
        addUniqueRule(managedRules, `DOMAIN,${{domain}},DIRECT`);
        addUniqueRule(managedRules, `DOMAIN-SUFFIX,${{domainSuffixFor(domain)}},DIRECT`);
      }} else {{
        addUniqueRule(managedRules, `DOMAIN-SUFFIX,${{domainSuffixFor(domain)}},DIRECT`);
      }}
    }} else if (entry.type === \"cidr\") {{
      ensureTunRouteExclude(config, entry.value);
      const ruleType = entry.value.includes(\":\") ? \"IP-CIDR6\" : \"IP-CIDR\";
      addUniqueRule(managedRules, `${{ruleType}},${{entry.value}},DIRECT,no-resolve`);
    }}
  }}

  if (WHITELIST_OPTIONS.vpnFriendly) {{
    for (const route of VPN_FRIENDLY_ROUTE_EXCLUDES) {{
      ensureTunRouteExclude(config, route);
      const ruleType = route.includes(\":\") ? \"IP-CIDR6\" : \"IP-CIDR\";
      addUniqueRule(managedRules, `${{ruleType}},${{route}},DIRECT,no-resolve`);
    }}
  }}

  const managedSet = new Set(managedRules);
  const staleRules = [];
  for (const route of STALE_GENERATED_ROUTE_EXCLUDES) {{
    if (managedSet.has(`IP-CIDR,${{route}},DIRECT,no-resolve`) || managedSet.has(`IP-CIDR6,${{route}},DIRECT,no-resolve`)) {{
      continue;
    }}
    removeTunRouteExclude(config, route);
    const ruleType = route.includes(\":\") ? \"IP-CIDR6\" : \"IP-CIDR\";
    staleRules.push(`${{ruleType}},${{route}},DIRECT,no-resolve`);
  }}
  const staleSet = new Set(staleRules);
  config.rules = [
    ...managedRules,
    ...config.rules.filter((rule) => !managedSet.has(rule) && !staleSet.has(rule)),
  ];
  return config;
}}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry", action="append", required=True, help="domain, domain=ip, IP, or CIDR")
    parser.add_argument(
        "--script",
        help="explicit profile extension script path; defaults to the global profiles/Script.js",
    )
    parser.add_argument(
        "--global-only",
        action="store_true",
        help="write only profiles/Script.js instead of also updating the current profile-bound script",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview files, entries, and proxy bypass changes without writing anything",
    )
    parser.add_argument(
        "--allow-public-direct",
        action="store_true",
        help="allow public IP/CIDR or domain=public-ip DIRECT/bypass entries after explicit user approval",
    )
    parser.add_argument(
        "--no-windows-system-proxy-bypass",
        action="store_true",
        help="do not update Windows system proxy bypass entries for whitelisted internal domains/IPs",
    )
    parser.add_argument(
        "--internal-dns-server",
        action="append",
        default=None,
        help="DNS server to use for whitelisted domains instead of system; repeatable, e.g. 10.0.0.53",
    )
    dns_group = parser.add_mutually_exclusive_group()
    dns_group.add_argument(
        "--system-dns-for-domains",
        action="store_true",
        default=None,
        help="force whitelisted domains to resolve through the system DNS policy",
    )
    dns_group.add_argument(
        "--no-system-dns-for-domains",
        action="store_false",
        dest="system_dns_for_domains",
        help="do not add nameserver-policy/direct-nameserver entries for domain-only whitelist items",
    )
    resolve_group = parser.add_mutually_exclusive_group()
    resolve_group.add_argument(
        "--auto-resolve-private-domains",
        action="store_true",
        default=None,
        help="resolve domain-only entries through the system resolver and add hosts mappings for private IPs",
    )
    resolve_group.add_argument(
        "--no-auto-resolve-private-domains",
        action="store_false",
        dest="auto_resolve_private_domains",
        help="do not automatically convert domain-only entries to domain=private-ip",
    )
    vpn_group = parser.add_mutually_exclusive_group()
    vpn_group.add_argument(
        "--vpn-friendly",
        action="store_true",
        default=None,
        help="exclude common LAN/VPN ranges from local TUN auto-route while preserving proxy rules",
    )
    vpn_group.add_argument(
        "--no-vpn-friendly",
        action="store_false",
        dest="vpn_friendly",
        help="disable the common LAN/VPN route excludes in generated script",
    )
    args = parser.parse_args()

    script_path = Path(args.script).expanduser() if args.script else DEFAULT_SCRIPT
    script_path.parent.mkdir(parents=True, exist_ok=True)
    existing_text = read_text(script_path)
    existing = extract_existing_entries(existing_text)
    options = extract_existing_options(existing_text)
    if args.vpn_friendly is not None:
        options["vpnFriendly"] = args.vpn_friendly
    if args.system_dns_for_domains is not None:
        options["systemDnsForDomains"] = args.system_dns_for_domains
    if args.auto_resolve_private_domains is not None:
        options["autoResolvePrivateDomains"] = args.auto_resolve_private_domains
    if args.internal_dns_server is not None:
        options["internalDnsServers"] = [parse_dns_server(value) for value in args.internal_dns_server]
    new_entries = [parse_entry(raw) for raw in args.entry]
    validate_public_direct_entries(new_entries, args.allow_public_direct)
    entries = merge_entries(existing, new_entries)
    entries = apply_auto_resolved_private_hosts(entries, options)
    validate_public_direct_entries(entries, args.allow_public_direct)
    rendered = render_script(entries, options)
    targets = [script_path]
    current_script = current_profile_script_path()
    if (
        current_script
        and not args.global_only
        and not args.script
        and options["writeCurrentProfileScript"]
    ):
        targets.append(current_script)
    updated = []
    for target in dict.fromkeys(targets):
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
        updated.append(str(target))
    proxy_bypass = []
    verge_proxy_bypass = None
    windows_proxy_bypass = None
    proxy_bypass_preview = None
    if not args.no_windows_system_proxy_bypass:
        proxy_bypass = windows_bypass_items_for_entries(entries)
        stale_proxy_bypass = stale_windows_bypass_items_for_entries(entries)
        if args.dry_run:
            proxy_bypass_preview = {
                "vergeConfig": preview_verge_system_proxy_bypass(proxy_bypass, stale_proxy_bypass),
                "currentSystemProxy": preview_windows_proxy_override(proxy_bypass, stale_proxy_bypass),
            }
        else:
            verge_proxy_bypass = update_verge_system_proxy_bypass(proxy_bypass, stale_proxy_bypass)
            windows_proxy_bypass = update_windows_proxy_override(proxy_bypass, stale_proxy_bypass)
    print("dry-run" if args.dry_run else "updated")
    print("files to update" if args.dry_run else "updated files")
    print(json.dumps(updated, ensure_ascii=False, indent=2))
    print("managed entries")
    print(json.dumps(entries, ensure_ascii=False, indent=2))
    print("summary")
    print(json.dumps({
        "options": options,
        "windowsSystemProxyBypass": {
            "entries": proxy_bypass,
            "vergeConfig": verge_proxy_bypass,
            "currentSystemProxy": windows_proxy_bypass,
            "preview": proxy_bypass_preview,
        },
        "nextSteps": [
            "reload or reapply the local proxy profile",
            "restart the affected app if Windows system proxy bypass or environment changed",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
