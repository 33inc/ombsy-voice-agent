import subprocess
import requests
import sys
import os
import time
import threading

from dotenv import load_dotenv
load_dotenv()

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
APP_ID = "3039124097754727792"

def update_telnyx_webhook(url):
    print(f"Updating Telnyx Webhook to: {url}/webhook")
    res = requests.patch(
        f"https://api.telnyx.com/v2/texml_applications/{APP_ID}",
        headers={
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        json={
            "voice_url": f"{url}/webhook",
            "voice_method": "post"
        }
    )
    if res.status_code == 200:
        print("Success! Telnyx is now pointing to your local machine.")
    else:
        print(f"Error updating Telnyx: {res.text}")

def read_tunnel(process):
    url_found = False
    while True:
        line = process.stdout.readline()
        if not line:
            break
        output = line.decode('utf-8', errors='ignore').strip()
        print(f"localhost.run: {output}", flush=True)
        if not url_found and "tunneled with tls termination" in output:
            words = output.split()
            for word in words:
                if word.startswith("https://") and ".lhr.life" in word:
                    clean_url = word.strip("| ")
                    update_telnyx_webhook(clean_url)
                    url_found = True

def main():
    print("Starting localhost.run Tunnel...")
    lt_process = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-R", "80:127.0.0.1:8000", "nokey@localhost.run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    
    t = threading.Thread(target=read_tunnel, args=(lt_process,))
    t.daemon = True
    t.start()
    
    # Wait a moment for it to establish
    time.sleep(5)
    
    print("\nStarting Voice Bot Server...")
    server_process = subprocess.Popen(
        ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
    )
    
    try:
        server_process.wait()
    except KeyboardInterrupt:
        print("Shutting down...")
        server_process.terminate()
        lt_process.terminate()

if __name__ == "__main__":
    main()
