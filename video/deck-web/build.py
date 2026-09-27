"""Inlines images and narration into template.html -> index.html (single self-contained page)."""
import base64, json, os, re
R = os.path.dirname(os.path.abspath(__file__)); V = os.path.dirname(R)
t = open(os.path.join(R, 'template.html')).read()
def data(p, mime): return f"data:{mime};base64," + base64.b64encode(open(p, 'rb').read()).decode()
t = re.sub(r'\{\{img:([a-z0-9-]+)\}\}', lambda m: data(os.path.join(R, 'assets', m.group(1) + '.jpg'), 'image/jpeg'), t)
nar = {}
for sc in json.load(open(os.path.join(V, 'script.json')))['scenes']:
    w = json.load(open(os.path.join(V, 'vo', sc['id'] + '.json')))
    nar[sc['id']] = {'src': data(os.path.join(V, 'vo', sc['id'] + '.mp3'), 'audio/mpeg'), 'duration': w['duration'], 'words': [{'w': x['w'], 's': round(x['s'], 2), 'e': round(x['e'], 2)} for x in w['words']]}
t = t.replace('{{narration}}', json.dumps(nar))
out = os.path.join(R, 'index.html'); open(out, 'w').write(t)
print(out, round(os.path.getsize(out) / 1e6, 2), 'MB')
