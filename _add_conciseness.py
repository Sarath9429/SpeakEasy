import pathlib, textwrap

endpoint = textwrap.dedent("""

# -- Practice Conciseness Feedback --
class ConciseFeedbackRequest(BaseModel):
    transcript: str
    topic: str = ""

@app.post("/practice/conciseness")
async def practice_conciseness(req: ConciseFeedbackRequest):
    try:
        if not req.transcript or len(req.transcript.strip()) < 20:
            return {"ok": False, "error": "Transcript too short."}
        from fusion_layer import NVIDIA_API_KEY
        if not NVIDIA_API_KEY:
            return {"ok": False, "error": "No API key configured."}
        topic_line = ("Topic: " + req.topic + "\\n") if req.topic else ""
        prompt = (
            "You are an expert speech coach. Analyze the following spoken transcript "
            "and provide conciseness feedback.\\n\\n"
            + topic_line
            + "Transcript:\\n\\"" + req.transcript.strip() + "\\"\\n\\n"
            + "Return ONLY this JSON, no extra text, no code fences:\\n"
            + "{\\"critique\\":\\"2-3 sentences on what made the speech verbose or unclear\\","
            + "\\"ideal_version\\":\\"A concise clear rewrite of the same ideas in 2-4 sentences\\"}"
        )
        headers = {"Authorization": "Bearer " + NVIDIA_API_KEY, "Content-Type": "application/json"}
        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5, "max_tokens": 512, "stream": False
        }
        import httpx, re as _re, json as _json
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers, json=payload, timeout=30.0)
            resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
        reply = _re.sub(r'^```(?:json)?\\s*', '', reply)
        reply = _re.sub(r'\\s*```$', '', reply).strip()
        try:
            return {"ok": True, "feedback": _json.loads(reply)}
        except Exception:
            return {"ok": False, "error": "Malformed JSON", "raw": reply}
    except Exception as e:
        return {"ok": False, "error": str(e)}
""")

p = pathlib.Path("server.py")
p.write_text(p.read_text(encoding="utf-8") + endpoint, encoding="utf-8")
print("Done - /practice/conciseness appended")
