@echo off
chcp 65001 > nul
echo 依存ライブラリをインストールします...
pip install requests pykakasi
if %errorlevel% neq 0 (
    echo エラーが発生しました。以下の点を確認してください：
    echo 1. Pythonがインストールされているか
    echo 2. pipがPATHに登録されているか
    echo 3. インターネット接続状態
    pause
    exit /b 1
)
echo インストールが正常に完了しました！
pause