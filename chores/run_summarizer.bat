@echo off
chcp 65001 > nul
title 파일 분류 & AI 요약기

echo ========================================================
echo   📂 파일 분류 ^& AI 요약 도구
echo ========================================================
echo.

set SCRIPT_DIR=%~dp0
set PY_SCRIPT=%SCRIPT_DIR%classify_and_summarize.py

echo [1] 원본 폴더 경로를 입력하세요 (분류할 파일이 있는 폴더):
set /p SOURCE_DIR=^> 

echo.
echo [2] 결과 저장 폴더 경로를 입력하세요 (분류 결과가 저장될 폴더):
set /p OUTPUT_DIR=^> 

echo.
echo [3] 사용할 AI를 선택하세요:
echo     1. claude
echo     2. gemini
echo     3. gpt
set /p AI_CHOICE=^> 번호 입력: 

if "%AI_CHOICE%"=="1" set AI_MODEL=claude
if "%AI_CHOICE%"=="2" set AI_MODEL=gemini
if "%AI_CHOICE%"=="3" set AI_MODEL=gpt
if not defined AI_MODEL set AI_MODEL=gemini

echo.
echo --------------------------------------------------------
echo   원본 폴더 : %SOURCE_DIR%
echo   결과 폴더 : %OUTPUT_DIR%
echo   선택 AI   : %AI_MODEL%
echo --------------------------------------------------------
echo.

python "%PY_SCRIPT%" "%SOURCE_DIR%" "%OUTPUT_DIR%" --ai %AI_MODEL%

echo.
echo ========================================================
echo   작업 완료! 아무 키나 누르면 창이 닫힙니다.
echo ========================================================
pause > nul
