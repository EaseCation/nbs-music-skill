/* 本地文件驱动的播放器，DOM文本使用textContent避免曲名成为HTML。 */
'use strict';
const $=id=>document.getElementById(id),player=new NBSAudio.Player(),library=[];
let selected=-1,groupType='instrument',solo=new Set(),muted=new Set(),rows=[],pair=null,busy=false;
const format=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
function status(text,error=false){$('status').textContent=text;$('status').hidden=!text;$('status').classList.toggle('error',error);}
function attempt(fn){return async(...args)=>{try{await fn(...args);}catch(error){status(error.message,true);}};}
function option(value,text){const el=document.createElement('option');el.value=value;el.textContent=text;return el;}
function groupId(n){return groupType==='layer'?String(n.layer):groupType==='role'?(n.role||'未标注'):String(n.instrument);}
function predicate(n){const id=groupId(n);return (!solo.size||solo.has(id))&&!muted.has(id);}
function enable(){const loaded=selected>=0;$('play').disabled=!loaded||!player.bank.size;$('download').disabled=!loaded;$('export').disabled=!loaded||!player.bank.size;$('ab').disabled=!loaded||$('compare').value==='';}
function refreshLists(){
 $('songs').replaceChildren(...library.map((x,i)=>option(i,x.name)));$('compare').replaceChildren(option('','未选择'),...library.map((x,i)=>option(i,x.name)));
 $('songs').value=String(selected);renderSongList();
}
function renderSongList(){
 $('song-count').textContent=`曲目 / ${String(library.length).padStart(2,'0')}`;
 $('song-list').replaceChildren(...library.map((item,index)=>{
  const button=document.createElement('button');button.className='song'+(index===selected?' active':'');button.setAttribute('aria-current',index===selected?'true':'false');
  const disc=document.createElement('span');disc.className='disc';disc.setAttribute('aria-hidden','true');
  const body=document.createElement('span'),name=document.createElement('b'),detail=document.createElement('small');name.textContent=item.song.title||item.name;
  detail.textContent=`${String(index+1).padStart(2,'0')} · ${format(item.song.duration)} · ${new Set(item.song.notes.map(n=>n.instrument)).size} 种音色`;
  body.append(name,detail);button.append(disc,body);button.onclick=attempt(async()=>{pair=null;await select(index);});return button;
 }));
}
function renderModes(){
 if(!player.song)return;const choices=[{id:null,name:'音符盒全曲'},...NBS.groups(player.song,'instrument')];
 $('modes').replaceChildren(...choices.map(row=>{
  const button=document.createElement('button');button.textContent=row.name;
  const active=row.id===null?!solo.size&&!muted.size:groupType==='instrument'&&solo.size===1&&solo.has(row.id)&&!muted.size;
  button.className=active?'active':'';button.setAttribute('aria-pressed',String(active));
  button.onclick=attempt(async()=>{groupType='instrument';$('group').value=groupType;solo.clear();muted.clear();if(row.id!==null)solo.add(row.id);await player.filter(predicate);renderTracks();draw();});return button;
 }));
 const activeRows=NBS.groups(player.song,groupType).filter(row=>row.notes.some(predicate));
 $('listening').textContent=!solo.size&&!muted.size?'音符盒全曲':activeRows.length===1?`只听 · ${activeRows[0].name}`:activeRows.length?`混音 · ${activeRows.length} 个声部`:'全部静音';
}
async function select(index,keep=false){
 if(!library[index])return;const running=player.playing;selected=index;solo.clear();muted.clear();player.setSong(library[index].song,keep);player.predicate=predicate;
 $('songs').value=String(index);$('title').textContent=library[index].song.title||library[index].name;
 const song=player.song;$('duration').textContent=format(song.duration);$('instruments').textContent=new Set(song.notes.map(n=>n.instrument)).size+' 种';$('notes').textContent=song.notes.length.toLocaleString();$('layers').textContent=song.layers.length.toLocaleString();$('track-number').textContent=`${String(index+1).padStart(2,'0')} / ${String(library.length).padStart(2,'0')}`;renderSongList();
 const hasRoles=song.notes.some(n=>n.role);$('group').replaceChildren(option('instrument','按音色'),option('layer','按 NBS 层'),...(hasRoles?[option('role','按语义声部')]:[]));
 if(groupType==='role'&&!hasRoles)groupType='instrument';$('group').value=groupType;
 $('seek').max=song.duration;$('peak').textContent='';renderTracks();enable();draw();if(running)await player.play();
}
function renderTracks(){
 if(!player.song)return;rows=NBS.groups(player.song,groupType);const query=$('search').value.toLowerCase(),elements=[];
 const focused=document.activeElement?.dataset.control;
 for(const row of rows){if(!row.name.toLowerCase().includes(query))continue;
  const audible=row.notes.some(predicate),only=solo.size===1&&solo.has(row.id);
  const el=document.createElement('div');el.className='track'+(audible?'':' inactive');const label=document.createElement('span');label.className='track-name';label.textContent=row.name;
  const info=document.createElement('small');info.textContent=`${row.notes.length} 音 · ${row.volumes.reduce((a,b)=>Math.min(a,b),100)}–${row.volumes.reduce((a,b)=>Math.max(a,b),0)}%`;
  const single=document.createElement('button');single.textContent=only?'恢复全曲':'只听';single.setAttribute('aria-label',`独奏 ${row.name}`);single.setAttribute('aria-pressed',String(only));single.dataset.control='solo:'+row.id;
  const include=document.createElement('input');include.type='checkbox';include.checked=audible;include.setAttribute('aria-label',`参与播放 ${row.name}`);include.dataset.control='include:'+row.id;
  single.onclick=attempt(async()=>{solo.clear();muted.clear();if(!only)solo.add(row.id);await player.filter(predicate);renderTracks();draw();});
  include.onchange=attempt(async()=>{
   if(solo.size){muted=new Set(rows.filter(r=>!solo.has(r.id)).map(r=>r.id));solo.clear();}
   include.checked?muted.delete(row.id):muted.add(row.id);await player.filter(predicate);renderTracks();draw();
  });
  el.append(label,info,include,single);elements.push(el);
 }
 $('tracks').replaceChildren(...elements);renderModes();$('peak').textContent='';
 if(focused){const next=[...$('tracks').querySelectorAll('[data-control]')].find(el=>el.dataset.control===focused);next?.focus({preventScroll:true});}
}
function draw(){
 const canvas=$('roll'),ctx=canvas.getContext('2d');if(!player.song){ctx.clearRect(0,0,canvas.width,canvas.height);return;}
 const song=player.song,lanes=NBS.groups(song,'instrument'),left=140,right=canvas.width-14,width=right-left;
 canvas.height=lanes.length*29+30;ctx.clearRect(0,0,canvas.width,canvas.height);ctx.font='13px sans-serif';
 for(let i=0;i<lanes.length;i++){
  const lane=lanes[i],top=i*29+7;ctx.fillStyle='#829078';ctx.fillText(lane.name,0,top+13);ctx.fillStyle='#f2f2e7';ctx.fillRect(left,top,width,18);
  const cells=new Map();for(const n of lane.notes){if(!predicate(n))continue;const cell=Math.floor(n.time*4);cells.set(cell,(cells.get(cell)||0)+1);}
  for(const [cell,count] of cells){ctx.fillStyle=`rgba(116,143,89,${Math.min(.85,.25+count*.13)})`;ctx.fillRect(left+cell/4/song.duration*width,top,Math.max(2,width/song.duration*.25-1),18);}
 }
 ctx.fillStyle='#36553c';ctx.fillRect(left+player.current()/song.duration*width,0,2,lanes.length*29+5);
 ctx.fillStyle='#9aa28e';ctx.fillText('0:00',left,canvas.height-3);ctx.fillText(format(song.duration),right-38,canvas.height-3);
}
async function sha(buffer){
 if(!crypto.subtle)throw Error('Metadata verification requires a secure local browser context');
 return [...new Uint8Array(await crypto.subtle.digest('SHA-256',buffer))].map(x=>x.toString(16).padStart(2,'0')).join('');
}
async function attachMeta(item,meta){
 if(meta.nbs_sha256!==await sha(item.buffer))throw Error('Sidecar hash does not match NBS');
 const lookup=new Map(meta.events.map(e=>[`${e.tick}:${e.layer}`,e]));for(const n of item.song.notes){const e=lookup.get(`${n.tick}:${n.layer}`);if(e)n.role=e.role;}
}
async function add(name,buffer,meta){
 if(buffer.byteLength>20*1024*1024)throw Error('NBS exceeds 20 MB limit');
 const song=NBS.parse(buffer);if(song.notes.length>150000)throw Error('NBS exceeds preview note limit');
 const item={name,buffer,song};if(meta)await attachMeta(item,meta);library.push(item);return library.length-1;
}
$('files').onchange=attempt(async event=>{
 const files=[...event.target.files];let last=-1;const errors=[];
 for(const file of files.filter(f=>f.name.toLowerCase().endsWith('.nbs'))){try{last=await add(file.name,await file.arrayBuffer());}catch(error){errors.push(`${file.name}: ${error.message}`);}}
 for(const file of files.filter(f=>f.name.toLowerCase().endsWith('.json'))){try{const meta=JSON.parse(await file.text());const item=library.findLast(x=>x.name+'.json'===file.name);if(!item)throw Error('Matching NBS file not loaded');await attachMeta(item,meta);}catch(error){errors.push(`${file.name}: ${error.message}`);}}
 refreshLists();if(last>=0)await select(last);else if(selected>=0)await select(selected,true);enable();status(errors.length?errors.join(' / '):'已导入。所有处理均在浏览器本地完成。',!!errors.length);event.target.value='';
});
$('pack').onchange=attempt(async event=>{const file=event.target.files[0];if(!file)return;await player.loadPack(JSON.parse(await file.text()));$('pack-state').textContent=`已载入 ${player.bank.size} 个本地采样`;enable();status('音色包已载入。');});
$('songs').onchange=attempt(async()=>{pair=null;await select(Number($('songs').value));});
$('compare').onchange=()=>{pair=null;enable();};
$('ab').onclick=attempt(async()=>{if(!pair)pair=[selected,Number($('compare').value)];if(pair[0]===pair[1])throw Error('Choose a different comparison song');await select(selected===pair[0]?pair[1]:pair[0],true);status(`当前：${library[selected].name} · 保持同一时间位置，声部选择已恢复全部。`);});
$('play').onclick=attempt(async()=>{if(player.playing){player.generation++;player.pause();}else await player.play();});
$('seek').oninput=attempt(async()=>{if(player.song){await player.seek(Number($('seek').value));draw();}});
$('volume').oninput=()=>{player.volume=Number($('volume').value);if(player.master)player.master.gain.value=player.volume;$('volume-value').textContent=Math.round(player.volume*100)+'%';$('peak').textContent='';};
$('profile').onchange=attempt(async()=>{const playing=player.playing;player.pause();player.profile=$('profile').value;if(playing)await player.play();status(player.profile==='game'?'游戏兼容：使用层音量，忽略逐音力度、微调与逐音声像。':'完整 NBS：使用层音量 × 逐音力度，并应用微调与逐音声像。');});
$('group').onchange=attempt(async()=>{groupType=$('group').value;solo.clear();muted.clear();await player.filter(predicate);renderTracks();draw();});
$('reset').onclick=attempt(async()=>{solo.clear();muted.clear();await player.filter(predicate);renderTracks();draw();});
$('search').oninput=renderTracks;
$('roll').onclick=attempt(async event=>{if(!player.song)return;const rect=$('roll').getBoundingClientRect();await player.seek(((event.clientX-rect.left)/rect.width*1200-140)/(1200-154)*player.song.duration);draw();});
function download(blob,name){const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}
$('download').onclick=()=>{if(selected>=0)download(new Blob([library[selected].buffer]),library[selected].name);};
$('export').onclick=attempt(async()=>{
 if(busy)return;busy=true;$('export').disabled=true;const name=library[selected].name.replace(/\.nbs$/i,'');status('正在浏览器内渲染当前声部…');
 try{const result=await player.render();$('peak').textContent=`采样峰值 ${result.peak?(20*Math.log10(result.peak)).toFixed(2):-Infinity} dBFS · ${result.clipped} 个削波采样`;
  if(result.clipped){status('当前组合存在削波，请降低总音量后重新导出；没有自动归一化。',true);return;}
  download(NBSAudio.wav(result.buffer),name+'-selection.wav');status('已在本机生成 WAV，保持当前音量与声部选择。');
 }finally{busy=false;enable();}
});
setInterval(()=>{if(!player.song)return;const time=player.current();$('clock').textContent=`${format(time)} / ${format(player.song.duration)}`;$('seek').value=time;$('play').textContent=player.playing?'Ⅱ':'▶';$('play').setAttribute('aria-label',player.playing?'暂停':'播放');if(player.playing)draw();},100);
attempt(async()=>{
 const boot=window.BOOT||{},pack=boot.pack||window.NBS_SOUNDPACK;if(pack){
  /* 初始解码不自动播放；音频上下文由用户点击后恢复。 */
  const saved=player.contextReady.bind(player);player.contextReady=async()=>{if(!player.context){player.context=new AudioContext();player.master=player.context.createGain();player.master.connect(player.context.destination);}return player.context;};
  await player.loadPack(pack);player.contextReady=saved;$('pack-state').textContent=`已载入 ${player.bank.size} 个 Minecraft 本地采样`;
 }
 for(const item of boot.songs||[])await add(item.name,NBSAudio.bytes(item.data),item.meta);
 if(library.length){refreshLists();await select(0);}enable();
})();
