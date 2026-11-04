import subprocess
import time
import sys
import os
import threading
import urllib.request

TARGET_SUBDOMAIN = "ayush-smart-backend"
PORT = 8000
HEALTH_URL = f"https://{TARGET_SUBDOMAIN}.loca.lt/health"

print("=" * 60)
print(f"  SMART TUNNEL SUPERVISOR — FIXED SUBDOMAIN LOCK")
print(f"  Target: https://{TARGET_SUBDOMAIN}.loca.lt")
print("=" * 60)
sys.stdout.flush()

tunnel_active = False

def keep_alive_pinger():
    """Periodically ping the tunnel URL to prevent idle drops from remote gateway."""
    global tunnel_active
    while True:
        time.sleep(30)
        if tunnel_active:
            try:
                req = urllib.request.Request(
                    HEALTH_URL,
                    headers={"User-Agent": "Tunnel-KeepAlive/1.0", "Bypass-Tunnel-Reminder": "true"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    if resp.status == 200:
                        pass
            except Exception:
                pass

pinger_thread = threading.Thread(target=keep_alive_pinger, daemon=True)
pinger_thread.start()

def kill_zombie_tunnels():
    """Kill any stuck node localtunnel processes before launching."""
    try:
        if os.name == 'nt':
            subprocess.run("taskkill /F /IM node.exe >nul 2>&1", shell=True)
    except Exception:
        pass

def start_tunnel():
    global tunnel_active
    tunnel_active = False
    
    print(f"\n[{time.strftime('%X')}] Requesting fixed subdomain '{TARGET_SUBDOMAIN}' on port {PORT}...")
    sys.stdout.flush()

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
                tunnel_active = True
                print(f"[{time.strftime('%X')}] [LOCK ACQUIRED] Live on https://{TARGET_SUBDOMAIN}.loca.lt")
                print(f"[{time.strftime('%X')}] Tunnel keep-alive heartbeat active (30s interval).")
                sys.stdout.flush()
            else:
                tunnel_active = False
                print(f"[{time.strftime('%X')}] [REJECTED] Server assigned random URL ({line_clean}). Killing to reclaim '{TARGET_SUBDOMAIN}'...")
                sys.stdout.flush()
                proc.terminate()
                try:
                    proc.kill()
                except Exception:
                    pass
                return False

    proc.wait()
    tunnel_active = False
    return assigned_correct_url

kill_zombie_tunnels()

while True:
    try:
        ok = start_tunnel()
        if not ok:
            print(f"[{time.strftime('%X')}] Waiting 12 seconds for localtunnel server to release subdomain lease...")
            time.sleep(12)
        else:
            print(f"[{time.strftime('%X')}] Tunnel connection closed or dropped. Re-establishing in 8 seconds...")
            time.sleep(8)
    except KeyboardInterrupt:
        print("\nTunnel supervisor stopped by user.")
        break
    except Exception as e:
        print(f"Supervisor error: {e}. Retrying in 10s...")
        time.sleep(10)
