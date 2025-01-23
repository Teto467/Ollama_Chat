import sys
import requests
import json
from threading import Event

# Windows向けエンコーディング設定
if sys.platform == "win32":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleCP(65001)
    kernel32.SetConsoleOutputCP(65001)

OLLAMA_API_URL = "http://localhost:11434"
COLOR = {
    "user": "\033[34m",
    "reset": "\033[0m",
    "model": "\033[32m"
}

def clear_input_buffer():
    """プラットフォーム別入力バッファクリア"""
    try:
        if sys.platform == "win32":
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
        else:
            import termios
            import tty
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while sys.stdin.read(1) == '': pass
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        pass

def safe_input(prompt):
    """安全な入力処理（EOF/エンコーディング対応）"""
    for _ in range(3):
        try:
            clear_input_buffer()
            if sys.stdin.encoding.lower() in ('cp932', 'shift_jis', 'mbcs'):
                return input(prompt).encode(sys.stdin.encoding, errors='replace').decode('utf-8')
            return input(prompt)
        except UnicodeDecodeError:
            print("文字化けを検出しました。再入力してください。")
        except EOFError:
            print("\n入力が中断されました")
            return "/exit"
    return ""

def get_models():
    """利用可能なモデル一覧を取得"""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=10)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"モデル取得エラー: {e}")
        return []

def select_model(models):
    """モデル選択インタフェース"""
    print("\n利用可能なモデル:")
    for i, model in enumerate(models):
        print(f"{i+1}. {model}")
    
    while True:
        choice = safe_input("\nモデル番号を入力 (0で終了): ").strip()
        if choice in ("0", "/exit"):
            print("プログラムを終了します")
            exit()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice)-1]
        print("無効な入力です")

def chat_session(model):
    """チャットセッション管理"""
    response = None
    try:
        print(f"\n{model}でチャット開始 (Ctrl+Cで中断)")
        while True:
            try:
                prompt = safe_input(f"{COLOR['user']}あなた: {COLOR['reset']}").strip()
                if not prompt:
                    continue
                
                # APIリクエスト処理
                try:
                    response = requests.post(
                        f"{OLLAMA_API_URL}/api/chat",
                        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                        stream=True,
                        timeout=60
                    )
                    response.raise_for_status()
                except requests.RequestException as e:
                    print(f"\nリクエストエラー: {e}")
                    continue

                # レスポンス処理
                print(f"{COLOR['model']}{model}: ", end="", flush=True)
                try:
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line).get("message", {}).get("content", "")
                                print(chunk, end="", flush=True)
                            except json.JSONDecodeError:
                                continue
                finally:
                    print(COLOR['reset'], end="", flush=True)
                print("\n")

            except KeyboardInterrupt:
                print(COLOR['reset'] + "\n中断されました", flush=True)
                break

    finally:
        if response:
            response.close()
        print(COLOR['reset'] + "セッションを終了します\n" + "="*50)

def main():
    """メイン処理"""
    models = get_models()
    if not models:
        print("利用可能なモデルが見つかりません")
        return
    
    try:
        while True:
            try:
                model = select_model(models)
                chat_session(model)
            except KeyboardInterrupt:
                print("\nメインメニューに戻ります")
                continue
    except KeyboardInterrupt:
        print("\nプログラムを終了します")

if __name__ == "__main__":
    main()