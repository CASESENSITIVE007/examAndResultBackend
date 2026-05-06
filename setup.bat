@echo off
echo === UAMP RMS Backend Setup ===
echo.

echo [1/3] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo [2/3] Installing dependencies...
pip install -r requirements.txt

echo [3/3] Done!
echo.
echo Next steps:
echo   1. Copy .env.example to .env and update DATABASE_URL
echo   2. Create Postgres DB:  createdb rms_db
echo   3. Initialize DB:       python init_db.py
echo   4. Start server:        uvicorn main:app --reload
echo.
