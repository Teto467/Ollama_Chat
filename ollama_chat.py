import sys
import os
import ctypes
import msvcrt
import requests
import json
import gc
import psutil
import time
from typing import Optional
import concurrent.futures
from datetime import datetime
from itertools import cycle
import signal
from ctypes import wintypes
from tenacity import retry, stop_after_attempt, wait_exponential
from pynvml import (
    nvmlInit,
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetMemoryInfo,
    nvmlDeviceGetName  # このインポートを追加
)

# Windows API定義
kernel32 = ctypes.windll.kernel32

# プログレス表示用
SPINNER = cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])

# コンソール設定
kernel32.SetConsoleCP(65001)
kernel32.SetConsoleOutputCP(65001)

OLLAMA_API_URL = "http://localhost:11434"
COLOR = {
    "user": "\033[34m",  # 青
    "reset": "\033[0m",  # リセット
    "model": "\033[32m",  # 緑
    "number": "\033[33m",  # 黄
    "model_name": "\033[36m",  # シアン
    "date": "\033[35m",  # マゼンタ
    "white": "\033[37m",  # 白 ← ここにカンマを追加
    "divider": "\033[90m",  # 明るいグレー
    "highlight": "\033[1;36m"  # シアン＋太字
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

def preload_model(model_name):
    """モデルをバックグラウンドでプリロード"""
    global current_preload_model
    try:
        current_preload_model = model_name
        # 実際のモデルロード処理（仮の実装）
        response = requests.post(
            f"{OLLAMA_API_URL}/api/load",
            json={"model": model_name, "keep_alive": "5m"}
        )
        response.raise_for_status()
        print(f"\n{COLOR['divider']}[✓] {model_name} プリロード完了{COLOR['reset']}")
    except Exception as e:
        print(f"\n{COLOR['divider']}[!] プリロード失敗: {e}{COLOR['reset']}")
    finally:
        current_preload_model = None


def select_model(models):
    """モデル選択インタフェース（Windows最適化版）"""
    # ヘッダー作成
    header = (
        f"{COLOR['divider']}┌{'─'*5}┬{'─'*25}┬{'─'*19}┐{COLOR['reset']}\n"
        f"{COLOR['number']}  No. {COLOR['divider']}│{COLOR['model_name']} モデル名{' '*18} "
        f"{COLOR['divider']}│{COLOR['date']} 更新日時{' '*11} {COLOR['divider']}│{COLOR['reset']}"
    )
    
    # ボディ作成
    body = []
    for i, model in enumerate(models):
        time_str = model["modified"].strftime('%Y-%m-%d %H:%M')
        body_line = (
            f"{COLOR['divider']}├{'─'*5}┼{'─'*25}┼{'─'*19}┤{COLOR['reset']}\n"
            f"{COLOR['number']}{i+1:>4}  {COLOR['divider']}│ "
            f"{COLOR['model_name']}{model['name'][:23]:<23} {COLOR['divider']}│ "
            f"{COLOR['date']}{time_str} {COLOR['divider']}│"
        )
        body.append(body_line)
    
    # フッター作成
    footer = f"{COLOR['divider']}└{'─'*5}┴{'─'*25}┴{'─'*19}┘{COLOR['reset']}"
    
    # 全体表示
    print(f"\n{header}\n" + "\n".join(body) + f"\n{footer}")
    
    # 入力処理
    while True:
        choice = safe_input(
            f"\n{COLOR['highlight']}🡢 {COLOR['white']}モデル{COLOR['number']}No.{COLOR['white']}を入力"
            f"{COLOR['divider']} [0:終了] {COLOR['reset']}"
        ).strip()
        
        if choice in ("0", "/exit"):
            print(f"{COLOR['divider']}―――――――――――――――――――――――――――――――{COLOR['reset']}")
            print("プログラムを終了します")
            exit()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice)-1]["name"]
        
        print(
            f"{COLOR['divider']}[!] {COLOR['number']}1〜{len(models)}の数値で入力してください"
            f"{COLOR['reset']}"
        )

def safe_input(prompt):
    """Windows向け強化版入力処理（シグナル対応）"""
    h_input = kernel32.GetStdHandle(-10)
    original_mode = wintypes.DWORD()
    kernel32.GetConsoleMode(h_input, ctypes.byref(original_mode))
    
    # シグナルハンドラを保存
    original_sigint = signal.getsignal(signal.SIGINT)
    buf = ctypes.create_unicode_buffer(256)
    received_signal = [False]

    def handler(signum, frame):
        received_signal[0] = True
        print("\n中断信号を検知")

    try:
        # シグナルハンドラ設定
        signal.signal(signal.SIGINT, handler)
        
        # コンソールモード設定
        new_mode = original_mode.value | 0x0002 | 0x0004 | 0x0001  # ENABLE flags
        kernel32.SetConsoleMode(h_input, new_mode)
        
        print(prompt, end='', flush=True)
        chars_read = wintypes.DWORD()
        
        # 入力を非同期で監視
        while not received_signal[0]:
            if kernel32.WaitForSingleObject(h_input, 100) == 0:
                if kernel32.ReadConsoleW(h_input, buf, len(buf)-1, ctypes.byref(chars_read), None):
                    return buf.value[:chars_read.value].strip()
                break
        return ""
    
    finally:
        # クリーンアップ処理
        kernel32.SetConsoleMode(h_input, original_mode)
        signal.signal(signal.SIGINT, original_sigint)
        while msvcrt.kbhit():
            msvcrt.getwch()
        if received_signal[0]:
            raise KeyboardInterrupt("入力がユーザーにより中断されました")

def monitor_resources():
    """GPU/CPUリソース監視"""
    nvmlInit()
    handle = nvmlDeviceGetHandleByIndex(0)
    gpu_info = nvmlDeviceGetMemoryInfo(handle)
    
    process = psutil.Process(os.getpid())
    cpu_usage = process.cpu_percent(interval=1)
    mem_usage = process.memory_info().rss / 1024 ** 3  # GB単位
    
    print(f" [GPU: {gpu_info.used/1024**2:.1f}MB | CPU: {cpu_usage}% | RAM: {mem_usage:.2f}GB]")


def initialize_gpu_resources() -> dict:
    """GPUリソースの初期化と設定を管理"""
    gpu_context = {
        'use_cuda': False,
        'torch': None,
        'handle': None
    }
    
    try:
        import torch
        from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetName, nvmlDeviceGetMemoryInfo
        
        nvmlInit()
        if torch.cuda.is_available():
            device = torch.device("cuda")
            torch.cuda.init()
            
            # CUDA最適化設定
            torch.cuda.set_per_process_memory_fraction(0.9, device=0)
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.enable_flash_sdp(True)
            torch.backends.cuda.enable_mem_efficient_sdp(True)
            
            # GPUメモリ情報取得
            handle = nvmlDeviceGetHandleByIndex(0)
            gpu_name = nvmlDeviceGetName(handle)
            gpu_mem = nvmlDeviceGetMemoryInfo(handle)
            
            print(f"{COLOR['divider']}―――――――――――――――――――――――――――――――{COLOR['reset']}")
            print(f"{COLOR['model']}⚡ CUDA有効: {gpu_name} [VRAM: {gpu_mem.free/1024**3:.1f}GB 空き]{COLOR['reset']}")
            os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"
            
            gpu_context.update({
                'use_cuda': True,
                'torch': torch,
                'handle': handle
            })
            
    except Exception as e:
        print(f"{COLOR['divider']}―――――――――――――――――――――――――――――――")
        print(f"{COLOR['model']}⚠ GPU初期化エラー: {e}{COLOR['reset']}")
    
    return gpu_context

def set_high_process_priority():
    """Windowsプロセスの優先度を設定"""
    kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00000080)

def create_request_payload(model: str, prompt: str, use_cuda: bool) -> dict:
    """リクエストペイロードを生成"""
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": {
            "num_ctx": 4096,
            "num_thread": 8 if use_cuda else os.cpu_count(),
            "num_batch": 512,
            "flash_attention": True
        }
    }

def handle_chat_response(response: requests.Response, model: str, executor: concurrent.futures.Executor, gpu_context: dict):
    """レスポンス処理と非同期タスク管理"""
    future = None
    try:
        print(f"{COLOR['model']}{model}: ", end="", flush=True)
        future = executor.submit(process_stream, response, model)
        
        while not future.done():
            if gpu_context['use_cuda']:
                kernel32.SetProcessWorkingSetSize(-1, 1024*1024*1024, -1)
                gpu_context['torch'].cuda.empty_cache()
            time.sleep(0.05)
            
        future.result()
        print(f"\n{COLOR['divider']}―――――――――――――――――――――――――――――――")
        
    finally:
        if future:
            future.cancel()

def run_chat_loop(model: str, gpu_context: dict):
    """チャットセッションのメインループ"""
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix='OllamaStream'
    ) as executor:
        while True:
            try:
                prompt = safe_input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                if not prompt or prompt.lower() == "/exit":
                    return

                payload = create_request_payload(model, prompt, gpu_context['use_cuda'])
                
                with requests.post(
                    f"{OLLAMA_API_URL}/api/chat",
                    json=payload,
                    stream=True,
                    timeout=150
                ) as response:
                    response.raise_for_status()
                    handle_chat_response(response, model, executor, gpu_context)
                
                if gpu_context['use_cuda']:
                    gpu_context['torch'].cuda.empty_cache()
                gc.collect()
                
            except KeyboardInterrupt:
                print(f"{COLOR['divider']}―――――――――――――――――――――――――――――――")
                print(f"{COLOR['reset']}\n入力を中断しました")
                break
            except requests.exceptions.RequestException as e:
                print(f"\n{COLOR['divider']}―――――――――――――――――――――――――――――――")
                print(f"通信エラー: {e}")

def cleanup_resources(response: Optional[requests.Response], gpu_context: dict):
    """リソースのクリーンアップ処理"""
    if response:
        response.close()
    if gpu_context['torch'] is not None and gpu_context['use_cuda']:
        gpu_context['torch'].cuda.synchronize()
        gpu_context['torch'].cuda.empty_cache()
        gpu_context['torch'].cuda.reset_peak_memory_stats()
    kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00000020)

def chat_session(model: str):
    """分割後のメイン関数"""
    response = None
    gpu_context = initialize_gpu_resources()
    
    try:
        set_high_process_priority()
        print(f"\n{COLOR['divider']}―――――――――――――――――――――――――――――――")
        print(f"{COLOR['model_name']} チャット開始: {model}{COLOR['reset']}")
        print(f"{COLOR['divider']}―――――――――――――――――――――――――――――――{COLOR['reset']}\n")
        
        run_chat_loop(model, gpu_context)
        
    except Exception as e:
        print(f"\n{COLOR['divider']}―――――――――――――――――――――――――――――――")
        print(f"予期せぬエラー: {e}")
    finally:
        cleanup_resources(response, gpu_context)
        print(f"{COLOR['divider']}―――――――――――――――――――――――――――――――")
        print(f"{COLOR['reset']}セッションを終了します\n" + "="*60)


def process_stream(response, model):
    """未加工のストリーミング出力処理"""
    buffer = bytearray()
    token_count = 0
    start_time = time.perf_counter()
    
    try:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                buffer.extend(chunk)
                while b'\n' in buffer:
                    line, _, buffer = buffer.partition(b'\n')
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        # 未加工のコンテンツをそのまま出力
                        print(content, end="", flush=True)
                        token_count += len(content.split())
                            
                    except json.JSONDecodeError:
                        continue
                    
        elapsed = time.perf_counter() - start_time
        tps = token_count / elapsed if elapsed > 0 else 0
        print(f"\n{COLOR['divider']}―――――――――――――――――――――――――――――――")
        print(f"{COLOR['number']}⚡ 処理速度: {tps:.1f} tokens/sec")
        
    except Exception as e:
        print(f"\nストリーミングエラー: {e}")
        raise
    
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