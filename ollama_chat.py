import sys
import os
import ctypes
import msvcrt
import requests
import json
import gc
import psutil
import time
import concurrent.futures
from datetime import datetime
from pynvml import (
    nvmlInit,
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetMemoryInfo,
    nvmlDeviceGetName  # このインポートを追加
)

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

def monitor_resources():
    """GPU/CPUリソース監視"""
    nvmlInit()
    handle = nvmlDeviceGetHandleByIndex(0)
    gpu_info = nvmlDeviceGetMemoryInfo(handle)
    
    process = psutil.Process(os.getpid())
    cpu_usage = process.cpu_percent(interval=1)
    mem_usage = process.memory_info().rss / 1024 ** 3  # GB単位
    
    print(f" [GPU: {gpu_info.used/1024**2:.1f}MB | CPU: {cpu_usage}% | RAM: {mem_usage:.2f}GB]")


def chat_session(model):
    """非同期処理＆GPU最適化版チャットセッション"""
    response = None
    torch = None
    handle = None
    try:
        # GPUリソース初期化
        use_cuda = False
        try:
            import torch
            from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlDeviceGetName
            nvmlInit()
            if torch.cuda.is_available():
                use_cuda = True
                device = torch.device("cuda")
                torch.cuda.init()
                torch.cuda.empty_cache()
                torch.cuda.set_per_process_memory_fraction(0.9, device=0)
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.benchmark = True
                handle = nvmlDeviceGetHandleByIndex(0)
                gpu_name = nvmlDeviceGetName(handle)
                gpu_mem = nvmlDeviceGetMemoryInfo(handle)
                print(f"{COLOR['model']}CUDA有効: {gpu_name} [VRAM: {gpu_mem.free/1024**3:.1f}GB 空き]{COLOR['reset']}\n")
        except Exception as e:
            print(f"{COLOR['model']}GPU初期化エラー: {e}{COLOR['reset']}")
            use_cuda = False

        print(f"{COLOR['model_name']}{model}{COLOR['reset']} でチャット開始 (Ctrl+Cで中断)")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            while True:
                try:
                    # ユーザー入力
                    prompt = safe_input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                    if not prompt or prompt.lower() == "/exit":
                        return

                    # リクエスト設定
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": True,
                        "options": {
                            "num_gpu": 1 if use_cuda else 0,
                            "num_ctx": 4096,
                            "num_batch": 512,
                            "main_gpu": 0,
                            "low_vram": False,
                            "f16_kv": True,
                            "flash_attention": True,
                            "mmap": True,
                            "mlock": False,
                            "num_thread": 1 if use_cuda else max(1, os.cpu_count()//2)
                        }
                    }

                    # 非同期リクエスト実行
                    future = None
                    with requests.post(
                        f"{OLLAMA_API_URL}/api/chat",
                        json=payload,
                        stream=True,
                        timeout=150
                    ) as response:
                        response.raise_for_status()

                        print(f"{COLOR['model']}{model}: ", end="", flush=True)
                        buffer = bytearray()

                        # ストリーミング処理を別スレッドで実行
                        future = executor.submit(
                            process_stream,
                            response,
                            model
                        )
                        # メインスレッドでリソース監視
                        while not future.done():
                            if use_cuda:
                                gpu_info = nvmlDeviceGetMemoryInfo(handle)
                                gpu_usage = gpu_info.used / gpu_info.total
                                if gpu_usage < 0.5:
                                    torch.cuda.empty_cache()
                            time.sleep(0.05)

                        future.result()  # 完了を待機

                    # メモリクリア
                    del payload, buffer
                    if use_cuda:
                        torch.cuda.empty_cache()
                    gc.collect()
                    print(COLOR['reset'] + "\n")

                except KeyboardInterrupt:
                    print(COLOR['reset'] + "\n入力を中断しました")
                    if future: future.cancel()
                    break
                except requests.exceptions.RequestException as e:
                    print(f"\n通信エラー: {e}")
                    if future: future.cancel()

    except Exception as e:
        print(f"\n予期せぬエラー: {e}")
    finally:
        # リソース完全解放
        if response:
            response.close()
        if torch is not None and use_cuda:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        print(COLOR['reset'] + "セッションを終了します\n" + "="*60)



def process_stream(response, model):
    """非同期ストリーミング処理（バッファ管理修正版）"""
    buffer = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                buffer.extend(chunk)
                while b'\n' in buffer:
                    line, _, buffer = buffer.partition(b'\n')
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        print(content, end="", flush=True)
                        del data
                        if len(content) % 50 == 0:
                            gc.collect(1)
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"\nストリーミングエラー: {e}")
    return buffer

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