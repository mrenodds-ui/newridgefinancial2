@echo off
set "SCRIPT_DIR=%~dp0"
set "REGISTER_SCRIPT=%SCRIPT_DIR%Register-HAL-Model-Automation.ps1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%REGISTER_SCRIPT%"" -SystemBoot'"

