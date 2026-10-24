@echo off
echo.
echo  ============================================================
echo   BashGuard -- Simulate Before You Execute
echo  ============================================================
echo.

:: ---- Backend Setup ----
echo  [1/4] Installing Python dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo  ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)
echo  [1/4] Done.

:: ---- Frontend Setup ----
echo  [2/4] Installing frontend dependencies...
cd frontend
call npm install --silent
if errorlevel 1 (
    echo  ERROR: npm install failed. Make sure Node.js is installed.
    pause
    exit /b 1
)
echo  [2/4] Done.
cd ..

:: ---- Start Backend ----
echo  [3/4] Starting BashGuard API server (port 8001)...
start "BashGuard API" cmd /k "uvicorn server:app --host 0.0.0.0 --port 8001 --reload"
timeout /t 2 /nobreak >nul

:: ---- Start Frontend ----
echo  [4/4] Starting React frontend (port 5173)...
start "BashGuard Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 3 /nobreak >nul

:: ---- Open Browser ----
echo.
echo  Opening BashGuard in your browser...
start http://localhost:5173

echo.
echo  ============================================================
echo   BashGuard is running!
echo   Frontend : http://localhost:5173
echo   API      : http://localhost:8001
echo   API Docs : http://localhost:8001/docs
echo  ============================================================
echo.
echo  Close the two terminal windows to stop the servers.
pause
