import subprocess
import time
import sys
import os

TARGET_SUBDOMAIN = "ayush-smart-backend"
PORT = 8000

print("=" * 60)
print(f"  SMART TUNNEL SUPERVISOR — FIXED SUBDOMAIN LOCK")
print(f"  Target: https://{TARGET_SUBDOMAIN}.loca.lt")
print("=" * 60)
sys.stdout.flush()

def start_tunnel():
    print(f"\n[{time.strftime('%X')}] Requesting fixed subdomain '{TARGET_SUBDOMAIN}' on port {PORT}...")
    sys.stdout.flush()
    
    # Spawn npx localtunnel
    cmd = f"npx localtunnel --port {PORT} --subdomain {TARGET_SUBDOMAIN}"
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=True
    )

    assigned_correct_url = False

    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line_clean = line.strip()
        print(line_clean)
        sys.stdout.flush()

        if "your url is:" in line_clean.lower():
            if TARGET_SUBDOMAIN in line_clean:
                assigned_correct_url = True
                print(f"[{time.strftime('%X')}] [OK] Confirmed: Live on https://{TARGET_SUBDOMAIN}.loca.lt")
                sys.stdout.flush()
            else:
                print(f"[{time.strftime('%X')}] [REJECTED] Server assigned random URL ({line_clean}). Killing to reclaim '{TARGET_SUBDOMAIN}'...")
                sys.stdout.flush()
                proc.terminate()
                try:
                    proc.kill()
                except Exception:
                    pass
                return False

    proc.wait()
    return assigned_correct_url

while True:
    try:
        ok = start_tunnel()
        if not ok:
            print(f"[{time.strftime('%X')}] Waiting 12 seconds for localtunnel server to release subdomain lease...")
            time.sleep(12)
        else:
            print(f"[{time.strftime('%X')}] Tunnel session ended. Re-establishing in 8 seconds...")
            time.sleep(8)
    except KeyboardInterrupt:
        print("\nTunnel supervisor stopped by user.")
        break
    except Exception as e:
        print(f"Supervisor error: {e}. Retrying in 10s...")
        time.sleep(10)
