import os
import json
import urllib.request
import urllib.error
import time

api_key = os.environ.get("NVIDIA_API_KEY", "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")
url = "https://integrate.api.nvidia.com/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

topic_line = "Topic: global warming\n"
transcript = "The carbon dioxide, uh, and the nitrosypsy used as a greenhouse gases. I noticed through the atmosphere due to this the sunrays trap. The voice of the air. And due to the green noise effect happens."

prompt = (
    "You are an expert speech coach. Analyze the following spoken transcript "
    "and provide conciseness feedback.\n\n"
    + topic_line
    + "Transcript:\n\"" + transcript.strip() + "\"\n\n"
    + "Return ONLY this JSON, no extra text, no code fences:\n"
    + "{\"critique\":\"2-3 sentences on what made the speech verbose or unclear\","
    + "\"ideal_version\":\"A concise clear rewrite of the same ideas in 2-4 sentences\"}"
)

payload = {
    "model": "meta/llama-3.1-70b-instruct",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.5,
    "max_tokens": 512,
    "stream": False
}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers=headers, method='POST')

print(f"Testing 70b...")
start = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        print(f"Status: {resp.status}")
        reply = resp.read().decode('utf-8')
        end = time.time()
        print(f"Time taken: {end - start:.2f} seconds")
except Exception as e:
    print(f"Error: {e}")
