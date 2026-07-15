@echo off
REM SideNotesIM HAL watcher is retired. Use BlueNote Communicator Lights instead.
echo HAL SideNotes watcher is disabled.
echo Use: C:\softdent\HAL-BlueNote-Workstation\Start-HAL-BlueNote.bat
if exist "C:\softdent\HAL-BlueNote-Workstation\Start-HAL-BlueNote.bat" (
  start "" "C:\softdent\HAL-BlueNote-Workstation\Start-HAL-BlueNote.bat"
)
exit /b 0
