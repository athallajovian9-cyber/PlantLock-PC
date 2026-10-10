@echo off
title PlantLock
cd /d "%~dp0"
python -c "import cv2, torch, transformers, customtkinter, PIL" 2>nul || (
  echo Installing dependencies (first run only, ~600 MB one time)...
  python -m pip install -r requirements.txt
)
start "" pythonw plantlock.py
if errorlevel 1 python plantlock.py
