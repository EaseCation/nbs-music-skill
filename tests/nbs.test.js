const test=require('node:test'),assert=require('node:assert/strict'),NBS=require('../web/nbs.js');
function fixture(version=5){
 const parts=[];const put=(size,value,signed=false)=>{const b=Buffer.alloc(size);signed?b.writeIntLE(value,0,size):b.writeUIntLE(value,0,size);parts.push(b);};
 const text=s=>{const b=Buffer.from(s);put(4,b.length);parts.push(b);};
 if(version===0)put(2,51);else{put(2,0);put(1,version);put(1,16);if(version>=3)put(2,51);}
 put(2,1);['Test','Author','',''].forEach(text);put(2,5000);[0,10,4].forEach(x=>put(1,x));for(let i=0;i<5;i++)put(4,0);text('');if(version>=4){put(1,0);put(1,0);put(2,0);}
 put(2,51);put(2,1);put(1,7);put(1,39);if(version>=4){put(1,40);put(1,120);put(2,25,true);}put(2,0);put(2,0);
 text('Layer');if(version>=4)put(1,0);put(1,75);if(version>=2)put(1,90);put(1,0);
 const b=Buffer.concat(parts);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
}
for(let v=0;v<=5;v++)test(`parse NBS v${v}`,()=>{const s=NBS.parse(fixture(v));assert.equal(s.version,v);assert.equal(s.notes.length,1);assert.equal(s.notes[0].time,1);assert.equal(s.layers[0].volume,75);assert.equal(s.notes[0].velocity,v>=4?40:100);});
test('game versus full profile retains actual dynamics',()=>{const s=NBS.parse(fixture());assert.equal(NBS.effective(s,s.notes[0],'game').gain,.75);assert.ok(Math.abs(NBS.effective(s,s.notes[0],'nbs').gain-.3)<1e-10);assert.notEqual(NBS.effective(s,s.notes[0],'nbs').rate,NBS.effective(s,s.notes[0],'game').rate);});
test('malformed input fails rather than producing a silent song',()=>assert.throws(()=>NBS.parse(fixture().slice(0,20)),/Truncated|Invalid/));
test('grouping and duplicate detection operate on final NBS',()=>{const s=NBS.parse(fixture());s.notes.push({...s.notes[0]});assert.equal(NBS.duplicates(s),1);assert.equal(NBS.groups(s,'instrument')[0].notes.length,2);assert.equal(NBS.groups(s,'layer')[0].name,'Layer');});
