@echo off
echo Starting UAMP RMS Backend...
echo.
echo Make sure PostgreSQL is running and you have created the database:
echo   createdb rms_db
echo.
echo Then copy .env.example to .env and update credentials.
echo.
uvicorn main:app --reload --host 0.0.0.0 --port 8000
