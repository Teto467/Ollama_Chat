import os
import sys
import json
import asyncio
import aiohttp
import subprocess
import signal
import time
from datetime import datetime
from typing import Optional, List, Dict

OLLAMA_API_URL = "http://localhost:11434"
COLOR = {
    "user": "\033[34m",
    "reset": "\033[0m",
    "model": "\033[32m",
    "prompt": "\033[36m",
    "error": "\033[31m",
    "date": "\033[33m",
    "warning": "\033[33m"
}

class GoToModelSelection(Exception):
    pass

def ctrl_c_handler(signum, frame):
    raise GoToModelSelection

signal.signal(signal.SIGINT, ctrl_c_handler)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def format_iso_date(iso_str: str) -> str:
    """ISO 8601形式の日時をユーザーフレンドリーな形式に変換"""
    try:
        # UTC時間をdatetimeオブジェクトに変換（Python 3.11以降のタイムゾーン対応）
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        # ローカルタイムゾーンに変換
        local_dt = dt.astimezone()
        # 日本語フォーマット（例: 2025年01月27日 22時40分）
        return local_dt.strftime('%Y年%m月%d日 %H時%M分')
    
    except ValueError:
        # 不正な形式の場合のフォールバック処理
        cleaned = iso_str.replace('T', ' ').replace('Z', '')[:16]
        return cleaned if len(cleaned) == 16 else iso_str[:16]
    
    except Exception as e:
        print(f"{COLOR['error']}日付変換エラー: {e}{COLOR['reset']}")
        return iso_str[:16]


async def fetch_models(session: aiohttp.ClientSession) -> List[Dict]:
    try:
        async with session.get(f"{OLLAMA_API_URL}/api/tags", timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                raise aiohttp.ClientError(f"APIエラー: {response.status}")
            data = await response.json()
            return sorted(
                [{
                    "name": m["name"],
                    "installed": format_iso_date(m["modified_at"])
                } for m in data.get("models", [])],
                key=lambda x: x["installed"],
                reverse=True
            )
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"{COLOR['error']}モデル取得エラー: {type(e).__name__} - {str(e)}{COLOR['reset']}")
        return []
    except json.JSONDecodeError:
        print(f"{COLOR['error']}モデルデータの解析に失敗しました{COLOR['reset']}")
        return []

def display_model_selection(models: List[Dict]) -> None:
    print(f"\n{COLOR['prompt']}{'No.':<4} {'モデル名':<20} {'インストール日時':<19}{COLOR['reset']}")
    print(f"{COLOR['prompt']}{'─'*4} {'─'*20} {'─'*19}{COLOR['reset']}")
    
    for i, model in enumerate(models, 1):
        name_parts = model['name'].split(':')
        name = f"{name_parts[0][:15]}:{name_parts[1][:3]}" if len(name_parts) > 1 else model['name'][:18]
        print(
            f"{COLOR['prompt']}{i:<4} "
            f"{COLOR['model']}{name:<20} "
            f"{COLOR['date']}{model['installed']}{COLOR['reset']}"
        )
    
    print(f"\n{COLOR['prompt']}0: 戻る{COLOR['reset']}")

async def select_model(session: aiohttp.ClientSession) -> Optional[str]:
    try:
        models = await fetch_models(session)
        if not models:
            print(f"{COLOR['warning']}利用可能なモデルが見つかりません{COLOR['reset']}")
            return None

        display_model_selection(models)
        
        while True:
            try:
                choice = input(f"{COLOR['prompt']}選択: {COLOR['reset']}").strip()
                if choice == "0":
                    return None
                if not choice.isdigit():
                    raise ValueError("数値を入力してください")
                
                index = int(choice) - 1
                if 0 <= index < len(models):
                    return models[index]['name']
                
                print(f"{COLOR['error']}1〜{len(models)}の範囲で入力してください{COLOR['reset']}")
            
            except ValueError as e:
                print(f"{COLOR['error']}{e}{COLOR['reset']}")
            except GoToModelSelection:
                print(f"{COLOR['prompt']}操作をキャンセルしました{COLOR['reset']}")
                return None
    
    except Exception as e:
        print(f"{COLOR['error']}モデル選択エラー: {e}{COLOR['reset']}")
        return None

async def stream_response(session: aiohttp.ClientSession, model: str, messages: List[Dict]) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.7, "num_ctx": 4096}
    }
    print(f"\n{COLOR['model']}{model}: {COLOR['reset']}", end='', flush=True)
    full_response = ""
    
    try:
        async with session.post(
            f"{OLLAMA_API_URL}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            
            if resp.status != 200:
                raise aiohttp.ClientError(f"APIエラー: {resp.status}")
            
            buffer = ""
            async for chunk in resp.content:
                buffer += chunk.decode('utf-8')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            print(content, end='', flush=True)
                            full_response += content
                        except json.JSONDecodeError:
                            continue
            print("\n" + "-"*60)
            return full_response
    
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"\n{COLOR['error']}通信エラー: {type(e).__name__} - {str(e)}{COLOR['reset']}")
        return ""
    except GoToModelSelection:
        print(f"\n{COLOR['prompt']}応答生成を中断します{COLOR['reset']}")
        raise

async def chat_session(model: str) -> None:
    async with aiohttp.ClientSession() as session:
        conversation = [{"role": "system", "content": "自然な会話を心がけてください"}]
        while True:
            try:
                prompt = input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                if prompt.lower() in ("/exit", "/quit"):
                    return
                if not prompt:
                    continue
                
                conversation.append({"role": "user", "content": prompt})
                full_response = await stream_response(session, model, conversation)
                
                if full_response:
                    conversation.append({"role": "assistant", "content": full_response})

            except GoToModelSelection:
                return
            except KeyboardInterrupt:
                print(f"\n{COLOR['prompt']}セッションを終了します{COLOR['reset']}")
                return
            except Exception as e:
                print(f"\n{COLOR['error']}予期せぬエラー: {e}{COLOR['reset']}")
                return

def check_server_health() -> bool:
    try:
        result = subprocess.run(
            ["curl", "-s", f"{OLLAMA_API_URL}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False

def start_ollama_server():
    try:
        if check_server_health():
            print(f"{COLOR['prompt']}Ollamaサーバーは既に起動しています{COLOR['reset']}")
            return
        
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        for _ in range(10):
            if check_server_health():
                print(f"{COLOR['prompt']}Ollamaサーバーが起動しました{COLOR['reset']}")
                return
            time.sleep(1)
        
        print(f"{COLOR['error']}サーバー起動がタイムアウトしました{COLOR['reset']}")
    
    except FileNotFoundError:
        print(f"{COLOR['error']}Ollamaがインストールされていません{COLOR['reset']}")
    except Exception as e:
        print(f"{COLOR['error']}サーバー起動エラー: {type(e).__name__} - {str(e)}{COLOR['reset']}")

def install_dependencies():
    required = ['aiohttp']
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--user"] + required,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"{COLOR['prompt']}依存ライブラリのインストールが完了しました{COLOR['reset']}")
    except subprocess.CalledProcessError:
        print(f"{COLOR['error']}依存ライブラリのインストールに失敗しました{COLOR['reset']}")
    except Exception as e:
        print(f"{COLOR['error']}インストールエラー: {type(e).__name__} - {str(e)}{COLOR['reset']}")

async def run_ollama_and_chat():
    start_ollama_server()
    if not check_server_health():
        print(f"{COLOR['error']}サーバー起動を確認できませんでした{COLOR['reset']}")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            model = await select_model(session)
            if model:
                await chat_session(model)
    except Exception as e:
        print(f"{COLOR['error']}実行エラー: {e}{COLOR['reset']}")

async def main_menu():
    while True:
        clear_screen()
        print(f"{COLOR['prompt']}==============================")
        print(" Ollama 統合管理ツール")
        print("==============================")
        print("1. Ollamaサーバーを起動")
        print("2. チャットプログラムを実行")
        print("3. 依存ライブラリをインストール")
        print("4. サーバー起動 → チャットプログラムを実行")
        print("5. 終了")
        print(f"=============================={COLOR['reset']}")
        
        try:
            choice = input(f"{COLOR['prompt']}番号を選択してください（1-5）: {COLOR['reset']}").strip()
            
            if choice == "1":
                start_ollama_server()
                input(f"{COLOR['prompt']}Enterキーでメニューに戻ります...{COLOR['reset']}")
            elif choice == "2":
                async with aiohttp.ClientSession() as session:
                    while True:
                        model = await select_model(session)
                        if not model:
                            break
                        await chat_session(model)
            elif choice == "3":
                install_dependencies()
                input(f"{COLOR['prompt']}Enterキーでメニューに戻ります...{COLOR['reset']}")
            elif choice == "4":
                await run_ollama_and_chat()
                input(f"{COLOR['prompt']}Enterキーでメニューに戻ります...{COLOR['reset']}")
            elif choice == "5":
                print(f"{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
                return
            else:
                print(f"{COLOR['error']}1〜5の数値を入力してください{COLOR['reset']}")
                await asyncio.sleep(1)
        
        except GoToModelSelection:
            print(f"{COLOR['prompt']}操作をキャンセルしました{COLOR['reset']}")
            continue  # ループを継続
        except Exception as e:
            print(f"{COLOR['error']}予期せぬエラー: {e}{COLOR['reset']}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    import platform
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    while True:
        try:
            asyncio.run(main_menu())
        except GoToModelSelection:
            print(f"\n{COLOR['prompt']}メインメニューに戻ります{COLOR['reset']}")
        except KeyboardInterrupt:
            print(f"\n{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
            break
