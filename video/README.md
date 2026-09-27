# Demo video and pitch deck

TV-style narrated demo (about 2:45, 1080p) and a 12-slide deck, built from real footage of the live app.

Outputs (not in git, too large): `out/sheltr-demo.mp4`, `out/sheltr-deck.pptx`, `out/sheltr-deck.pdf`.

## Rebuild

```
cd video && npm install && npx playwright install chromium
python3 make_vo.py            # narration from script.json via ElevenLabs (ELEVENLABS_API_KEY), writes vo/*.mp3 + word timings
node record.mjs               # records the scripted case, a live run on the public URL, and stills (footage/)
python3 gen_clips.py          # picks the clip offsets for each shot (src/clips.json)
npx remotion render src/index.ts Demo out/sheltr-demo.mp4 --codec=h264 --crf=18
node deck.js                  # out/sheltr-deck.pptx
```

`public/fema/` holds the public-domain FEMA photos from `datasets/fetch.py`; `public/music.mp3` is an instrumental bed generated with the ElevenLabs music API. Fonts in `public/fonts/` are the same three families as the app.

## Fluid web presentation (`deck-web/`)

A single self-contained HTML page that plays the same story as one continuous, animated flow: a live flowing-water canvas, kinetic type, count-ups, wipes and morphs between scenes, and a Play mode that runs the narration with word-synced captions. Arrow keys, click or swipe to step; space to play.

```
cd video && python3 deck-web/build.py      # inlines assets + narration -> deck-web/index.html (about 4.6 MB)
node deck-web/shots.mjs                   # optional: screenshots of key scenes for a quick check
```
