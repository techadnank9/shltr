"""Generate the narration with ElevenLabs, one MP3 per scene plus word timings.
Key is read from an env var or a .env file; it is never written anywhere."""
import base64, json, os, sys, time, urllib.request
ROOT = os.path.dirname(os.path.abspath(__file__))
key = os.environ.get("ELEVENLABS_API_KEY")
if not key:
    for p in [os.path.join(ROOT, "..", ".env"), os.path.expanduser("~/Documents/soul/.env")]:
        if os.path.exists(p):
            for line in open(p):
                if line.startswith("ELEVENLABS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"')
    if not key: sys.exit("no ELEVENLABS_API_KEY")
s = json.load(open(os.path.join(ROOT, "script.json")))
out = os.path.join(ROOT, "vo"); os.makedirs(out, exist_ok=True)
for sc in s["scenes"]:
    mp3 = os.path.join(out, sc["id"] + ".mp3")
    if os.path.exists(mp3): print("skip", sc["id"]); continue
    body = json.dumps({"text": sc["text"], "model_id": "eleven_multilingual_v2",
                       "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.25, "speed": 1.0}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{s['voice']}/with-timestamps?output_format=mp3_44100_128",
                                 data=body, headers={"xi-api-key": key, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=120)); break
        except Exception as e:
            print("retry", sc["id"], e); time.sleep(3)
    open(mp3, "wb").write(base64.b64decode(r["audio_base64"]))
    al = r["alignment"]
    # characters -> words with start/end
    words, cur, start = [], "", None
    for ch, t0, t1 in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if ch.isspace():
            if cur: words.append({"w": cur, "s": start, "e": last}); cur, start = "", None
        else:
            if start is None: start = t0
            cur += ch; last = t1
    if cur: words.append({"w": cur, "s": start, "e": last})
    json.dump({"id": sc["id"], "text": sc["text"], "duration": al["character_end_times_seconds"][-1], "words": words},
              open(os.path.join(out, sc["id"] + ".json"), "w"), indent=1)
    print("ok", sc["id"], f'{al["character_end_times_seconds"][-1]:.1f}s')
