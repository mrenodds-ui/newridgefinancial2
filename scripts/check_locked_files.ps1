# PowerShell script to check for locked files in node_modules
$folders = @('frontend/node_modules')
foreach ($folder in $folders) {
    Write-Host "Checking: $folder"
    if (Test-Path $folder) {
        try {
            Get-ChildItem -Path $folder -Recurse -ErrorAction Stop | Out-Null
            Write-Host "  No lock detected."
        } catch {
            Write-Host "  LOCKED: $($_.Exception.Message)"
        }
    } else {
        Write-Host "  Not found."
    }
}
Write-Host "Check complete. Close all dev servers and editors if locks are found."
