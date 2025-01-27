import os
import sys
import json
import asyncio
import aiohttp
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
                [{
                    "name": m["name"],
                    "installed": format_iso_date(m["modified_at"])
                } for m in data.get("models", [])],
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
        name_parts = model['name'].split(':')
        name = f"{name_parts[0][:15]}:{name_parts[1][:3]}" if len(name_parts) > 1 else model['name'][:18]
        print(
            f"{COLOR['prompt']}{i:<4} "
            f"{COLOR['model']}{name:<20} "
            f"{COLOR['date']}{model['installed']}{COLOR['reset']}"
        )
    
    print(f"\n{COLOR['prompt']}0: 終了{COLOR['reset']}")

async def select_model(session: aiohttp.ClientSession) -> Optional[str]:
    models = await fetch_models(session)
    if not models:
        return None

    display_model_selection(models)
    
    while True:
        try:
            choice = input(f"{COLOR['prompt']}選択: {COLOR['reset']}").strip()
            if choice == "0":
                return None
            if choice.isdigit() and 1 <= int(choice) <= len(models):
                return models[int(choice)-1]['name']
            print(f"{COLOR['error']}1〜{len(models)}の数値で入力してください{COLOR['reset']}")
        except KeyboardInterrupt:
            return None

async def stream_response(session: aiohttp.ClientSession, messages: list) -> None:
    """会話履歴を丸ごと送信し、ストリーミングレスポンスを受け取る"""
    if not messages:
        return

    # 最後に送ったユーザーの入力からモデル名を取得
    model = messages[-1]["model"]
    payload = {
        "model": model,
        "messages": [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in messages if msg["role"] in ["system", "user", "assistant"]
        ],
        "stream": True
    }

    print(f"\n{COLOR['model']}{model}: {COLOR['reset']}", end="", flush=True)

    try:
        async with session.post(
            f"{OLLAMA_API_URL}/api/chat",
            json=payload,
            timeout=300
        ) as response:
            buffer = ""
            assistant_text = ""
            async for chunk in response.content:
                if chunk:
                    buffer += chunk.decode()
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line.strip():
                            try:
                                data = json.loads(line)
                                content = data["message"]["content"]
                                print(content, end="", flush=True)
                                assistant_text += content
                            except json.JSONDecodeError:
                                continue
            # レスポンスを"assistant"として履歴に追加
            messages.append({"role": "assistant", "content": assistant_text, "model": model})

        print("\n" + "-"*60)
        
    except asyncio.TimeoutError:
        print(f"\n{COLOR['error']}タイムアウトが発生しました{COLOR['reset']}")
    except Exception as e:
        print(f"\n{COLOR['error']}エラー: {e}{COLOR['reset']}")

async def chat_session(model: str) -> None:
    async with aiohttp.ClientSession() as session:
        # システムプロンプトや会話履歴を保持するリスト
        # 必要があれば最初にシステムプロンプトを追加してもよい
        messages = []

        while True:
            try:
                prompt = input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                if prompt.lower() == "/exit":
                    return
                if prompt:
                    # ユーザーの入力を会話履歴に追加
                    messages.append({"role": "user", "content": prompt, "model": model})
                    await stream_response(session, messages)
            except KeyboardInterrupt:
                print(f"\n{COLOR['prompt']}セッションを終了します{COLOR['reset']}")
                return

async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            selected_model = await select_model(session)
            if not selected_model:
                print(f"{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
                return
            await chat_session(selected_model)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
