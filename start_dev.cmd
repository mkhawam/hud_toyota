@echo off
rem Works from cmd or PowerShell regardless of execution policy:  start_dev [sim|elm327]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dev.ps1" %*
