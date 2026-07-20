param(
    [string]$AppName = "Windows app",
    [int]$ProxyPort = 7897,
    [string]$TestUrl = "https://example.com/",
    [switch]$SetUserEnv,
    [switch]$SetWinHttp
)

$ErrorActionPreference = "Continue"
$proxyUrl = "http://127.0.0.1:$ProxyPort"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "==== $Title ===="
}

function Show-Command {
    param([string]$Text)
    Write-Host ""
    Write-Host "> $Text"
}

Write-Section "Windows App Proxy Diagnose"
Write-Host "App: $AppName"
Write-Host "Proxy: $proxyUrl"
Write-Host "Test URL: $TestUrl"

Write-Section "Matching Processes"
$processPattern = if ($AppName -eq "Windows app") { "git|node|python|java|npm|pnpm|mvn|gradle|curl|powershell|pwsh" } else { [regex]::Escape($AppName) }
Get-Process |
    Where-Object { $_.ProcessName -match $processPattern -or ($_.Path -and $_.Path -match $processPattern) } |
    Select-Object Id, ProcessName, StartTime, Path |
    Sort-Object ProcessName, Id |
    Format-Table -AutoSize

Write-Section "User Proxy Environment"
Get-ItemProperty "HKCU:\Environment" -ErrorAction SilentlyContinue |
    Select-Object HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, NO_PROXY |
    Format-List

if ($SetUserEnv) {
    Write-Section "Set User Proxy Environment"
    [Environment]::SetEnvironmentVariable("HTTP_PROXY", $proxyUrl, "User")
    [Environment]::SetEnvironmentVariable("HTTPS_PROXY", $proxyUrl, "User")
    [Environment]::SetEnvironmentVariable("ALL_PROXY", $proxyUrl, "User")
    [Environment]::SetEnvironmentVariable("NO_PROXY", "localhost,127.0.0.1,::1", "User")
    Get-ItemProperty "HKCU:\Environment" |
        Select-Object HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, NO_PROXY |
        Format-List
    Write-Host "User environment variables are set. Fully restart the app for this to take effect."
}

Write-Section "Windows Internet Settings Proxy"
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" |
    Select-Object ProxyEnable, ProxyServer, AutoConfigURL |
    Format-List

Write-Section "WinHTTP Proxy"
Show-Command "netsh winhttp show proxy"
netsh winhttp show proxy

if ($SetWinHttp) {
    Write-Section "Set WinHTTP Proxy"
    Show-Command "netsh winhttp set proxy 127.0.0.1:$ProxyPort"
    netsh winhttp set proxy "127.0.0.1:$ProxyPort"
    netsh winhttp show proxy
}

Write-Section "Local Proxy Port"
Test-NetConnection 127.0.0.1 -Port $ProxyPort | Format-List
$connections = Get-NetTCPConnection -LocalPort $ProxyPort -ErrorAction SilentlyContinue
if ($connections) {
    $owners = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    Get-Process -Id $owners -ErrorAction SilentlyContinue |
        Select-Object Id, ProcessName, Path |
        Format-Table -AutoSize
}

Write-Section "Direct URL Test"
Show-Command "curl.exe -I --connect-timeout 15 --max-time 30 $TestUrl"
curl.exe -I --connect-timeout 15 --max-time 30 $TestUrl

Write-Section "Proxy URL Test"
Show-Command "curl.exe -I --proxy $proxyUrl --connect-timeout 15 --max-time 30 $TestUrl"
curl.exe -I --proxy $proxyUrl --connect-timeout 15 --max-time 30 $TestUrl

Write-Section "Interpretation"
Write-Host "- If direct test fails but proxy test returns HTTP headers, configure the app to use the proxy."
Write-Host "- User env changes affect only newly started processes."
Write-Host "- WinHTTP changes may require Administrator PowerShell."
Write-Host "- Fully quit and restart the affected app after changes."
