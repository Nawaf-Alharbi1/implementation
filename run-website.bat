@echo off
setlocal
set "ROOT=%~dp0"

echo Starting Thiqa Ecosystem...
echo 1. Insurers Platform & Mock APIs (Port 8001)
echo 2. Thiqa Multi-Agent Service (Port 8000)
echo 3. Thiqa Recommendation Website (Port 3000)

:: تشغيل الموقع المستقل لشركات التأمين والـ API على المنفذ 8001
start "Thiqa Insurers Platform - 8001" cmd /k "cd /d ""%ROOT%agents"" && python -m uvicorn mock_insurer_api:app --host 127.0.0.1 --port 8001"
timeout /t 2 /nobreak >nul

:: تشغيل خدمة الوكلاء الثلاثة على المنفذ 8000
start "Thiqa Agents Service - 8000" cmd /k "cd /d ""%ROOT%agents"" && python -m uvicorn main:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul

:: تشغيل موقع ثقة الأساسي على المنفذ 3000
start "Thiqa Main Web - 3000" cmd /k "cd /d ""%ROOT%server"" && npm start"

timeout /t 3 /nobreak >nul

:: فتح الموقعين معاً في المتصفح
start "" "http://localhost:3000"
start "" "http://127.0.0.1:8001"