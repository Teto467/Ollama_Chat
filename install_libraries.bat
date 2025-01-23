@echo off
chcp 65001 > nul
echo 必要なライブラリをインストールします...
echo （管理者権限が必要な場合があります）

python -m pip install --upgrade pip
pip install requests keyboard

echo インストール完了！
pause