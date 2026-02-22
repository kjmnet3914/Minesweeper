@echo off
cd /d "%~dp0"
python minesweeper.py
if %errorlevel% neq 0 (
    echo.
    echo 오류가 발생했습니다. Python이 설치되어 있는지 확인하세요.
    pause
)
