@echo off
echo Starting Code Review Buddy...
cd C:\Users\nikki\code-review-buddy
call venv\Scripts\activate.bat
start "ngrok" cmd /k "C:\ngrok\ngrok.exe http 8000"
timeout /t 3
start "Bot Server" cmd /k "uvicorn main:app --port 8000"
echo Both started! Open http://localhost:8000