<#
.SYNOPSIS
  Build HAL programming context bundle for Gemma 2 code review.

.DESCRIPTION
  Writes gemma2_hal_program_context.txt at repo root with:
  - validate-hal.mjs output (if node is available)
  - Key HAL source slices (routing, agent, skills, validator, widget contract)

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gemma2_hal_program_context.ps1
#>
[CmdletBinding()]
param(
    [int]$MaxChars = 48000
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Nr2 = Join-Path $Root 'NewRidgeFinancial2'
$OutFile = Join-Path $Root 'gemma2_hal_program_context.txt'

function Limit-TextLength {
    param([string]$Text, [int]$Limit)
    if ($Text.Length -le $Limit) { return $Text }
    $half = [Math]::Floor($Limit / 2)
    return (
        $Text.Substring(0, $half) +
        "`n`n...[truncated at $Limit chars]...`n`n" +
        $Text.Substring($Text.Length - $half)
    )
}

function Get-LineRangeText {
    param([string]$RelPath, [int]$StartLine, [int]$EndLine)
    $path = Join-Path $Root $RelPath
    if (-not (Test-Path $path)) {
        Write-Warning "Skipping missing file: $RelPath"
        return ''
    }
    $lines = Get-Content -Path $path -Encoding UTF8
    $start = [Math]::Max(1, $StartLine)
    $end = [Math]::Min($lines.Count, $EndLine)
    if ($end -lt $start) { return '' }
    $snippet = ($lines[($start - 1)..($end - 1)] -join "`n")
    return "=== $RelPath (lines $start-$end) ===`n$snippet`n"
}

function Get-FullFileText {
    param([string]$RelPath, [int]$MaxFileChars = 8000)
    $path = Join-Path $Root $RelPath
    if (-not (Test-Path $path)) { return '' }
    $text = Get-Content -Path $path -Raw -Encoding UTF8
    if ($text.Length -gt $MaxFileChars) {
        $text = Limit-TextLength -Text $text -Limit $MaxFileChars
    }
    return "=== $RelPath (full, capped) ===`n$text`n"
}

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine('HAL PROGRAMMING REVIEW CONTEXT — NewRidgeFinancial 2.0')
[void]$sb.AppendLine("Generated (local): $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('SCOPE: HAL intent routing, agent loop, skills, route execution, widget contract, validate-hal.mjs expectations.')
[void]$sb.AppendLine('')

# validate-hal.mjs output
$validateScript = Join-Path $Nr2 'validate-hal.mjs'
if (Test-Path $validateScript) {
    [void]$sb.AppendLine('=== validate-hal.mjs (automated regression output) ===')
    Push-Location $Nr2
    try {
        $validateOut = & node validate-hal.mjs 2>&1 | Out-String
        [void]$sb.AppendLine($validateOut.Trim())
    } catch {
        [void]$sb.AppendLine("validate-hal.mjs failed to run: $_")
    } finally {
        Pop-Location
    }
    [void]$sb.AppendLine('')
}

# HAL programming slices — routing, agent, self-check, skills, execution, contract
$segments = @(
    @{ Rel = 'NewRidgeFinancial2/site/hal-core.js'; Start = 1; End = 120 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-core.js'; Start = 900; End = 1100 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-agent.js'; Start = 1; End = 80 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-agent.js'; Start = 560; End = 650 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-agent.js'; Start = 720; End = 860 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-route-exec.js'; Start = 1; End = 120 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-skills.js'; Start = 1; End = 80 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-skills.js'; Start = 1330; End = 1420 }
    @{ Rel = 'NewRidgeFinancial2/site/hal-skills.js'; Start = 2500; End = 2600 }
    @{ Rel = 'NewRidgeFinancial2/site/widget-contract.js'; Start = 1; End = 220 }
    @{ Rel = 'NewRidgeFinancial2/site/app.js'; Start = 1; End = 80 }
    @{ Rel = 'NewRidgeFinancial2/validate-hal.mjs'; Start = 520; End = 560 }
    @{ Rel = 'NewRidgeFinancial2/validate-hal.mjs'; Start = 700; End = 790 }
    @{ Rel = 'NewRidgeFinancial2/validate-hal.mjs'; Start = 1250; End = 1290 }
)

foreach ($seg in $segments) {
    $chunk = Get-LineRangeText -RelPath $seg.Rel -StartLine $seg.Start -EndLine $seg.End
    if ($chunk) { [void]$sb.AppendLine($chunk) }
}

$modelsChunk = Get-FullFileText -RelPath 'NewRidgeFinancial2/site/data/hal-models.json' -MaxFileChars 6000
if ($modelsChunk) { [void]$sb.AppendLine($modelsChunk) }
$managerChunk = Get-FullFileText -RelPath 'NewRidgeFinancial2/site/data/hal-manager.json' -MaxFileChars 4000
if ($managerChunk) { [void]$sb.AppendLine($managerChunk) }

$content = Limit-TextLength -Text $sb.ToString() -Limit $MaxChars
Set-Content -Path $OutFile -Value $content -Encoding UTF8
Write-Host "Wrote $OutFile ($($content.Length) chars)" -ForegroundColor Green
