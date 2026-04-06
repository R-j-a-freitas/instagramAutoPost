import requests
import os
import time

# API Key do utilizador
api_key = "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"
url = "https://integrate.api.nvidia.com/v1/chat/completions"

models_to_test = [
    "moonshotai/kimi-k2.5",
    "nvidia/llama-3.1-8b-instruct"
]

print(f"Testing connection to {url}")
for model in models_to_test:
    print(f"\n--- Testing model: {model} ---")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 10
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    start_time = time.time()
    try:
        print("Trying with 10s timeout...")
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"Success! Response time: {time.time() - start_time:.2f}s")
        print(f"Content: {resp.json()['choices'][0]['message']['content']}")
    except Exception as e:
        print(f"Failed with 10s timeout: {e}")
        print("Trying with 60s timeout...")
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            print(f"Success with 60s! Response time: {time.time() - start_time:.2f}s")
            print(f"Content: {resp.json()['choices'][0]['message']['content']}")
        except Exception as e2:
            print(f"Failed with 60s timeout: {e2}")
            print("Trying with 120s timeout...")
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
                resp.raise_for_status()
                print(f"Success with 120s! Response time: {time.time() - start_time:.2f}s")
                print(f"Content: {resp.json()['choices'][0]['message']['content']}")
            except Exception as e3:
                print(f"Failed with 120s timeout: {e3}")
