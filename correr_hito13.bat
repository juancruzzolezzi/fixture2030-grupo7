@echo off
cd /d "%~dp0"
set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%GITBASH%" set "GITBASH=%LocalAppData%\Programs\Git\bin\bash.exe"
if not exist "%GITBASH%" (
  echo No encontre Git Bash. Instala Git for Windows y volve a correr esto.
  pause
  exit /b 1
)
"%GITBASH%" fixture2030-hito-13-monitoreo/scripts/correr_todo.sh
pause
