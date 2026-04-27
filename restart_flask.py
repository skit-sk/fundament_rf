#!/usr/bin/env python3
"""restart_flask.py - быстрый перезапуск Flask после изменений"""
import subprocess
import time
import os
import signal
import sys

PROJECT_DIR = "/home/user_aioc/workspace/fundament_rf"
APP_FILE = "app.py"

def kill_flask():
    """Убить процессы Flask"""
    try:
        result = subprocess.check_output(["pgrep", "-f", APP_FILE], text=True)
        for pid in result.strip().split("\n"):
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"✅ Killed {pid}")
                except:
                    pass
    except subprocess.CalledProcessError:
        pass
    time.sleep(0.5)

def start_flask():
    """Запустить Flask"""
    with open("/tmp/flask.log", "w") as log:
        proc = subprocess.Popen(
            [sys.executable, APP_FILE],
            cwd=PROJECT_DIR,
            stdout=log,
            stderr=subprocess.STDOUT
        )
    time.sleep(1)
    print(f"✅ Flask started (PID: {proc.pid})")
    return proc

def restart():
    """Перезапустить Flask"""
    print("🔄 Restarting Flask...")
    kill_flask()
    start_flask()
    print("✅ Done")

if __name__ == "__main__":
    restart()