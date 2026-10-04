"""
Cloudflare Quick Tunnel Launcher & Auto-Registrar.
Runs cloudflared.exe, discovers the assigned *.trycloudflare.com HTTPS domain,
saves it to output/cloudflare_tunnel.json, and keeps the tunnel active.
"""

import os
import re
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Ensure utf-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
INFO_FILE = OUTPUT_DIR / "cloudflare_tunnel.json"

CLOUDFLARED_EXE = Path("cloudflared.exe")

def run():
    if not CLOUDFLARED_EXE.exists():
        print("Error: cloudflared.exe not found in working directory.")
        sys.exit(1)

    cmd = [
        str(CLOUDFLARED_EXE),
        "tunnel",
        "--url", "http://127.0.0.1:8000",
        "--no-autoupdate"
    ]

    print("Starting Cloudflare Tunnel to http://127.0.0.1:8000...")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Read output to capture the public URL and keep process alive
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            clean_line = line.strip()
            print(f"[cloudflared] {clean_line}")
            match = url_pattern.search(clean_line)
            if match and not tunnel_url:
                tunnel_url = match.group(0)
                print("\n" + "="*60)
                print(f"[OK] CLOUDFLARE PUBLIC HTTPS TUNNEL ACTIVE:")
                print(f"Domain: {tunnel_url}")
                print(f"Telnyx Webhook: {tunnel_url}/api/voice/webhook/telnyx")
                print("="*60 + "\n")
                
                # Write to json file
                data = {
                    "url": tunnel_url,
                    "webhook_telnyx": f"{tunnel_url}/api/voice/webhook/telnyx",
                    "webhook_twilio": f"{tunnel_url}/api/voice/webhook/twilio",
                    "status": "active",
                    "started_at": datetime.now().isoformat()
                }
                INFO_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    rc = process.poll()
    print(f"cloudflared exited with return code {rc}")

if __name__ == "__main__":
    run()
