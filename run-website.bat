@echo off
setlocal
set "ROOT=%~dp0"

echo Starting Thiqa demo services...
echo Install Python dependencies first: cd agents ^&^& pip install -r requirements.txt
echo Install Node dependencies first: cd server ^&^& npm install

start "Thiqa Mock Insurers - 8001" cmd /k "cd /d ""%ROOT%agents"" && python -m uvicorn mock_insurer_api:app --host 127.0.0.1 --port 8001"
timeout /t 2 /nobreak >nul
start "Thiqa Agents - 8000" cmd /k "cd /d ""%ROOT%agents"" && python -m uvicorn main:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul
start "Thiqa Website - 3000" cmd /k "cd /d ""%ROOT%server"" && npm start"

timeout /t 3 /nobreak >nul
start "" "http://localhost:3000"
