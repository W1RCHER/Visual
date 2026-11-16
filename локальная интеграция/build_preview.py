"""Build a read-only, local snapshot of the public school homepage."""
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urljoin, urlsplit
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json, re, shutil
from lxml import html, etree

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'preview'
BASE='https://xn--9-itbifh1e.xn--p1ai/'
OUT.mkdir(exist_ok=True)
(OUT/'assets').mkdir(exist_ok=True)
doc=html.fromstring((ROOT/'original.html').read_bytes())
doc.find('head').insert(0,html.Element('meta',charset='utf-8'))
cssurl=urljoin(BASE,doc.xpath('//link[@rel="stylesheet"]/@href')[0])
css=(ROOT/'original.css').read_text()
urls=set()
def full(u,base=BASE):
    return urljoin(base,u) if u and not u.startswith(('data:','#','javascript:','mailto:','tel:')) else None
for el in doc.xpath('//img[@src] | //link[@rel="icon"]'):
    u=full(el.get('src') or el.get('href'))
    if u:urls.add(u)
for raw in re.findall(r'url\(\s*[\'"]?([^\)\'\"]+)',css):
    u=full(raw.strip(),cssurl)
    if u:urls.add(u)
for el in doc.xpath('//*[@style]'):
    for raw in re.findall(r'url\(\s*[\'"]?([^\)\'\"]+)',el.get('style')):
        u=full(raw.strip())
        if u:urls.add(u)
def get(u):
    suffix=Path(urlsplit(u).path).suffix
    if len(suffix)>7:suffix=''
    p='assets/'+sha256(u.encode()).hexdigest()[:18]+suffix
    if 'pos.gosuslugi.ru' in u:return u,None,'Optional external widget omitted'
    try:
        dest=OUT/p
        if not dest.exists():
            with urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as r:dest.write_bytes(r.read())
        return u,p,None
    except Exception as e:return u,None,type(e).__name__
with ThreadPoolExecutor(max_workers=10) as pool:results=list(pool.map(get,sorted(urls)))
assets={u:p for u,p,e in results if p}
def replace_url(match,base):
    raw=match.group(1).strip();u=full(raw,base)
    return 'url("'+(assets.get(u,'') if u else raw)+'")'
css=re.sub(r'url\(\s*[\'"]?([^\)\'\"]+)[\'"]?\s*\)',lambda m:replace_url(m,cssurl),css)
(OUT/'school.css').write_text(css)
for el in doc.xpath('//script | //noscript | //iframe'):
    el.getparent().remove(el)
for el in doc.xpath('//*[@id="agreedBanner" or @id="js-show-iframe-wrapper"]'):
    el.getparent().remove(el)
for el in doc.iter():
    for key in list(el.attrib):
        if key.lower().startswith('on') or key=='srcset':del el.attrib[key]
    if el.get('style'):
        el.set('style',re.sub(r'url\(\s*[\'"]?([^\)\'\"]+)[\'"]?\s*\)',lambda m:replace_url(m,BASE),el.get('style')))
for el in doc.xpath('//img[@src] | //link[@rel="icon"]'):
    attr='src' if el.tag=='img' else 'href';u=full(el.get(attr))
    if u:el.set(attr,assets.get(u,''))
for el in doc.xpath('//link[@rel="stylesheet"]'):el.set('href','school.css')
for el in doc.xpath('//base | //link[@rel="alternate"]'):
    el.getparent().remove(el)
# Preserve original menu appearance, but all links in this local test stay local.
for a in doc.xpath('//a[@href]'):
    a.set('href','index.html')
    a.attrib.pop('target',None)
for f in doc.xpath('//form'):
    f.set('action','index.html');f.set('onsubmit','return false')
def link(label,where):
    a=html.Element('a',href='schedule.html');a.set('data-schedule-link',where);a.text=label;return a
top=doc.get_element_by_id('service_menu_top_map').getparent()
li=html.Element('li');li.append(link('расписание занятий','top'));top.addnext(li)
access=doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," widget_accessibility_column ")]')[0]
block=html.Element('div',{'class':'local-schedule-widget'})
a=link('','sidebar');a.append(html.fromstring('<span aria-hidden="true" class="calendar-icon">▦</span>'));a.append(html.fromstring('<span>Расписание занятий</span>'));block.append(a);access.addnext(block)
exam=doc.xpath('//*[contains(@class,"mainMenu")]//a[normalize-space(text())="Экзамены"]')[0].getparent()
breakli=html.Element('li',{'class':'schedule-row-break','aria-hidden':'true'});exam.addprevious(breakli)
li=html.Element('li',{'class':'item local-schedule-item'});li.append(link('Расписание занятий','menu'));exam.addprevious(li)
style=html.Element('style');style.text='''
.local-schedule-widget{margin:10px 0 16px}.local-schedule-widget a{display:flex;align-items:center;gap:12px;padding:16px 20px;color:#050731;background:#a1ced2;border-radius:5px;text-decoration:none;box-shadow:inset 0 0 10px #d0e9eb;font-size:20px}.local-schedule-widget a:hover{background:#b6dce0}.calendar-icon{font-size:32px}.mainMenu>ul>li.schedule-row-break{display:block;height:0;overflow:hidden;padding:0;margin:0;border:0}.local-preview-banner{position:relative;z-index:10000;padding:8px 18px;background:#fff2c5;color:#4f4320;font:14px/1.4 system-ui,sans-serif;text-align:center}.local-preview-banner a{color:inherit}.local-frame{display:block;border:0;width:100%;min-height:1200px;background:#f3f5f8}.local-back{display:inline-block;margin:12px;color:#050731;font:16px system-ui}.local-schedule-title{padding:12px;font:600 25px system-ui;color:#050731}'''
style.text+='\n.mainMenu>ul>li.schedule-row-break~li>a{font-size:1.45em;padding:10px 10px}.local-schedule-widget a{font-family:Arial,sans-serif;font-size:18px;text-align:left;min-height:64px}.local-schedule-widget .calendar-icon{flex:0 0 auto}\n'
doc.find('head').append(style)
banner=html.fromstring('<div class="local-preview-banner">Локальная проверка интеграции · действующий сайт лицея не изменён</div>')
doc.find('body').insert(0,banner)
(OUT/'index.html').write_bytes(html.tostring(doc,encoding='utf-8',doctype='<!doctype html>'))
# Find the homepage content container by its news heading.
heading=None
for e in doc.xpath('//h1|//h2'):
    if ' '.join(e.itertext()).strip()=='Новости':heading=e;break
assert heading is not None
content=heading.getparent().getparent()
assert 'siteContent' in content.get('class','')
for child in list(content):content.remove(child)
back=html.fromstring('<a href="index.html" class="local-back">← На главную лицея</a>');content.append(back)
frame=html.Element('iframe',src='schedule-app/index.html',title='Интерактивное расписание и карта кабинетов',id='schedule-frame',attrib={'class':'local-frame'})
content.append(frame)
script=html.Element('script');script.text="window.addEventListener('message',function(e){var f=document.getElementById('schedule-frame');if(e.source===f.contentWindow&&e.data&&e.data.type==='schedule-height'&&Number.isFinite(e.data.height))f.style.height=Math.min(15000,Math.max(800,e.data.height))+'px';});"
doc.find('body').append(script)
doc.find('head/title').text='Расписание занятий · Лицей № 9 · локальная проверка'
doc.find('body').set('class',doc.find('body').get('class','').replace('mainPage',''))
(OUT/'schedule.html').write_bytes(html.tostring(doc,encoding='utf-8',doctype='<!doctype html>'))
shutil.copytree(ROOT.parent/'расписание/dist',OUT/'schedule-app',dirs_exist_ok=True)
app=OUT/'schedule-app/index.html'
s=app.read_text();s=s.replace('</head>','<style>header{display:none}main{padding:12px}@media(min-width:800px) and (max-width:1000px){.map-layout{grid-template-columns:minmax(0,1fr) 280px;gap:14px}.room-detail{padding:16px}}</style></head>')
s=s.replace('</body>',"<script>new ResizeObserver(function(){parent.postMessage({type:'schedule-height',height:document.documentElement.scrollHeight},'*');}).observe(document.body);</script></body>")
app.write_text(s)
(ROOT/'asset-manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print('Assets downloaded',len(assets),'failed',[(u,e) for u,p,e in results if e])
