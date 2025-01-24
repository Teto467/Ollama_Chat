import sys
import requests
import json
from threading import Event
from datetime import datetime

# Windows向けエンコーディング設定
if sys.platform == "win32":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleCP(65001)
    kernel32.SetConsoleOutputCP(65001)

OLLAMA_API_URL = "http://localhost:11434"
COLOR = {
    "user": "\033[34m",    # 青
    "reset": "\033[0m",    # リセット
    "model": "\033[32m",   # 緑
    "number": "\033[33m",  # 黄
    "model_name": "\033[36m",  # シアン
    "date": "\033[35m"     # マゼンタ
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
    """改良版モデル情報取得（日時情報含む）"""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=10)
        response.raise_for_status()
        return sorted(
            [{"name": m["name"], 
              "modified": datetime.fromisoformat(m["modified_at"].rstrip('Z'))}
             for m in response.json().get("models", [])],
            key=lambda x: x["modified"], 
            reverse=True
        )
    except Exception as e:
        print(f"モデル取得エラー: {e}")
        return []

def select_model(models):
    """カラー表示付きモデル選択インタフェース"""
    print(f"\n{COLOR['number']}番号 {COLOR['model_name']}モデル名 {COLOR['date']}DL日時{COLOR['reset']}")
    
    for i, model in enumerate(models):
        local_time = model["modified"].astimezone().strftime('%Y-%m-%d %H:%M')
        print(
            f"{COLOR['number']}{i+1:2d}. "
            f"{COLOR['model_name']}{model['name'][:20]:<20} "
            f"{COLOR['date']}[DL: {local_time}]{COLOR['reset']}"
        )
    
    while True:
        choice = safe_input("\n選択するモデルの番号を入力 (0で終了): ").strip()
        if choice in ("0", "/exit"):
            print("プログラムを終了します")
            exit()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice)-1]["name"]
        print("無効な入力です")

def chat_session(model):
    """チャットセッション管理"""
    response = None
    try:
        print(f"\n{model}でチャット開始 (Ctrl+Cで中断&モデル選択)")
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