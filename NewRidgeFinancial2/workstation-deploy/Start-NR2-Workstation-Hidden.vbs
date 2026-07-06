' Silent NR2 Workstation boot — no console flash (Startup / Scheduled Task).
Option Explicit
Dim sh, fso, pkgRoot
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
pkgRoot = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = pkgRoot
sh.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & pkgRoot & "\Start-Workstation.ps1"" -Hidden", 0, False
