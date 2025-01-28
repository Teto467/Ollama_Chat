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
    """ISO 8601日時をローカル時刻でフォーマット（改善版）"""
    try:
        # タイムゾーン情報を考慮したパース
        utc_time = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        local_time = utc_time.astimezone()
        return local_time.strftime('%Y-%m-%d %H:%M')  # 秒を削除
    except ValueError:
        # フォールバック処理：オリジナルからTをスペースに置換し秒を削除
        cleaned = iso_str.replace('T', ' ')[:16]
        return cleaned if len(cleaned) == 16 else iso_str[:16]
    except Exception as e:
        print(f"{COLOR['error']}日付変換エラー: {e}{COLOR['reset']}")
        return iso_str[:16]  # 最低限のフォーマット整形

async def fetch_models(session: aiohttp.ClientSession) -> list:
    """モデルリストとインストール日時を取得"""
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
    """モデル選択画面（日付表示追加）"""
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
    """モデル選択処理（変更なし）"""
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

async def stream_response(session: aiohttp.ClientSession, model: str, messages: list) -> str:
    """ストリーミング処理+履歴管理対応版"""
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
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data["message"]["content"]
                            print(content, end='', flush=True)
                            full_response += content  # 完全なレスポンスを蓄積
                        except (json.JSONDecodeError, KeyError):
                            continue
            print("\n" + "-"*60)
            return full_response  # 完全なレスポンスを返却
            
    except aiohttp.ClientError as e:
        print(f"\n{COLOR['error']}Network Error: {type(e).__name__}{COLOR['reset']}")
        return ""

    print(f"\n{COLOR['model']}{model}: {COLOR['reset']}", end="", flush=True)
    
    try:
        async with session.post(
            f"{OLLAMA_API_URL}/api/chat",
            json=payload,
            timeout=300
        ) as response:
            buffer = ""
            async for chunk in response.content:
                if chunk:
                    buffer += chunk.decode()
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line.strip():
                            try:
                                data = json.loads(line)
                                print(data["message"]["content"], end="", flush=True)
                            except json.JSONDecodeError:
                                continue
        print("\n" + "-"*60)
        
    except asyncio.TimeoutError:
        print(f"\n{COLOR['error']}タイムアウトが発生しました{COLOR['reset']}")
    except Exception as e:
        print(f"\n{COLOR['error']}エラー: {e}{COLOR['reset']}")

async def chat_session(model: str) -> None:
    """メモリ保持機能追加版"""
    async with aiohttp.ClientSession() as session:
        conversation = [{"role": "system", "content": "自然な会話を心がけてください"}]  # メモリ保持用
        while True:
            try:
                prompt = input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                if prompt.lower() == "/exit":
                    return
                if not prompt:
                    continue
                
                # ユーザーメッセージを履歴に追加
                conversation.append({"role": "user", "content": prompt})
                
                # ストリーミング応答処理
                full_response = await stream_response(session, model, conversation)
                
                # アシスタントメッセージを履歴に追加
                if full_response:
                    conversation.append({"role": "assistant", "content": full_response})

            except KeyboardInterrupt:
                print(f"\n{COLOR['prompt']}セッションを終了します{COLOR['reset']}")
                return

async def main():
    """非同期メイン処理"""
    async with aiohttp.ClientSession() as session:
        while True:
            model = await select_model(session)
            if not model:
                print(f"{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")
                return
            await chat_session(model)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{COLOR['prompt']}プログラムを終了します{COLOR['reset']}")