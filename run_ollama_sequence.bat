@echo off
chcp 65001 > nul
cls
title Ollama統合管理ツール

:MAIN_MENU
echo.
echo ==============================
echo  Ollama 統合管理ツール
echo ==============================
echo 1. Ollamaサーバーを起動
echo 2. チャットプログラムを実行
echo 3. 依存ライブラリをインストール
echo 4. 終了
echo ==============================
set /p choice="番号を選択してください（1-4）: "

if "%choice%"=="1" goto START_OLLAMA
if "%choice%"=="2" goto RUN_CHAT
if "%choice%"=="3" goto INSTALL_DEPS
if "%choice%"=="4" exit /b

echo.
echo [エラー] 正しい番号を入力してください（1-4）
timeout /t 2 >nul
goto MAIN_MENU

:START_OLLAMA
cls
echo Ollamaサーバーを起動しています...
echo （Ctrl+Cで終了できます）
echo ==============================
ollama serve
echo.
pause
goto MAIN_MENU

:RUN_CHAT
cls
echo チャットプログラムを起動しています...
echo ==============================
if not exist "ollama_chat.py" (
    echo [エラー] ollama_chat.pyが見つかりません
    echo スクリプトと同じディレクトリに配置してください
    pause
    goto MAIN_MENU
)
python ollama_chat.py
if %ERRORLEVEL% neq 0 (
    echo [エラー] 実行に失敗しました
    echo 1. Pythonがインストールされているか確認
    echo 2. 依存ライブラリをインストールしてください
)
echo.
pause
goto MAIN_MENU

:INSTALL_DEPS
cls
echo 必要なPythonライブラリをインストールします...
echo ==============================
echo.

:: Pythonチェック
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [エラー] Pythonがインストールされていません
    echo Python 3.11以降をインストールしてください
    pause
    goto MAIN_MENU
)

:: pipチェック
python -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [エラー] pipがインストールされていません
    echo Pythonを再インストールするかget-pip.pyでインストールしてください
    pause
    goto MAIN_MENU
)

:: インストール実行
echo aiohttpをインストール中...
python -m pip install aiohttp --user

if %ERRORLEVEL% neq 0 (
    echo [エラー] インストールに失敗しました
    echo 1. インターネット接続を確認
    echo 2. 管理者権限が必要な場合:
    echo    管理者コマンドプロンプトで再度実行してください
    pause
    goto MAIN_MENU
)

echo.
echo ==============================
echo インストールが正常に完了しました！
echo チャットプログラムを実行するにはメインメニューで2を選択
echo ==============================
pause
goto MAIN_MENU