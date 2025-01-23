@echo off
rem start_ollama.batを別ウィンドウで起動（常時実行状態）
start "Ollama Server" cmd /c start_ollama.bat

rem run_ollama_chat.batを別ウィンドウで起動
start "Ollama Chat" cmd /c run_ollama_chat.bat

rem 1秒待機（ウィンドウが開くのを待つ）
timeout /t 1 /nobreak >nul

rem PowerShellでOllama Chatウィンドウにフォーカスを移動
powershell -Command "$sig='[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);'; Add-Type -MemberDefinition $sig -Name NativeMethods -Namespace Utils; $hwnd=@(Get-Process | ?{$_.MainWindowTitle -eq 'Ollama Chat'}).MainWindowHandle; if($hwnd) { [Utils.NativeMethods]::SetForegroundWindow($hwnd[0]) }"

rem 自プロセスのコマンドプロンプトを閉じる
exit