$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Source = Join-Path $RepoRoot "codex-skill\jqcli"

if (-not (Test-Path -LiteralPath $Source)) {
    throw "Skill source not found: $Source"
}

$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillsDir = Join-Path $CodexHome "skills"
$Target = Join-Path $SkillsDir "jqcli"

New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null
$ResolvedSkillsDir = (Resolve-Path -LiteralPath $SkillsDir).Path
$ResolvedTargetParent = (Resolve-Path -LiteralPath (Split-Path -Parent $Target)).Path

if ($ResolvedTargetParent -ne $ResolvedSkillsDir) {
    throw "Refusing to install outside skills directory: $Target"
}

if (Test-Path -LiteralPath $Target) {
    $ResolvedTarget = (Resolve-Path -LiteralPath $Target).Path
    if (-not $ResolvedTarget.StartsWith($ResolvedSkillsDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside skills directory: $ResolvedTarget"
    }
    Remove-Item -LiteralPath $Target -Recurse -Force
}

Copy-Item -LiteralPath $Source -Destination $Target -Recurse

Write-Output "Installed jqcli skill to $Target"
