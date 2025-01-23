import requests
import json
import keyboard  # 追加
from threading import Event

OLLAMA_API_URL = "http://localhost:11434"
COLOR = {
    "user": "\033[34m",
    "model": "\033[32m",
    "reset": "\033[0m"
}

def get_models():
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags")
        return [m["name"] for m in response.json().get("models", [])]
    except Exception:
        return []

def select_model(models):
    print("\n利用可能なモデル:")
    for i, model in enumerate(models):
        print(f"{i+1}. {model}")
    
    while True:
        choice = input("\nモデル番号を入力 (0で終了): ")
        if choice == "0":
            exit()
        if choice.isdigit() and 0 < int(choice) <= len(models):
            return models[int(choice)-1]
        print("無効な入力です")

def chat_session(model):
    print(f"\n{model}でチャット開始 (ESCキー押してENTER'/exit'でLLM選択に戻る)")  # 説明文更新
    exit_event = Event()
    
    def on_esc_pressed(e):
        if e.event_type == keyboard.KEY_DOWN and e.name == 'esc':
            exit_event.set()
            keyboard.unhook_all()
            print("\n")  # 改行を追加
            
    keyboard.hook(on_esc_pressed)  # ESCキー監視開始

    while not exit_event.is_set():
        try:
            prompt = input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
            if prompt == "/exit" or exit_event.is_set():
                break
            
            # APIリクエスト処理
            response = requests.post(
                f"{OLLAMA_API_URL}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                stream=True
            )
            
            print(f"{COLOR['model']}{model}: ", end="", flush=True)
            for line in response.iter_lines():
                if exit_event.is_set():
                    break
                if line:
                    chunk = json.loads(line).get("message", {}).get("content", "")
                    print(chunk, end="", flush=True)
            print(COLOR['reset'] + "\n")
            
        except Exception as e:
            print(f"エラー: {e}")
    
    keyboard.unhook_all()  # キー監視終了

def main():
    models = get_models()
    if not models:
        print("モデルが見つかりません")
        return
    
    while True:
        model = select_model(models)
        chat_session(model)
        print("\n" + "="*50)

if __name__ == "__main__":
    main()