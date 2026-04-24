import subprocess
import sys
import time
import os
import signal
import socket

def handler(signum, frame):
    pass

signal.signal(signal.SIGTERM, handler)

def is_port_in_use(port=5000):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(('127.0.0.1', port))
            return True
    except:
        return False

def kill_flask():
    try:
        subprocess.run(['pkill', '-f', 'python3 app.py'], capture_output=True)
    except:
        pass
    time.sleep(1)

def run():
    return subprocess.Popen(
        [sys.executable, 'app.py'],
        stdout=open('/tmp/flask_runner.log', 'a'),
        stderr=subprocess.STDOUT,
        cwd='/home/user_aioc/workspace/fundament_rf'
    )

if __name__ == '__main__':
    print('Flask watchdog started')
    kill_flask()
    time.sleep(2)
    proc = run()
    
    while True:
        try:
            proc.wait()
        except:
            pass
        
        time.sleep(1)
        
        if proc.poll() is not None:
            print(f'Flask crashed, restarting... (code: {proc.returncode})')
            kill_flask()
            time.sleep(2)
            proc = run()