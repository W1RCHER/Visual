/* Source data is loaded locally; no external API or publication. */
(() => {
 'use strict';
 const d=window.SCHEDULE_DATA, $=id=>document.getElementById(id);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let mode='map', floor=1, selected=null;
 const options=(el,items)=>{el.innerHTML=items.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('');};
 options($('day'),d.days.map((v,i)=>[i,v]));
 options($('class'),d.classes.map(v=>[v,v]));$('class').value='11И';
 options($('room'),[['all','Все кабинеты'],...d.rooms.map(v=>[v,v==='с/з'?'Спортзал':v])]);
 options($('issue'),[['all','Все замечания'],...Array.from(new Set(d.issues.map(x=>x.kind))).map(v=>[v,v])]);
 const dayLessons=()=>d.lessons.filter(l=>l.day===Number($('day').value)&&l.scope!=='cdo');
 const sourceDetails=l=>`<details><summary>Источник и сверка</summary>${esc(l.source)}<br>${esc(l.raw)}${l.roomChecks.map(c=>`<br>${esc(c.room)}: ${esc(c.state==='matched'?'совпадает с Word':c.word.join('; ')||'совпадение не подтверждено')}`).join('')}</details>`;
 function byClass(){
  const ls=dayLessons().filter(l=>l.className===$('class').value).sort((a,b)=>a.lesson-b.lesson);
  $('summary').textContent=`${d.days[Number($('day').value)]} · ${$('class').value} · ${ls.length} занятий`;
  if(!ls.length){$('output').innerHTML='<div class="empty">Для этого класса нет занятий в выбранный день вне ЦДО.</div>';return;}
  $('output').innerHTML=`<div class="tablewrap"><table><thead><tr><th>Урок</th><th>Время</th><th>Предмет</th><th>Кабинеты</th><th>Учитель</th></tr></thead><tbody>${ls.map(l=>`<tr><td>${l.lesson}<div class="meta">${l.shift} смена</div></td><td>${esc(l.start&&l.end?l.start+'–'+l.end:'Не установлено')}${l.shift===2?'<div class="badge">Время требует подтверждения</div>':''}</td><td><div class="subject">${esc(l.subject)}</div>${l.scope==='remote'?'<span class="badge remote">Дистанционно · Moodle</span>':''}${sourceDetails(l)}</td><td>${esc(l.rooms.join(', ')||'—')}${l.roomChecks.some(c=>c.state!=='matched')?'<div class="badge">Есть вопрос при сверке</div>':''}</td><td>${esc(l.teachers.join(', ')||'Не подтверждён')}</td></tr>`).join('')}</tbody></table></div>`;
 }
 function roomEvents(room){
  const ls=dayLessons().filter(l=>l.scope==='main'&&l.rooms.includes(room));
  const events=ls.map(l=>({start:l.start,end:l.end,slot:l.slot,classes:[l.className],subject:l.subject,teachers:l.roomChecks.find(c=>c.room===room)?.teachers||[],source:l.source,raw:l.raw}));
  d.occupancy.filter(o=>o.day===Number($('day').value)&&o.room===room).forEach(o=>{
   const matches=ls.filter(l=>l.slot===o.slot&&o.classes.includes(l.className));
   const remaining=o.classes.filter(c=>!matches.some(l=>l.className===c));
   if(matches.length&&!remaining.length)return;
   events.push({start:o.start,end:o.end,slot:o.slot,classes:remaining,subject:'Запись графика кабинетов',teachers:o.teacher?[o.teacher]:[],source:o.source,raw:o.raw});
  });
  return events;
 }
 function mapState(id){
  const gym=id.startsWith('gym-'),key=gym?'с/з':id,all=roomEvents(key),time=$('time').value;
  const active=time?all.filter(e=>e.start&&e.start<=time&&time<e.end):[];
  const unknown=all.filter(e=>!e.start);
  const state=gym?'check':!d.rooms.includes(id)?'nodata':active.length?'busy':unknown.length?'check':'free';
  return {key,gym,all,active,unknown,state,label:gym?'Зал не уточнён':state==='nodata'?'Нет данных':state==='busy'?'Есть занятия':state==='check'?'Проверить время':'Нет занятий'};
 }
 function detail(id){
  const s=mapState(id),title=id==='gym-big'?'Большой спортзал':id==='gym-small'?'Малый спортзал':'Кабинет '+id;
  const event=e=>`<div class="event"><div class="event-time">${esc(e.start&&e.end?e.start+'–'+e.end:'Время не установлено')}</div><div class="subject">${esc(e.classes.join(', ')||'Класс не указан')}</div><div>${esc(e.subject)}</div>${e.teachers.length?`<div class="meta">${esc(e.teachers.join(', '))}</div>`:''}</div>`;
  return `<h2>${esc(title)}</h2><p><span class="status ${s.state}">${esc(s.label)}</span></p><p class="meta">${esc(d.days[Number($('day').value)])} · ${esc($('time').value)}</p><div class="day-events"><h3>${s.gym?'Общий график спортзалов': 'На выбранное время'}</h3>${s.active.map(event).join('')||`<p class="meta">${s.state==='nodata'?'Сведения отсутствуют.':'Нет занятий.'}</p>`}</div><details class="day-events"><summary>Расписание на день (${s.all.length})</summary>${s.all.sort((a,b)=>a.slot-b.slot).map(event).join('')||'<p class="meta">Записей нет.</p>'}</details>`;
 }
 function byMap(){
  const m=window.SCHOOL_MAPS[floor],old=document.querySelector('.map-scroll'),scroll=old?{left:old.scrollLeft,top:old.scrollTop}:null;
  if(!$('time').value){$('summary').textContent='Выберите время для просмотра занятости';$('output').innerHTML='';return;}
  const mapped=new Set(Object.values(window.SCHOOL_MAPS).flatMap(f=>f.rooms.map(r=>r[0])));
  const unplaced=d.rooms.filter(r=>r!=='с/з'&&!mapped.has(r));
  $('summary').textContent='';
  const rooms=m.rooms.map(([id,x,y,w,h,label])=>{const s=mapState(id),name=label||id;return `<g class="map-room ${s.state} ${s.gym?'gym':''} ${selected===id?'selected':''}" data-map-room="${id}" role="button" tabindex="0" aria-label="${esc(name)}, ${esc(s.label)}" aria-pressed="${selected===id}"><title>${esc(name)} — ${esc(s.label)}</title><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="1"/><text x="${x+w/2}" y="${y+h/2}">${s.gym?`<tspan x="${x+w/2}" dy="-5">С/з</tspan><tspan x="${x+w/2}" dy="12">${id==='gym-big'?'большой':'малый'}</tspan>`:esc(name)}</text></g>`;}).join('');
  const stairs=m.stairs.map(([x,y,w,h])=>`<g aria-label="Лестница"><title>Лестница</title><rect class="stair" x="${x}" y="${y}" width="${w}" height="${h}"/>${Array.from({length:Math.floor(h/3)},(_,i)=>`<line class="step" x1="${x}" x2="${x+w}" y1="${y+3*i}" y2="${y+3*i}"/>`).join('')}</g>`).join('');
  $('output').innerHTML=`<div class="map-layout"><div><div class="map-pane"><div class="map-tools" aria-label="Выбор этажа">${[1,2,3].map(n=>`<button data-floor="${n}" aria-pressed="${floor===n}">${n} этаж</button>`).join('')}</div><div class="map-scroll"><svg class="floor-svg" viewBox="0 0 ${m.view.join(' ')}" role="group" aria-label="План ${floor} этажа, нажимаемые кабинеты"><path class="building" d="${m.outline}"/>${m.walls.map(p=>`<path class="wall" d="${p}"/>`).join('')}${stairs}${rooms}</svg></div></div></div><aside class="room-detail" aria-label="Выбранный кабинет" aria-live="polite"><div class="map-legend"><span><i class="dot busy"></i>Есть занятия</span><span><i class="dot"></i>Нет занятий</span><span><i class="dot check"></i>Нужно уточнение</span><span><i class="dot nodata"></i>Нет данных</span></div>${selected?detail(selected):'<h2>Выберите кабинет</h2><p class="meta">Нажмите на номер помещения: здесь появятся занятия, классы, учителя и расписание на день.</p>'}</aside></div>`;
  const sc=document.querySelector('.map-scroll');if(scroll){sc.scrollLeft=scroll.left;sc.scrollTop=scroll.top;}
 }
 function byRooms(){
  const time=$('time').value;
  if(!time){$('summary').textContent='Укажите время';$('output').innerHTML='';return;}
  const cards=d.rooms.filter(r=>$('room').value==='all'||r===$('room').value).map(room=>{
   const all=roomEvents(room),active=all.filter(e=>e.start&&e.start<=time&&time<e.end),unknown=all.filter(e=>!e.start),state=active.length?'busy':unknown.length?'check':'free';
   return {room,all,active,unknown,state};
  }).filter(c=>$('status').value==='all'||c.state===$('status').value);
  $('summary').textContent=`${d.days[Number($('day').value)]} · ${time} · Показано помещений: ${cards.length}`;
  $('output').innerHTML=cards.length?`<div class="grid">${cards.map(c=>`<article class="room"><div class="roomtop"><strong><button data-room="${esc(c.room)}">${esc(c.room==='с/з'?'Спортзал':c.room)}</button></strong><span class="status ${c.state}">${c.state==='busy'?'Есть занятия':c.state==='check'?'Проверить время':'Нет занятий'}</span></div>${c.active.map(e=>`<div class="event"><div class="subject">${esc(e.classes.join(', ')||'Класс не указан')}</div><div>${esc(e.subject)}</div><div class="meta">${esc(e.start)}–${esc(e.end)} · ${esc(e.teachers.join(', ')||'Учитель не подтверждён')}</div><details><summary>Исходная запись</summary>${esc(e.source)}<br>${esc(e.raw)}</details></div>`).join('')}${c.unknown.length?'<div class="badge">Есть занятие без установленного времени</div>':''}${!c.active.length?'<p class="meta">В выбранный момент нет подтверждённой записи о занятии.</p>':''}<details><summary>Все записи на день (${c.all.length})</summary>${c.all.sort((a,b)=>a.slot-b.slot).map(e=>`<p>${esc(e.start||'Время неизвестно')} · ${esc(e.classes.join(', ')||e.raw)} · ${esc(e.subject)}<br>${esc(e.source)}</p>`).join('')||'Записей нет'}</details></article>`).join('')}</div>`:'<div class="empty">Нет кабинетов по выбранным условиям.</div>';
 }
 function checks(){
  const ids=new Set(dayLessons().map(l=>l.id));const rows=d.issues.filter(i=>ids.has(i.lesson)&&($('issue').value==='all'||i.kind===$('issue').value));
  $('summary').textContent=`${d.days[Number($('day').value)]} · ${rows.length} замечаний. Это вопросы для проверки, исходники не исправлены.`;
  $('output').innerHTML=`<div class="checks meta">Сопоставление II смены: урок 0 → 13:25; урок 1 → 13:45. Этот вариант даёт ${d.stats.offsetScores['7']} совпадения класса и кабинета. Время 7-го урока II смены в Word отсутствует.</div><div class="tablewrap"><table><thead><tr><th>Проверка</th><th>Excel</th><th>Word</th></tr></thead><tbody>${rows.map(i=>`<tr><td>${esc(i.kind)}</td><td>${esc(i.text)}<div class="meta">${esc(i.source)}</div></td><td>${esc(i.word||'Нет соответствующей записи')}</td></tr>`).join('')||'<tr><td colspan="3">Нет замечаний этого типа.</td></tr>'}</tbody></table></div>`;
 }
 function render(){
  document.body.dataset.mode=mode;
  $('class-wrap').hidden=mode!=='class';$('time-wrap').hidden=!['rooms','map'].includes(mode);for(const id of ['room-wrap','status-wrap'])$(id).hidden=mode!=='rooms';$('issue-wrap').hidden=mode!=='checks';
  document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
  ({map:byMap,class:byClass,rooms:byRooms,checks})[mode]();
 }
 document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;render();});
 for(const id of ['day','class','room','time','status','issue'])$(id).addEventListener('change',render);
 $('output').addEventListener('click',e=>{
  const room=e.target.closest('[data-map-room]');if(room){selected=room.dataset.mapRoom;render();return;}
  const f=e.target.closest('[data-floor]');if(f){floor=Number(f.dataset.floor);selected=null;render();return;}
  const b=e.target.closest('[data-room]');if(b){$('room').value=b.dataset.room;render();}
 });
 $('output').addEventListener('keydown',e=>{const r=e.target.closest('.map-room');if(r&&(e.key==='Enter'||e.key===' ')){e.preventDefault();const id=r.dataset.mapRoom;selected=id;render();document.querySelector(`[data-map-room="${id}"]`)?.focus();}});
 render();
})();
