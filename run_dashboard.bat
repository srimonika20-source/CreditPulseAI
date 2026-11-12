@echo off
cd /d "%~dp0"
echo Starting CreditPulse AI...
.\.venv312\Scripts\python.exe -m streamlit run app.py
pause
