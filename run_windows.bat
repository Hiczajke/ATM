@echo off
REM Uruchomienie aplikacji ATM w katalogu projektu.
cd /d "%~dp0"
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py -3 app.py
) else (
    python app.py
)
pause
