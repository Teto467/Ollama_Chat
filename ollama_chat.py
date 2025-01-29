import os
import sys
import json
import asyncio
import aiohttp
import subprocess
import signal
import time
import unicodedata
from datetime import datetime
from typing import Optional

OLLAMA_API_URL = "http://localhost:11434"
COLOR = {
    "user": "\033[34m",
    "reset": "\033[0m",
    "model": "\033[32m",
    "prompt": "\033[36m",
    "error": "\033[31m",
    "date": "\033[33m"
}

class GoToModelSelection(Exception):
    pass

def ctrl_c_handler(signum, frame):
    raise GoToModelSelection

signal.signal(signal.SIGINT, ctrl_c_handler)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def format_iso_date(iso_str: str) -> str:
    try:
        utc_time = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        local_time = utc_time.astimezone()
        return local_time.strftime('%Y-%m-%d %H:%M')
    except ValueError:
        cleaned = iso_str.replace('T', ' ')[:16]
        return cleaned if len(cleaned) == 16 else iso_str[:16]
    except Exception as e:
        print(f"{COLOR['error']}日付変換エラー: {e}{COLOR['reset']}")
        return iso_str[:16]

async def fetch_models(session: aiohttp.ClientSession) -> list:
    try:
        async with session.get(f"{OLLAMA_API_URL}/api/tags") as response:
            data = await response.json()
            return sorted(
                [
                    {
                        "name": m["name"],
                        "installed": format_iso_date(m["modified_at"])
                    }
                    for m in data.get("models", [])
                ],
                key=lambda x: x["installed"],
                reverse=True
            )
    except Exception as e:
        print(f"{COLOR['error']}モデル取得エラー: {e}{COLOR['reset']}")
        return []

def display_model_selection(models: list) -> None:
    print(f"\n{COLOR['prompt']}{'No.':<4} {'モデル名':<20} {'インストール日時':<19}{COLOR['reset']}")
    print(f"{COLOR['prompt']}{'─'*4} {'─'*20} {'─'*19}{COLOR['reset']}")
    
    for i, model in enumerate(models, 1):
        name_parts = model["name"].split(":")
        name = f"{name_parts[0][:15]}:{name_parts[1][:3]}" if len(name_parts) > 1 else model["name"][:18]
        print(
            f"{COLOR['prompt']}{i:<4} "
            f"{COLOR['model']}{name:<20} "
            f"{COLOR['date']}{model['installed']}{COLOR['reset']}"
        )
    
    print(f"\n{COLOR['prompt']}0: 戻る{COLOR['reset']}")

def normalize_input_number(prompt: str) -> str:
    while True:
        try:
            raw = input(prompt).strip()
            # 全角を半角へ正規化し、その後で数字かどうかを判定
            normalized = unicodedata.normalize('NFKC', raw)
            if normalized.isdigit():
                return normalized
            print(f"{COLOR['error']}数字で入力してください{COLOR['reset']}")
        except GoToModelSelection:
            # Ctrl+Cでモデル選択へ戻したい場合など
            raise

async def select_model(session: aiohttp.ClientSession) -> Optional[str]:
    models = await fetch_models(session)
    if not models:
        return None

    display_model_selection(models)
    
    while True:
        try:
            choice = normalize_input_number(f"{COLOR['prompt']}選択: {COLOR['reset']}")
            # 0以外はモデル名として返す
            if choice == "0":
                return None
            num_choice = int(choice)
            if 1 <= num_choice <= len(models):
                return models[num_choice - 1]["name"]
            print(f"{COLOR['error']}1〜{len(models)}の範囲内で入力してください{COLOR['reset']}")
        except GoToModelSelection:
            print(f"{COLOR['prompt']}Ctrl+Cが押されました。再度モデルを選択できます。{COLOR['reset']}")
            return None

async def stream_response(session: aiohttp.ClientSession, model: str, messages: list) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.7, "num_ctx": 4096}
    }
    print(f"\n{COLOR['model']}{model}: {COLOR['reset']}", end='', flush=True)
    full_response = ""
    
    try:
        async with session.post(f"{OLLAMA_API_URL}/api/chat", json=payload) as resp:
            buffer = ""
            async for chunk in resp.content:
                buffer += chunk.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data["message"]["content"]
                            print(content, end="", flush=True)
                            full_response += content
                        except (json.JSONDecodeError, KeyError):
                            continue
            print("\n" + "-"*60)
            return full_response
    except aiohttp.ClientError as e:
        print(f"\n{COLOR['error']}Network Error: {type(e).__name__}{COLOR['reset']}")
        return ""
    except GoToModelSelection:
        raise

async def chat_session(model: str) -> None:
    async with aiohttp.ClientSession() as session:
        conversation = [{"role": "system", "content": "自然な会話を心がけてください"}]
        while True:
            try:
                prompt = input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                if prompt.lower() == "/exit":
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

def start_ollama_server():
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{COLOR['prompt']}Ollamaサーバーを起動しています...{COLOR['reset']}")
    except FileNotFoundError:
        print(f"{COLOR['error']}Ollamaがインストールされていないか、パスが通っていません。{COLOR['reset']}")
    except Exception as e:
        print(f"{COLOR['error']}Ollamaサーバーの起動に失敗しました: {e}{COLOR['reset']}")

def install_dependencies():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
        print(f"{COLOR['prompt']}依存ライブラリのインストールが完了しました。{COLOR['reset']}")
    except subprocess.CalledProcessError:
        print(f"{COLOR['error']}依存ライブラリのインストールに失敗しました。{COLOR['reset']}")

async def run_ollama_and_chat():
    start_ollama_server()
    time.sleep(0.5)
    async with aiohttp.ClientSession() as session:
        print(f"{COLOR['prompt']}モデルを選択してください{COLOR['reset']}")
        model = await select_model(session)
        if model:
            await chat_session(model)


async def main_menu():
    while True:
        try:
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
            
            in_choice = normalize_input_number(f"{COLOR['prompt']}番号を選択してください（1-5）: {COLOR['reset']}")
            choice = int(in_choice)
            
            if choice == 1:
                start_ollama_server()
                input(f"{COLOR['prompt']}Enterキーを押してメインメニューに戻ります...{COLOR['reset']}")
            elif choice == 2:
                async with aiohttp.ClientSession() as session:
                    while True:
                        model = await select_model(session)
                        if not model:
                            break
                        await chat_session(model)
            elif choice == 3:
                install_dependencies()
                input(f"{COLOR['prompt']}Enterキーを押してメインメニューに戻ります...{COLOR['reset']}")
            elif choice == 4:
                await run_ollama_and_chat()
                input(f"{COLOR['prompt']}Enterキーを押してメインメニューに戻ります...{COLOR['reset']}")
            elif choice == 5:
                print(f"{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
                return
            else:
                print(f"{COLOR['error']}正しい番号を入力してください（1-5）{COLOR['reset']}")
                await asyncio.sleep(2)
                
        except GoToModelSelection:
            print(f"{COLOR['prompt']}Ctrl+Cが押されました。メインメニューに戻ります。{COLOR['reset']}")
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
            return
        except Exception as e:
            print(f"{COLOR['error']}予期せぬエラーが発生しました: {e}{COLOR['reset']}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        print(f"\n{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
