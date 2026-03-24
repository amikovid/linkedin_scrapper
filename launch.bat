@echo off
cd /d "%~dp0"
echo Starting LinkedIn Pattern Scraper...
echo Opening in browser at http://localhost:8501
streamlit run app.py --server.headless false
pause
