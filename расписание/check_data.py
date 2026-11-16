"""Independent invariants of the imported timetable and source joins."""
import json
from pathlib import Path

d=json.loads((Path(__file__).parent/'data.json').read_text())
assert len(d['classes'])==35
assert set(map(int,d['slots']))==set(range(1,14))
assert d['slots']['4']==['10:55','11:35']
assert d['slots']['7']==['13:25','14:05']
assert d['slots']['8']==['13:45','14:25']
assert len({l['source'] for l in d['lessons']})==len(d['lessons'])
assert set(o['day'] for o in d['occupancy'])==set(range(6))
assert all(l['rooms'] for l in d['lessons'] if l['scope']=='main')
assert all(not l['rooms'] for l in d['lessons'] if l['scope']=='remote')
assert all(not (r.isdigit() and int(r)<100) for l in d['lessons'] if l['scope']=='main' for r in l['rooms'])
assert d['stats']['missingTimes']==3
assert d['stats']['offsetScores']['7']>max(v for k,v in d['stats']['offsetScores'].items() if k!='7')
known={l['source']:l for l in d['lessons']}
assert known['Excel: 1 смена!AC17']['className']=='11И'
assert known['Excel: 1 смена!AC17']['subject']=='Информатика'
assert known['Excel: 1 смена!AC17']['rooms']==['309','311']
assert known['Excel: 2 смена!H53']['start'] is None
for l in d['lessons']:
 for c in l['roomChecks']:
  for teacher in c['teachers']:
   assert any(o['teacher']==teacher and o['day']==l['day'] and o['slot']==l['slot'] and o['room']==c['room'] and l['className'] in o['classes'] for o in d['occupancy'])
 for teacher in l['teachers']:
  assert any(o['teacher']==teacher and o['day']==l['day'] and o['slot']==l['slot'] and o['room'] in l['rooms'] and l['className'] in o['classes'] for o in d['occupancy'])
assert any(i['lesson']=='xlsx-1-P12' and i['kind']=='В Word указан другой класс' for i in d['issues'])
print('OK: slots, overlapping shifts, class/room extraction, excluded CDO, teacher provenance, unknown time, source discrepancies')
