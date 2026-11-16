"""Read the original print layouts without modifying either source file."""
import csv
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import openpyxl
from lxml import etree as E

ROOT = Path(__file__).resolve().parent
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']

def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()

def klass(s):
    return re.sub(r'\s+', '', s).upper().replace('Ё', 'Е')

def extract_classes(s):
    # Longest suffix first; no fuzzy matching of classes/teachers.
    return list(dict.fromkeys(klass(m.group()) for m in re.finditer(
        r'(?<!\d)(?:1[01]|[1-9])\s*(?:авиа|мед|[АБВГДЕИМЛЭФ])', s, re.I)))

def doc_rows(table):
    for tr in table.findall('w:tr', NS):
        col = 0
        cells = []
        before = tr.find('w:trPr/w:gridBefore', NS)
        if before is not None:
            col = int(before.get('{'+NS['w']+'}val'))
        for tc in tr.findall('w:tc', NS):
            text = clean(' '.join(''.join(p.xpath('.//w:t/text()', namespaces=NS)) for p in tc.findall('w:p', NS)))
            sp = tc.find('w:tcPr/w:gridSpan', NS)
            span = int(sp.get('{'+NS['w']+'}val')) if sp is not None else 1
            cells.append((col, span, text))
            col += span
        yield cells

def main():
    sources = ROOT/'source'
    xp = sources/'расписание.xlsx'
    dp = sources/'кабинеты.docx'
    if not xp.exists():
        shutil.copy2(next(Path('/Users/aleksandr/Downloads').glob('Расписание на печать Iполугодие* (9) (3).xlsx')), xp)
    if not dp.exists():
        shutil.copy2('/Users/aleksandr/Downloads/кабинеты (2).docx', dp)
    occupancy, slots, rooms = [], {}, set()
    with ZipFile(dp) as z:
        doc = E.fromstring(z.read('word/document.xml'))
    day = None
    coverage = set()
    for ti, table in enumerate(doc.findall('.//w:tbl', NS), 1):
        rows = list(doc_rows(table))
        text = ' '.join(c[2] for row in rows for c in row)
        for d in DAYS:
            if d in text:
                day = DAYS.index(d)
        assert day is not None
        columns = {}
        for row in rows:
            for col, span, value in row:
                m = re.fullmatch(r'(1[0-3]|[1-9])\s*(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})', value)
                if m:
                    slot, start, end = int(m[1]), m[2].zfill(5), m[3].zfill(5)
                    assert slot not in slots or slots[slot] == [start, end]
                    slots[slot] = [start, end]
                    for c in range(col, col+span):
                        columns[c] = slot
        assert len(set(columns.values())) == 13, (ti, columns)
        for ri, row in enumerate(rows, 1):
            if not row or not re.fullmatch(r'\d{3}|с/з', row[0][2]):
                continue
            room = row[0][2]
            rooms.add(room)
            coverage.add((day, room))
            for col, span, raw in row[1:]:
                if not raw:
                    continue
                represented = sorted({columns[c] for c in range(col, col+span) if c in columns})
                for slot in represented:
                    found = extract_classes(raw)
                    teacher_match = re.search(r'[А-ЯЁ][а-яё-]+\s+[А-ЯЁ]\s*\.\s*[А-ЯЁ]\s*\.?', raw)
                    teacher = clean(teacher_match.group()) if teacher_match else None
                    occupancy.append(dict(id=f'doc-{ti}-{ri}-{slot}', day=day, room=room,
                        slot=slot, start=slots[slot][0], end=slots[slot][1], classes=found,
                        teacher=teacher, raw=raw, source=f'Word: таблица {ti}, строка {ri}'))
    lessons = []
    book = openpyxl.load_workbook(xp, data_only=True)
    for si, sheet in enumerate(book, 1):
        cols = {c.column: klass(str(c.value)) for c in sheet[6] if c.value and re.fullmatch(r'\d+[А-Яа-я]+', str(c.value))}
        groups = [(col, 2+8*((col-3)//8)) for col in cols]
        day = None
        for row in range(7, sheet.max_row+1):
            d = clean(sheet.cell(row, 1).value).capitalize()
            if d in DAYS:
                day = DAYS.index(d)
            for col, lesson_col in groups:
                num = sheet.cell(row, lesson_col).value
                raw = clean(sheet.cell(row, col).value)
                if not isinstance(num, (int, float)) or not raw:
                    continue
                subject = clean(re.sub(r'\s*\([^)]*\)\s*$', '', raw))
                parens = re.findall(r'\(([^)]*)\)', raw)
                room_tokens = []
                for part in parens:
                    if re.fullmatch(r'\s*\d+(?:\s*,\s*\d+)*\s*', part):
                        room_tokens.extend(re.findall(r'\d+', part))
                    elif 'с/з' in part.lower():
                        room_tokens.append('с/з')
                remote = 'moodle' in raw.lower()
                # Confirmed scope: CDO rooms 2–7 and the unlocated Saturday CDO courses.
                cdo = bool(room_tokens and all(r.isdigit() and int(r)<100 for r in room_tokens))
                cdo = cdo or (day == 5 and not room_tokens and not remote and bool(re.search(r'робот|модел|БПЛА|[Мм]ашин|VR', raw)))
                scope = 'cdo' if cdo else 'remote' if remote else 'main'
                # 2nd shift numbering is inferred from same-class/same-room matches below.
                slot = int(num) if si==1 else int(num)+7
                times = slots.get(slot, [None, None])
                lessons.append(dict(id=f'xlsx-{si}-{sheet.cell(row,col).coordinate}', day=day,
                    shift=si, lesson=int(num), slot=slot, start=times[0], end=times[1],
                    className=cols[col], subject=subject, rooms=room_tokens if scope=='main' else [],
                    scope=scope, raw=raw, teachers=[], source=f'Excel: {sheet.title}!{sheet.cell(row,col).coordinate}'))
    index = {}
    for o in occupancy:
        index.setdefault((o['day'],o['slot'],o['room']), []).append(o)
    issues = []
    for l in lessons:
        l['roomChecks'] = []
        if l['scope']!='main':
            continue
        rooms.update(l['rooms'])
        if not l['start']:
            issues.append(dict(kind='Время не установлено', lesson=l['id'], text=f"{DAYS[l['day']]} · {l['className']} · {l['lesson']} урок, смена {l['shift']} · {l['subject']}", source=l['source']))
        for room in l['rooms']:
            candidates = index.get((l['day'],l['slot'],room), [])
            matches = [o for o in candidates if l['className'] in o['classes']]
            if matches:
                state='matched'
                for o in matches:
                    if o['teacher'] and o['teacher'] not in l['teachers']:
                        l['teachers'].append(o['teacher'])
            else:
                state = ('different' if any(o['classes'] for o in candidates) else 'unconfirmed') if candidates else 'blank' if (l['day'],room) in coverage else 'not_listed'
                # Shared gym can host several classes; still display discrepancy for review.
                issues.append(dict(kind={'different':'В Word указан другой класс','unconfirmed':'В Word не указан класс','blank':'В Word пусто','not_listed':'Кабинет отсутствует в Word'}[state],
                    lesson=l['id'], text=f"{DAYS[l['day']]} · {l['className']} · {l['lesson']} урок, смена {l['shift']} · {l['subject']} · {room}",
                    word='; '.join(o['raw'] for o in candidates), source=l['source']))
            l['roomChecks'].append(dict(room=room, state=state, word=[o['raw'] for o in candidates],
                teachers=list(dict.fromkeys(o['teacher'] for o in matches if o['teacher']))))
    # Compare shifts using class+room signals, without treating the inference as an approved bell schedule.
    offset_scores = {}
    second=[l for l in lessons if l['shift']==2 and l['scope']=='main']
    for offset in range(5,9):
        offset_scores[offset]=sum(any(l['className'] in o['classes'] for o in index.get((l['day'],l['lesson']+offset,r),[])) for l in second for r in l['rooms'])
    used={(l['day'],l['slot'],r,l['className']) for l in lessons if l['scope']=='main' for r in l['rooms']}
    doc_extra=[o for o in occupancy if not any((o['day'],o['slot'],o['room'],c) in used for c in o['classes'])]
    stats=dict(classes=len({l['className'] for l in lessons}),rooms=len(rooms),lessons=len(lessons),
        scope=dict(Counter(l['scope'] for l in lessons)),wordRecords=len(occupancy),
        checks=dict(Counter(c['state'] for l in lessons for c in l['roomChecks'])),
        missingTimes=sum(l['scope']=='main' and not l['start'] for l in lessons),
        extraWordRecords=len(doc_extra),offsetScores=offset_scores)
    data=dict(days=DAYS, slots={str(k):v for k,v in slots.items()}, classes=sorted({l['className'] for l in lessons}, key=lambda c:(int(re.match(r'\d+',c)[0]),c)),
        rooms=sorted(rooms),lessons=lessons,occupancy=occupancy,issues=issues,stats=stats,
        metadata=dict(period='I полугодие 2026–2027',shift2Offset=7,shift2Mapping='inferred',
            notice='Базовое недельное расписание без замен. Время II смены сопоставлено по совпадениям класса и кабинета; требует подтверждения.'))
    (ROOT/'data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    (ROOT/'dist'/'data.js').write_text('window.SCHEDULE_DATA='+json.dumps(data,ensure_ascii=False)+';')
    with (ROOT/'занятия.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['День','Класс','Смена','Урок','Начало','Конец','Предмет','Кабинеты','Учителя','Область','Источник'])
        for l in lessons:w.writerow([DAYS[l['day']],l['className'],l['shift'],l['lesson'],l['start'],l['end'],l['subject'],', '.join(l['rooms']),', '.join(l['teachers']),l['scope'],l['source']])
    with (ROOT/'сверка.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['kind','lesson','text','word','source']);w.writeheader();w.writerows(issues)
    (ROOT/'сверка.md').write_text('# Сверка расписания\n\n'+json.dumps(stats,ensure_ascii=False,indent=2)+'\n\nВремя второй смены пока выведено из соответствий между файлами (урок + 7 в графике Word). Не утверждено пользователем. Уроки вне 13 интервалов Word оставлены без времени.\n\nЗаписи Word без соответствия в Excel сохранены отдельно и учитываются в занятости. Пустое поле не доказывает фактическую доступность кабинета. При отсутствии совпадения учитель не переносится автоматически. Для ЦДО исходные записи сохранены с областью cdo, из пользовательского просмотра исключены.\n\nПервые расхождения:\n\n'+'\n'.join('- '+i['kind']+': '+i['text']+(' / Word: '+i.get('word','') if i.get('word') else '') for i in issues[:20]))
    report = ['# Что требует проверки', '',
        f"Сведены {stats['classes']} классов, {stats['rooms']} помещений, {stats['lessons']} записей занятий. Из просмотра исключены 48 записей ЦДО. Исходные файлы сохранены без изменений.", '',
        '## Разные классы в одном кабинете и временном слоте', '',
        'Эти записи требуют проверки руководителем. Они не исправлены автоматически.']
    report += ['\n- '+i['text']+'\n  - Word: '+i['word']+'\n  - '+i['source'] for i in issues if i['kind']=='В Word указан другой класс']
    report += ['', '## Неустановленное время', '',
        'Правило II смены «номер урока + 7» даёт 424 совпадения класса и кабинета. Нулевой урок — 13:25–14:05, первый — 13:45–14:25. Это вывод из файлов, который нужно подтвердить. Для седьмого урока II смены интервал в Word отсутствует.']
    report += ['- '+i['text']+' ('+i['source']+')' for i in issues if i['kind']=='Время не установлено']
    report += ['', '## Неполные сведения', '',
        '- Кабинеты 210 и 307 встречаются в Excel, но отсутствуют в графике Word.',
        '- В 73 сопоставлениях кабинет–урок Excel содержит занятие, а в Word пусто. Полный перечень — в сверка.csv.',
        '- В 10 сопоставлениях Word содержит запись без класса; учитель автоматически не перенесён.',
        '- 186 записей Word не имеют точного соответствия в Excel: начальные классы, дополнительные занятия, неполные записи и расхождения. Они сохранены и учитываются в занятости.',
        '', '## Правила расчёта', '',
        'Допустимые пересечения смен сохранены. При расхождении учитываются оба источника. Moodle не занимает физический кабинет. Для занятий без времени кабинет получает пометку «Проверить время». Ежедневные замены не предоставлены.']
    (ROOT/'проверить.md').write_text('\n'.join(report)+'\n')
    html=(ROOT/'dist'/'index.html').read_text()
    for filename in ['data.js','maps.js','map-references.js','app.js']:
        code=(ROOT/'dist'/filename).read_text().replace('</script','<\\/script')
        html=html.replace(f'<script src="{filename}"></script>', '<script>'+code+'</script>')
    (ROOT/'расписание.html').write_text(html)
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
