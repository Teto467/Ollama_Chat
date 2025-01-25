@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: Pythonチェック
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Pythonがインストールされていません
    echo https://www.python.org/downloads/ からPython 3.8以上をインストールしてください
    pause
    exit /b 1
)

:: 必要ライブラリ一括インストール
echo 依存ライブラリをインストール中...
pip install ^
    torch==2.3.1+cu121 --extra-index-url https://download.pytorch.org/whl/cu121 ^
    requests==2.32.3 ^
    pynvml==11.5.0 ^
    psutil==5.9.8 ^
    colorama==0.4.6

if %errorlevel% neq 0 (
    echo インストール中にエラーが発生しました
    pause
    exit /b 1
)

:: Ollamaサービスチェック
echo Ollamaの最新版を確認...
curl --fail http://localhost:11434 >nul 2>&1
if %errorlevel% neq 0 (
    echo Ollamaが実行されていません
    echo 最新版をインストールしてください: https://ollama.com/download
    pause
)

:: 完了メッセージ
echo -------------------------------
echo インストールが完了しました
echo プログラムを起動するには以下を実行：
echo python ollama_chat.py
pause