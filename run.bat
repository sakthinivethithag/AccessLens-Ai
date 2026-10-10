@echo off
REM AccessLens AI - one-click start for Windows
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Could not create the virtual environment. Is Python installed and on PATH?
        pause
        exit /b 1
    )
)

call venv\Scripts\activate
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo Starting AccessLens AI at http://127.0.0.1:5000  (press Ctrl+C to stop)
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
python app.py
pause
