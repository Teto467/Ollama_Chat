@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ■ Ollamaクライアントセットアップ for Windows ■
echo.

:: Pythonチェック
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo エラー: Pythonがインストールされていません
    echo 公式サイトからPython 3.8以上をインストールしてください
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 必要ライブラリ一括インストール
echo 必要なライブラリをインストールします...
echo.

python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo エラー: pipの更新に失敗しました
    pause
    exit /b 1
)

pip install requests==2.32.3 colorama==0.4.6
if %errorlevel% neq 0 (
    echo エラー: ライブラリのインストールに失敗しました
    pause
    exit /b 1
)

:: 完了チェック
echo.
echo インストール済みパッケージ確認:
pip list | findstr "requests colorama"

echo.
echo ■ セットアップ完了 ■
echo 以下のコマンドでプログラムを起動できます：
echo   python ollama_client.py
pause