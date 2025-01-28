@echo off
chcp 65001 > nul
cls
title 🚀 Ollama Super Manager v2.0

:: カラーコード設定
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do (
  set "COLOR_END=%%a"
  set "COLOR_SET=%%b"
)

:: カラーパレット定義
set "COLOR_TITLE=38;5;45"
set "COLOR_MENU=38;5;255"
set "COLOR_SELECTED=38;5;48;48;5;232"
set "COLOR_WARNING=38;5;196"
set "COLOR_SUCCESS=38;5;46"
set "COLOR_PROGRESS=38;5;33"
set "COLOR_HEADER=38;5;99"

:: アニメーション用文字
set "SPINNER=⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

:INIT
call :SETUP_UI
goto MAIN_MENU

:MAIN_MENU
call :SHOW_HEADER
echo %COLOR_SET%%COLOR_MENU%╔══════════════════════════════════╗
echo ║         メインメニュー          ║
echo ╠══════════════════════════════════╣
echo ║  1. Ollamaサーバー起動          ║
echo ║  2. チャットプログラム実行      ║
echo ║  3. 依存ライブラリインストール  ║
echo ║  4. ヘルプ＆設定                ║
echo ║  5. 終了                        ║
echo ╚══════════════════════════════════╝
echo %COLOR_END%
call :GET_CHOICE 5

if %choice%==1 goto START_OLLAMA
if %choice%==2 goto RUN_CHAT
if %choice%==3 goto INSTALL_DEPS
if %choice%==4 goto HELP_MENU
if %choice%==5 exit /b

:START_OLLAMA
call :SHOW_HEADER
echo %COLOR_SET%%COLOR_TITLE%🚀 Ollamaサーバーを起動します...%COLOR_END%
echo.
echo %COLOR_SET%%COLOR_MENU%📢 注意: このウィンドウを閉じるとサーバーが停止します
echo      Ctrl+C で終了できます%COLOR_END%
echo.
call :SHOW_PROGRESS
ollama serve
echo.
pause
goto MAIN_MENU

:RUN_CHAT
call :SHOW_HEADER
echo %COLOR_SET%%COLOR_TITLE%🤖 チャットプログラムを起動します...%COLOR_END%
echo.
if not exist "ollama_chat.py" (
  call :SHOW_ERROR "ollama_chat.pyが見つかりません"
  pause
  goto MAIN_MENU
)
call :SHOW_PROGRESS
python ollama_chat.py
if %ERRORLEVEL% neq 0 (
  call :SHOW_ERROR "実行に失敗しました"
  echo %COLOR_SET%%COLOR_WARNING%考えられる原因:%COLOR_END%
  echo 1. Pythonがインストールされていない
  echo 2. 依存ライブラリが不足している
  echo 3. スクリプトに構文エラーがある
)
echo.
pause
goto MAIN_MENU

:INSTALL_DEPS
call :SHOW_HEADER
echo %COLOR_SET%%COLOR_TITLE%📦 依存ライブラリをインストールします...%COLOR_END%
echo.
call :CHECK_PYTHON || goto MAIN_MENU
call :CHECK_PIP || goto MAIN_MENU

echo %COLOR_SET%%COLOR_PROGRESS%🔄 aiohttpをインストール中...%COLOR_END%
call :SHOW_SPINNER "インストール中" python -m pip install aiohttp --user

if %ERRORLEVEL% neq 0 (
  call :SHOW_ERROR "インストール失敗"
  echo %COLOR_SET%%COLOR_WARNING%解決方法:%COLOR_END%
  echo 1. インターネット接続を確認
  echo 2. 管理者権限で再実行
  echo    → このプログラムを右クリックで[管理者として実行]
) else (
  call :SHOW_SUCCESS "インストール完了！"
)
pause
goto MAIN_MENU

:HELP_MENU
call :SHOW_HEADER
echo %COLOR_SET%%COLOR_TITLE%📚 ヘルプ＆設定%COLOR_END%
echo.
echo %COLOR_SET%%COLOR_MENU%► システム情報:%COLOR_END%
ver | findstr /i "Version"
wmic os get Caption /value | findstr /i "Caption"
echo.
echo %COLOR_SET%%COLOR_MENU%► 必要環境:%COLOR_END%
echo - Windows 10/11 64-bit
echo - Python 3.11+
echo - インターネット接続環境
echo.
pause
goto MAIN_MENU

:GET_CHOICE
setlocal EnableDelayedExpansion
set "max=%1"
:CHOICE_LOOP
echo %COLOR_SET%%COLOR_SELECTED%[入力待ち]%COLOR_END% 選択 (1-%max%) : 
set /p "choice="
if "!choice!"=="" (
  call :SHOW_ERROR "入力がありません"
  goto CHOICE_LOOP
)
if !choice! lss 1 (
  call :SHOW_ERROR "1より小さい数値は無効です"
  goto CHOICE_LOOP
)
if !choice! gtr %max% (
  call :SHOW_ERROR "%max%より大きい数値は無効です"
  goto CHOICE_LOOP
)
endlocal & set choice=%choice%
exit /b

:SHOW_HEADER
cls
echo %COLOR_SET%%COLOR_HEADER%╔══════════════════════════════════════╗
echo ║ ██████╗ ██╗     ██╗      ███╗   ███╗ █████╗ ║
echo ║ ██╔══██╗██║     ██║      ████╗ ████║██╔══██╗║
echo ║ ██████╔╝██║     ██║█████╗██╔████╔██║███████║║
echo ║ ██╔══██╗██║     ██║╚════╝██║╚██╔╝██║██╔══██║║
echo ║ ██║  ██║███████╗██║      ██║ ╚═╝ ██║██║  ██║║
echo ║ ╚═╝  ╚═╝╚══════╝╚═╝      ╚═╝     ╚═╝╚═╝  ╚═╝║
echo ╚══════════════════════════════════════╝%COLOR_END%
exit /b

:SHOW_PROGRESS
setlocal
for /l %%i in (1,1,3) do (
  <nul set /p "=%COLOR_SET%%COLOR_PROGRESS%...%COLOR_END%"
  ping -n 2 127.0.0.1 >nul
)
endlocal
exit /b

:SHOW_SPINNER
setlocal
set "msg=%~1"
set "cmd=%~2"
set "count=0"

echo %COLOR_SET%%COLOR_PROGRESS%⌛ %msg% %COLOR_END%
:SPIN_LOOP
for /f "tokens=1-2" %%a in ("!count! !SPINNER!") do (
  <nul set /p "=%%b "
  set "char=%%b"
)
%cmd% >nul 2>&1
if errorlevel 1 (
  <nul set /p "=%COLOR_SET%%COLOR_WARNING%✖%COLOR_END%"
  endlocal
  exit /b 1
)
ping -n 1 127.0.0.1 >nul
set /a "count=(count + 1) %% 10"
if "!char!" neq "⠏" goto SPIN_LOOP
<nul set /p "=%COLOR_SET%%COLOR_SUCCESS%✔%COLOR_END%"
endlocal
exit /b 0

:SHOW_SUCCESS
echo %COLOR_SET%%COLOR_SUCCESS%✅ %~1%COLOR_END%
exit /b

:SHOW_ERROR
echo %COLOR_SET%%COLOR_WARNING%❌ エラー: %~1%COLOR_END%
exit /b

:CHECK_PYTHON
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
  call :SHOW_ERROR "Pythonが見つかりません"
  echo 公式サイトから最新版をインストールしてください:
  echo https://www.python.org/downloads/
  pause
  exit /b 1
)
exit /b 0

:CHECK_PIP
python -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
  call :SHOW_ERROR "pipが利用できません"
  echo Pythonインストーラーで[Add python.exe to PATH]をチェックしてください
  pause
  exit /b 1
)
exit /b 0

:SETUP_UI
:: カーソル非表示（一部のターミナルで有効）
echo [ESC][?25l
exit /b