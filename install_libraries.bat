@echo off
chcp 65001 > nul
echo 必要なライブラリをインストールします...
echo.

:: 基本ライブラリ
python -m pip install --upgrade pip
python -m pip install requests psutil tenacity pynvml

:: PyTorch (CUDA 12.1版)
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: Windows用追加依存
python -m pip install pywin32 ctypes-samples

echo.
echo インストール完了！エラーがなければ準備完了です。
pause