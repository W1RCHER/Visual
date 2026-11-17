"""Rebuild the Nubex integration after updating the standalone timetable."""
from pathlib import Path
import gzip, base64, re
root = Path(__file__).resolve().parent
app = (root.parent / 'расписание/расписание.html').read_text()
app = re.sub(r'<script>window.MAP_REFERENCES=.*?</script>', '', app, flags=re.S)
app = app.replace('</head>', '<style>header{display:none}main{padding:8px}body{background:transparent}</style></head>')
app = app.replace('</body>', "<script>new ResizeObserver(function(){parent.postMessage({type:'lyceum-schedule-height',height:document.documentElement.scrollHeight},'*');}).observe(document.body);</script></body>")
payload = base64.b64encode(gzip.compress(app.encode(), mtime=0)).decode()
code = (root / 'integration.js').read_text()
code, count = re.subn(r"atob\('[A-Za-z0-9+/=]+'\)", "atob('" + payload + "')", code)
assert count == 1
(root / 'integration.js').write_text(code)
(root / 'external-javascript.html').write_text('<script>\n' + code + '\n</script>')
print('Integration rebuilt. Paste external-javascript.html into Nubex settings.')
