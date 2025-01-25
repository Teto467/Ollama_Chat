import sys
import os
import ctypes
import msvcrt
import requests
import json
from datetime import datetime

# Windows API定義
kernel32 = ctypes.windll.kernel32

# コンソール設定
kernel32.SetConsoleCP(65001)
kernel32.SetConsoleOutputCP(65001)

OLLAMA_API_URL = "http://localhost:11434"
COLOR = {
"user": "\033[34m", # 青
"reset": "\033[0m", # リセット
"model": "\033[32m", # 緑
"number": "\033[33m", # 黄
"model_name": "\033[36m", # シアン
"date": "\033[35m", # マゼンタ
"white": "\033[37m" # 白
}

class TIME_ZONE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Bias", ctypes.c_long),
        ("StandardName", ctypes.c_wchar * 32),  # c_wcharに修正
        ("StandardDate", ctypes.c_byte * 16),
        ("StandardBias", ctypes.c_long),
        ("DaylightName", ctypes.c_wchar * 32),  # c_wcharに修正
        ("DaylightDate", ctypes.c_byte * 16),
        ("DaylightBias", ctypes.c_long),
    ]

def clear_input_buffer():
    """Windows専用入力バッファクリア"""
    try:
        while msvcrt.kbhit():
            msvcrt.getch()
    except Exception as e:
        print(f"入力バッファクリアエラー: {e}")

def get_local_timezone():
    """Windowsのタイムゾーン情報を正確に取得"""
    tzi = TIME_ZONE_INFORMATION()
    if kernel32.GetTimeZoneInformation(ctypes.byref(tzi)) != 0xFFFFFFFF:
        return datetime.now().astimezone().tzinfo
    return datetime.utcnow().astimezone().tzinfo

def convert_to_local_time(utc_time):
    """UTC時刻をローカル時刻に変換"""
    try:
        return utc_time.astimezone(get_local_timezone())
    except Exception as e:
        print(f"時刻変換エラー: {e}")
        return utc_time

def get_models():
    """モデル情報取得（時刻フォーマット修正版）"""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=15)
        response.raise_for_status()
        
        models = []
        for m in response.json().get("models", []):
            try:
                # タイムスタンプのマイクロ秒を6桁に正規化
                raw_time = m["modified_at"].rstrip('Z').replace('Z', '')
                if '.' in raw_time:
                    main_part, fractional = raw_time.split('.')
                    fractional = fractional.split('+')[0][:6]  # 最大6桁に制限
                    tz_part = raw_time.split('+')[-1] if '+' in raw_time else ''
                    raw_time = f"{main_part}.{fractional}+{tz_part}" if tz_part else f"{main_part}.{fractional}"
                
                utc_time = datetime.fromisoformat(raw_time)
                models.append({
                    "name": m["name"],
                    "modified": convert_to_local_time(utc_time)
                })
            except Exception as e:
                print(f"モデル {m['name']} の時刻解析に失敗: {e}")
        
        return sorted(models, key=lambda x: x["modified"], reverse=True)
    except requests.exceptions.RequestException as e:
        print(f"モデル取得エラー: {e}")
        return []

def select_model(models):
    """モデル選択インタフェース（Windows最適化版）"""
    print(f"\n{COLOR['number']}番号 {COLOR['model_name']}モデル名 {COLOR['date']}                 ダウンロード日時{COLOR['reset']}")  # 変更箇所
    
    for i, model in enumerate(models):
        time_str = model["modified"].strftime('%Y-%m-%d %H:%M')  # タイムゾーン名削除
        print(
            f"{COLOR['number']}{i+1:2d}. "
            f" {COLOR['model_name']}{model['name'][:25]:<25} "
            f"{COLOR['date']}{time_str}{COLOR['reset']}"
        )
    
    while True:
        choice = safe_input(f"\n{COLOR['white']}モデル{COLOR['number']}番号{COLOR['white']}を入力 (0で終了): ").strip()
        if choice in ("0", "/exit"):
            print("プログラムを終了します")
            exit()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice)-1]["name"]
        print("無効な入力です")

def safe_input(prompt):
    """Windowsコンソール向け入力処理"""
    for _ in range(3):
        try:
            clear_input_buffer()
            return input(prompt)
        except UnicodeDecodeError:
            print("文字化けを検出しました。再入力してください。")
        except EOFError:
            print("\n入力が中断されました")
            return "/exit"
    return ""

def chat_session(model):
    """チャットセッション管理（Windows最適化版）"""
    response = None
    try:
        print(f"\n{COLOR['model_name']}{model}{COLOR['reset']} でチャット開始 (Ctrl+Cで中断)")
        while True:
            try:
                prompt = safe_input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                if not prompt:
                    continue
                if prompt.lower() == "/exit":
                    return

                response = requests.post(
                    f"{OLLAMA_API_URL}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": True
                    },
                    stream=True,
                    timeout=75
                )
                response.raise_for_status()

                print(f"{COLOR['model']}{model}: ", end="", flush=True)
                for chunk in response.iter_content(chunk_size=1024):
                    try:
                        data = json.loads(chunk.decode())
                        content = data.get("message", {}).get("content", "")
                        print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        continue
                print(COLOR['reset'] + "\n")

            except KeyboardInterrupt:
                print(COLOR['reset'] + "\n入力を中断しました")
                break
            except requests.exceptions.RequestException as e:
                print(f"\n通信エラー: {e}")

    finally:
        if response:
            response.close()
        print(COLOR['reset'] + "セッションを終了します\n" + "="*60)

def main():
    """メイン処理（Windows専用版）"""
    try:
        while True:
            models = get_models()
            if not models:
                print("利用可能なモデルが見つかりません")
                if input("再試行しますか？ (y/n): ").lower() != 'y':
                    return
                continue
            
            try:
                model = select_model(models)
                chat_session(model)
            except KeyboardInterrupt:
                print("\nモデル選択に戻ります")
    except KeyboardInterrupt:
        print("\nプログラムを終了します")

if __name__ == "__main__":
    main()