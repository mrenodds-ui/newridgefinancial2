<#
.SYNOPSIS
  Build NR2 micro focus bundles for isolated 235B section audits.

.DESCRIPTION
  Writes 235b_eval_section{1a,1b,...}.txt at repo root (~12k chars each).
  Run before scripts/run_235b_isolated_section.ps1 -Section 1a (etc.).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_235b_nr2_focus.ps1
#>
[CmdletBinding()]
param(
    [int]$MaxCharsPerBundle = 12000,
    [int]$SliceMaxChars = 6000
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Nr2 = Join-Path $Root 'NewRidgeFinancial2'

function Limit-TextLength {
    param(
        [string]$Text,
        [int]$Limit
    )
    if ($Text.Length -le $Limit) {
        return $Text
    }
    $half = [Math]::Floor($Limit / 2)
    return (
        $Text.Substring(0, $half) +
        "`n`n...[truncated at $Limit chars]...`n`n" +
        $Text.Substring($Text.Length - $half)
    )
}

function Get-LineRangeText {
    param(
        [string]$RelPath,
        [int]$StartLine,
        [int]$EndLine
    )

    $path = Join-Path $Root $RelPath
    if (-not (Test-Path $path)) {
        Write-Warning "Skipping missing file: $RelPath"
        return ''
    }

    $lines = Get-Content -Path $path -Encoding UTF8
    $start = [Math]::Max(1, $StartLine)
    $end = [Math]::Min($lines.Count, $EndLine)
    if ($end -lt $start) {
        return ''
    }

    $snippet = ($lines[($start - 1)..($end - 1)] -join "`n")
    return "=== $RelPath (lines $start-$end) ===`n$snippet`n"
}

function Write-SliceFocusBundle {
    param(
        [string]$OutName,
        [hashtable]$Spec
    )

    $max = if ($Spec.MaxChars) { [int]$Spec.MaxChars } else { $SliceMaxChars }
    $sb = [System.Text.StringBuilder]::new()

    if ($Spec.Segments) {
        foreach ($seg in $Spec.Segments) {
            $chunk = Get-LineRangeText -RelPath $seg.Rel -StartLine $seg.Start -EndLine $seg.End
            if ($chunk) {
                [void]$sb.AppendLine($chunk)
            }
        }
    }

    if ($Spec.Files) {
        foreach ($rel in $Spec.Files) {
        $path = Join-Path $Root $rel
        if (-not (Test-Path $path)) {
            Write-Warning "Skipping missing file: $rel"
            continue
        }
        $text = Get-Content -Path $path -Raw -Encoding UTF8
        [void]$sb.AppendLine("=== $rel ===")
        [void]$sb.AppendLine($text)
        [void]$sb.AppendLine('')
        }
    }

    $content = Limit-TextLength -Text $sb.ToString().TrimEnd() -Limit $max
    $outPath = Join-Path $Root $OutName
    Set-Content -Path $outPath -Value $content -Encoding UTF8
    Write-Host ("Wrote {0} ({1} chars)" -f $OutName, $content.Length) -ForegroundColor Green
}

function Write-FocusBundle {
    param(
        [string]$OutName,
        [string[]]$RelativePaths,
        [int]$MaxChars = $MaxCharsPerBundle
    )

    $sb = [System.Text.StringBuilder]::new()
    $total = 0
    foreach ($rel in $RelativePaths) {
        $path = Join-Path $Root $rel
        if (-not (Test-Path $path)) {
            Write-Warning "Skipping missing file: $rel"
            continue
        }
        $text = Get-Content -Path $path -Raw -Encoding UTF8
        $header = "=== $rel ==="
        [void]$sb.AppendLine($header)
        [void]$sb.AppendLine($text)
        [void]$sb.AppendLine('')
        $total = $sb.Length
        if ($total -ge $MaxChars) {
            break
        }
    }

    $content = $sb.ToString()
    if ($content.Length -gt $MaxChars) {
        $content = $content.Substring(0, $MaxChars) + "`n`n...[truncated at $MaxChars chars]...`n"
    }

    $outPath = Join-Path $Root $OutName
    Set-Content -Path $outPath -Value $content -Encoding UTF8
    Write-Host ("Wrote {0} ({1} chars)" -f $OutName, $content.Length) -ForegroundColor Green
}

$bundles = [ordered]@{
    '235b_eval_section1a_focus.txt' = @(
        'NewRidgeFinancial2/softdent_dashboard_period_sync.py'
        'NewRidgeFinancial2/import_direct_pipeline.py'
        'NewRidgeFinancial2/test_softdent_dashboard_period_sync.py'
    )
    '235b_eval_section1b_focus.txt' = @(
        'NewRidgeFinancial2/site/import-loader.js'
        'NewRidgeFinancial2/test_import_loader_accounting.mjs'
    )
    '235b_eval_section1c_focus.txt' = @(
        'NewRidgeFinancial2/import_loader.py'
        'NewRidgeFinancial2/import_sync.py'
        'NewRidgeFinancial2/practice_source_access.py'
    )
    '235b_eval_section2a_focus.txt' = @(
        'NewRidgeFinancial2/site/hal-skills.js'
        'NewRidgeFinancial2/site/widget-contract.js'
    )
    '235b_eval_section2b_focus.txt' = @(
        'NewRidgeFinancial2/site/import-loader.js'
        'NewRidgeFinancial2/site/hal-widget-master-chart.js'
    )
    '235b_eval_section2c_focus.txt' = @(
        'NewRidgeFinancial2/site/page-canvas.js'
        'NewRidgeFinancial2/site/hal-page.js'
        'NewRidgeFinancial2/validate-hal.mjs'
    )
}

foreach ($entry in $bundles.GetEnumerator()) {
    Write-FocusBundle -OutName $entry.Key -RelativePaths $entry.Value
}

$sliceSpecs = [ordered]@{
    '235b_eval_section1a1_focus.txt' = @{
        MaxChars = 8200
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/softdent_dashboard_period_sync.py'; Start = 131; End = 319 }
        )
    }
    '235b_eval_section1a2_focus.txt' = @{
        MaxChars = 13000
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/import_direct_pipeline.py'; Start = 195; End = 464 }
        )
        Files = @('NewRidgeFinancial2/test_softdent_dashboard_period_sync.py')
    }
    '235b_eval_section1b1_focus.txt' = @{
        MaxChars = 9500
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/site/import-loader.js'; Start = 385; End = 515 }
            @{ Rel = 'NewRidgeFinancial2/site/import-loader.js'; Start = 522; End = 579 }
            @{ Rel = 'NewRidgeFinancial2/site/import-loader.js'; Start = 1264; End = 1300 }
        )
    }
    '235b_eval_section1b2_focus.txt' = @{
        Files = @('NewRidgeFinancial2/test_import_loader_accounting.mjs')
    }
    '235b_eval_section1c1_focus.txt' = @{
        MaxChars = 10500
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/import_loader.py'; Start = 92; End = 335 }
        )
    }
    '235b_eval_section1c2_focus.txt' = @{
        MaxChars = 12000
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/import_sync.py'; Start = 649; End = 750 }
            @{ Rel = 'NewRidgeFinancial2/practice_source_access.py'; Start = 119; End = 180 }
            @{ Rel = 'NewRidgeFinancial2/practice_source_access.py'; Start = 449; End = 500 }
        )
    }
    '235b_eval_section2a1_focus.txt' = @{
        MaxChars = 13000
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/site/hal-skills.js'; Start = 1331; End = 1401 }
            @{ Rel = 'NewRidgeFinancial2/site/hal-skills.js'; Start = 1501; End = 1580 }
            @{ Rel = 'NewRidgeFinancial2/site/hal-skills.js'; Start = 1773; End = 1870 }
        )
    }
    '235b_eval_section2a2_focus.txt' = @{
        MaxChars = 9000
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/site/widget-contract.js'; Start = 1; End = 211 }
        )
    }
    '235b_eval_section2b1_focus.txt' = @{
        MaxChars = 11000
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/site/hal-widget-master-chart.js'; Start = 1; End = 250 }
        )
    }
    '235b_eval_section2b2_focus.txt' = @{
        MaxChars = 9500
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/site/import-loader.js'; Start = 1020; End = 1150 }
            @{ Rel = 'NewRidgeFinancial2/site/import-loader.js'; Start = 1264; End = 1300 }
        )
    }
    '235b_eval_section2c1_focus.txt' = @{
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/site/page-canvas.js'; Start = 160; End = 520 }
        )
    }
    '235b_eval_section2c2_focus.txt' = @{
        MaxChars = 12000
        Segments = @(
            @{ Rel = 'NewRidgeFinancial2/site/hal-page.js'; Start = 1; End = 120 }
            @{ Rel = 'NewRidgeFinancial2/site/hal-page.js'; Start = 400; End = 480 }
            @{ Rel = 'NewRidgeFinancial2/validate-hal.mjs'; Start = 706; End = 730 }
            @{ Rel = 'NewRidgeFinancial2/validate-hal.mjs'; Start = 780; End = 785 }
        )
    }
}

foreach ($entry in $sliceSpecs.GetEnumerator()) {
    Write-SliceFocusBundle -OutName $entry.Key -Spec $entry.Value
}

# Legacy section runners still accept combined focus files.
Copy-Item -Path (Join-Path $Root '235b_eval_section1a_focus.txt') -Destination (Join-Path $Root '235b_eval_section1_focus.txt') -Force
Copy-Item -Path (Join-Path $Root '235b_eval_section2a_focus.txt') -Destination (Join-Path $Root '235b_eval_section2_focus.txt') -Force

Write-Host 'NR2 micro focus bundles ready.' -ForegroundColor Cyan
