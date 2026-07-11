' Run a PowerShell .ps1 with no console window (for Scheduled Tasks / Startup).
' Usage:
'   wscript.exe //B //Nologo Run-PowerShell-Hidden.vbs "C:\path\script.ps1" [extra args...]
Option Explicit
Dim sh, args, i, cmd, arg
Set sh = CreateObject("WScript.Shell")
Set args = WScript.Arguments
If args.Count < 1 Then
  WScript.Quit 1
End If

cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & args(0) & """"
For i = 1 To args.Count - 1
  arg = args(i)
  If InStr(arg, " ") > 0 And Left(arg, 1) <> """" Then
    cmd = cmd & " """ & arg & """"
  Else
    cmd = cmd & " " & arg
  End If
Next

' 0 = hidden window, False = do not wait
sh.Run cmd, 0, False