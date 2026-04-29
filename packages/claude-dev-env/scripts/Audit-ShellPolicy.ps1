#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Scans Claude Code settings*.json files for legacy shell-invocation patterns
    that violate the pwsh-only policy.

.DESCRIPTION
    Walks the configured project roots, finds every settings.json,
    settings.local.json, and settings.local.json.template, and counts permission
    rule strings that invoke powershell.exe / Windows PowerShell 5.1 / bash -c /
    cmd /c instead of pwsh. Prints exactly one summary line and exits 0 when
    clean or 1 when violations remain.

.PARAMETER Roots
    One or more directories to scan recursively. Defaults to the user's known
    Claude Code project parents.

.PARAMETER Verbose
    Use the standard PowerShell -Verbose switch to print per-file violation
    detail in addition to the summary line.

.OUTPUTS
    One line on stdout:
        POLICY: OK
        POLICY: VIOLATIONS=<count> IN=<n> FILES

.EXAMPLE
    pwsh -NoProfile -File Audit-ShellPolicy.ps1
    pwsh -NoProfile -File Audit-ShellPolicy.ps1 -Verbose
    pwsh -NoProfile -File Audit-ShellPolicy.ps1 -Roots 'Y:\Projects'
#>
[CmdletBinding()]
param(
    [string[]]$Roots = @(
        'Y:\Projects',
        'Y:\Information Technology\Scripts',
        'Y:\Python',
        'Y:\claude-settings'
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$violationPatterns = @(
    [regex]'^Bash\(powershell(?:\.exe)?(?:[\s:].*)?\)$'
    [regex]'^Bash\(bash\s+(?:-c|--login|--rcfile|--init-file)\b.*\)$'
    [regex]'^Bash\(cmd(?:\.exe)?\s+/c\b.*\)$'
)

$settingsFileNames = @(
    'settings.json',
    'settings.local.json',
    'settings.local.json.template'
)

function Test-RuleViolatesPolicy {
    param([string]$Rule)
    foreach ($pattern in $violationPatterns) {
        if ($pattern.IsMatch($Rule)) { return $true }
    }
    return $false
}

function Test-HasProperty {
    param($Target, [string]$Name)
    if ($null -eq $Target) { return $false }
    if ($Target -isnot [psobject]) { return $false }
    return ($Target.PSObject.Properties.Name -contains $Name)
}

function Get-PermissionRuleArrays {
    param([Parameter(Mandatory)] $SettingsObject)
    $arrays = @()
    if (-not (Test-HasProperty -Target $SettingsObject -Name 'permissions')) { return $arrays }
    $permissions = $SettingsObject.permissions
    foreach ($key in @('allow', 'ask')) {
        if (-not (Test-HasProperty -Target $permissions -Name $key)) { continue }
        $maybeArray = $permissions.$key
        if ($null -ne $maybeArray) { $arrays += , $maybeArray }
    }
    return $arrays
}

$totalViolations = 0
$filesWithViolations = 0
$existingRoots = $Roots | Where-Object { Test-Path $_ }

foreach ($root in $existingRoots) {
    $candidateFiles = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $settingsFileNames -contains $_.Name }
    foreach ($file in $candidateFiles) {
        $rawContent = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
        if ([string]::IsNullOrWhiteSpace($rawContent)) { continue }
        try {
            $parsed = $rawContent | ConvertFrom-Json -ErrorAction Stop
        } catch {
            Write-Verbose "Skipped (invalid JSON): $($file.FullName)"
            continue
        }
        $fileViolationCount = 0
        foreach ($ruleArray in (Get-PermissionRuleArrays -SettingsObject $parsed)) {
            foreach ($rule in $ruleArray) {
                if ($rule -is [string] -and (Test-RuleViolatesPolicy -Rule $rule)) {
                    $fileViolationCount++
                    Write-Verbose "  $($file.FullName): $rule"
                }
            }
        }
        if ($fileViolationCount -gt 0) {
            $totalViolations += $fileViolationCount
            $filesWithViolations++
        }
    }
}

if ($totalViolations -eq 0) {
    Write-Output 'POLICY: OK'
    exit 0
}

Write-Output ('POLICY: VIOLATIONS={0} IN={1} FILES' -f $totalViolations, $filesWithViolations)
exit 1
