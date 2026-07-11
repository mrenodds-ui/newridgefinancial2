# Shared helper: build a Scheduled Task /TR that runs a .ps1 with no console flash.
# Prefers pythonw + CREATE_NO_WINDOW (reliable). Falls back to wscript VBS if pythonw missing.

function Get-HiddenPowerShellLauncher {
    [CmdletBinding()]
    param()

    $scriptsDir = $PSScriptRoot
    $pyLauncher = Join-Path $scriptsDir "run_powershell_hidden.py"
    $vbsLauncher = Join-Path $scriptsDir "Run-PowerShell-Hidden.vbs"

    $pythonwCandidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\pythonw.exe",
        (Join-Path (Split-Path -Parent (Split-Path -Parent $scriptsDir)) ".venv\Scripts\pythonw.exe")
    )

    foreach ($exe in $pythonwCandidates) {
        if ($exe -and (Test-Path $exe) -and (Test-Path $pyLauncher)) {
            return [pscustomobject]@{
                Kind = "pythonw"
                Execute = $exe
                Launcher = $pyLauncher
            }
        }
    }

    $where = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($where -and (Test-Path $pyLauncher)) {
        return [pscustomobject]@{
            Kind = "pythonw"
            Execute = $where.Source
            Launcher = $pyLauncher
        }
    }

    if (Test-Path $vbsLauncher) {
        return [pscustomobject]@{
            Kind = "wscript"
            Execute = "wscript.exe"
            Launcher = $vbsLauncher
        }
    }

    throw "No hidden launcher found (need pythonw + run_powershell_hidden.py, or Run-PowerShell-Hidden.vbs)."
}

function Get-HiddenPowerShellTaskCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$ExtraArgs = @()
    )

    $launcher = Get-HiddenPowerShellLauncher
    $extra = if ($ExtraArgs -and $ExtraArgs.Count -gt 0) { " " + ($ExtraArgs -join " ") } else { "" }

    if ($launcher.Kind -eq "pythonw") {
        return "`"$($launcher.Execute)`" `"$($launcher.Launcher)`" `"$ScriptPath`"$extra"
    }

    return "wscript.exe //B //Nologo `"$($launcher.Launcher)`" `"$ScriptPath`"$extra"
}

function Set-HiddenScheduledTaskAction {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$TaskName,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$ExtraArgs = @()
    )

    $launcher = Get-HiddenPowerShellLauncher
    $argParts = @("`"$($launcher.Launcher)`"", "`"$ScriptPath`"") + @($ExtraArgs)
    if ($launcher.Kind -eq "wscript") {
        $argParts = @("//B", "//Nologo") + $argParts
    }
    $action = New-ScheduledTaskAction -Execute $launcher.Execute -Argument ($argParts -join " ")
    Set-ScheduledTask -TaskName $TaskName -Action $action | Out-Null
}
