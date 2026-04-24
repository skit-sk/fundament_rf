import subprocess
import sys
import time
import os
import signal

def handler(signum, frame):
    pass

signal.signal(signal.SIGTERM, handler)

def run():
    return subprocess.Popen(
        [sys.executable, 'app.py'],
        stdout=open('/tmp/flask.log', 'a'),
        stderr=subprocess.STDOUT,
        cwd='/home/user_aioc/workspace/fundament_rf'
    )

if __name__ == '__main__':
    proc = run()
    while True:
        try:
            proc.wait()
        except:
            pass
        
        time.sleep(1)
        
        if proc.poll() is not None:
            proc = run()