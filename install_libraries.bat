@echo off
chcp 65001 > nul
REM Ollamaチャットクライアント用依存関係インストールスクリプト
echo Ollamaクライアントセットアップを開始します...

REM Pythonのバージョンチェック
python --version 3>nul
if errorlevel 1 (
    echo Pythonがインストールされていません
    echo https://www.python.org/downloads/ からPython 3.7以降をインストールしてください
    pause
    exit /b 1
)

REM 必要なパッケージのインストール
echo 依存ライブラリをインストールします...
pip install --upgrade pip
pip install aiohttp colorama

if errorlevel 1 (
    echo インストール中にエラーが発生しました
    pause
    exit /b 1
)

REM Ollamaの実行確認
echo.
echo 注意: Ollamaが実行されていることを確認してください
echo 1. Ollamaの公式サイトからインストール
echo 2. 別のコマンドプロンプトで以下を実行:
echo    ollama serve
echo.

echo セットアップが完了しました
pause