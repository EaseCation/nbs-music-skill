const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),engine=require('web-audio-engine'),{JSDOM}=require('jsdom');
function setup(){
 const root=path.join(__dirname,'../web');let html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 for(const name of ['nbs.js','audio.js','app.js'])html=html.replace(`<script src="${name}"></script>`,`<script>${fs.readFileSync(path.join(root,name),'utf8')}</script>`);
 const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://test.invalid',beforeParse(window){window.TextDecoder=TextDecoder;window.AudioContext=engine.RenderingAudioContext;window.OfflineAudioContext=engine.OfflineAudioContext;window.HTMLCanvasElement.prototype.getContext=()=>({clearRect(){},fillRect(){}});}});
 return dom;
}
test('empty standalone DOM boots with no network or pretend playback',()=>{const dom=setup();try{assert.equal(dom.window.document.querySelector('#play').disabled,true);assert.equal(dom.window.document.querySelector('#tracks').textContent.includes('导入'),true);assert.equal(dom.window.document.querySelectorAll('script[src]').length,0);}finally{dom.window.close();}});
test('loaded songs group correctly and AB preserves seek while resetting solo',async()=>{const dom=setup();try{
 const w=dom.window;await w.eval(`(async()=>{
 const song={title:'Test A',vanilla:16,duration:10,tempo:50,layers:[{name:'lead',volume:80,pan:100},{name:'bass',volume:45,pan:100}],notes:[{time:1,tick:50,instrument:14,key:45,velocity:100,pan:100,fine:0,layer:0},{time:2,tick:100,instrument:1,key:45,velocity:100,pan:100,fine:0,layer:1}]};
 library.push({name:'a.nbs',buffer:new ArrayBuffer(0),song},{name:'b.nbs',buffer:new ArrayBuffer(0),song:{...song,title:'Test B'}});refreshLists();await select(0);await player.seek(3);})();`);
 assert.equal(w.document.querySelectorAll('.track').length,2);assert.equal(w.document.querySelector('#title').textContent,'Test A');
 w.document.querySelector('#compare').value='1';w.document.querySelector('#compare').dispatchEvent(new w.Event('change'));w.document.querySelector('#ab').click();await new Promise(r=>setImmediate(r));
 assert.equal(w.document.querySelector('#title').textContent,'Test B');assert.equal(w.eval('player.current()'),3);
 w.document.querySelector('#group').value='layer';w.document.querySelector('#group').dispatchEvent(new w.Event('change'));await new Promise(r=>setImmediate(r));assert.match(w.document.querySelector('#tracks').textContent,/lead/);
 w.document.querySelector('[aria-label="独奏 lead"]').click();await new Promise(r=>setImmediate(r));assert.equal(w.eval('player.predicate(player.song.notes[1])'),false);
 }finally{dom.window.close();}});
