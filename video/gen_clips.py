"""Builds src/clips.json: which recording and offset (seconds) each shot uses.
Falls back to the scripted recording when the live one is missing."""
import json, os
live = json.load(open('footage/live.marks.json')) if os.path.exists('footage/live.marks.json') and os.path.exists('public/footage/live.mp4') else None
fake = json.load(open('footage/fake.marks.json'))
f0 = fake['loaded']  # fake demo clock starts when the page loaded
def F(t): return {'src': 'footage/fake.mp4', 'from': round(f0 + t, 2)}
def L(k, plus=0): return {'src': 'footage/live.mp4', 'from': round(live[k] + plus, 2)}
clips = {
  'app:start':     L('start_loaded', 0.5) if live else F(0),
  'app:depth':     L('case_page', 25.5) if live and live.get('estimate') else F(2.5),
  'app:retry':     F(8.6),
  'app:damage':    F(12.6),
  'app:contained': L('check_link_sent', 2.0) if live and live.get('contained') else F(18.2),
  'app:form':      F(24.2),
  'numbers':       L('estimate', -6) if live and live.get('estimate') else F(15),
}
json.dump(clips, open('src/clips.json', 'w'), indent=1); print(json.dumps(clips))
