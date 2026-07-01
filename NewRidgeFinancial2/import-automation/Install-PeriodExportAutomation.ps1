# Wires SoftDent period export automation env vars for scheduled refresh tasks.
$ErrorActionPreference = 'Stop'
$Installer = 'C:\New folder\ops\softdent\tasks\Install-SoftdentExportAutomationEnv.ps1'
if (!(Test-Path -LiteralPath $Installer)) {
    throw "Missing installer: $Installer"
}
& $Installer
