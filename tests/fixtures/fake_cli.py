"""Stand-in for a provider CLI. Mode = argv[1]. Reads the prompt from stdin like the real adapters pass it.
Modes: ok | echo | exit3 | badjson | sleep | tree <pidfile> | big"""
import json
import subprocess
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
prompt = sys.stdin.read()

if mode == "ok":
    print(json.dumps({"session": "sess-123", "text": "xong"}))
elif mode == "echo":  # prove the prompt arrived verbatim as DATA
    print(json.dumps({"session": "s", "text": prompt, "argv": sys.argv[1:]}))
elif mode == "exit3":
    sys.stderr.write("lỗi giả lập api_key=sk-abcdefghijklmnopqrstuvwxyz123456\n")
    sys.exit(3)
elif mode == "badjson":
    print("{not json")
elif mode == "sleep":
    time.sleep(60)
elif mode == "tree":  # spawn a grandchild, publish its pid, then wait
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    open(sys.argv[2], "w").write(str(child.pid))
    time.sleep(60)
elif mode == "pids":  # publish own pid + a grandchild's pid, then wait (orphan-on-crash drill)
    import os
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    open(sys.argv[2], "w").write(f"{os.getpid()} {child.pid}")
    time.sleep(120)
elif mode == "probe_old":   # an older CLI: --version works, --help lacks the flags AATPO needs
    print("0.0.1" if "--version" in sys.argv else "usage: tool [options]")
elif mode == "big":
    sys.stdout.write("x" * 3_000_000)
elif mode == "claude_ok":
    print(json.dumps({"type": "result", "result": "đã đọc xong", "is_error": False,
                      "session_id": "11111111-2222-3333-4444-555555555555", "echo": prompt}))
elif mode == "codex_ok":
    out = sys.argv[sys.argv.index("-o") + 1]
    open(out, "w", encoding="utf-8").write("câu trả lời cuối")
    print(json.dumps({"type": "thread.started", "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}))
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "tạm"}}))
    print(json.dumps({"type": "turn.completed"}))
