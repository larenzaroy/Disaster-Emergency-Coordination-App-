@echo off
echo ResQNet 2.0 - Emergency Management System
echo ============================================
echo Starting server on http://localhost:8000
echo.
echo PORTALS:
echo   Patient  -> http://localhost:8000/patient
echo   Doctor   -> http://localhost:8000/doctor
echo   Ambulance -> http://localhost:8000/ambulance
echo.
echo Demo Login:
echo   Patient:   patient@demo.com  (any password)
echo   Doctor:    doctor@demo.com   (any password)
echo   Ambulance: ambulance@demo.com (any password)
echo.
py main.py
pause
