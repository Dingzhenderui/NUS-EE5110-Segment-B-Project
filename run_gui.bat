@echo off
chcp 65001 >nul
title EE5110 Event Camera Simulator
echo 正在启动 EE5110 事件相机模拟器图形界面...
set PYTHON_EXE=E:\anaconda3\envs\EE5110-Segment-B\python.exe
if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" run_app.py
) else (
    python run_app.py
)
if errorlevel 1 (
    echo 启动出错，请检查 Python 环境与依赖。
    pause
)
