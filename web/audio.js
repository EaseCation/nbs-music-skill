/* 固定采样自然衰减；不以MIDI时值截断或延长音符。 */
(function(root){
'use strict';
function bytes(encoded){return Uint8Array.from(atob(encoded),c=>c.charCodeAt(0)).buffer;}
class Player{
 constructor(){this.context=null;this.bank=new Map();this.song=null;this.position=0;this.playing=false;this.volume=1;this.profile='game';this.predicate=()=>true;this.active=new Set();this.timer=null;this.generation=0;}
 async contextReady(){if(!this.context){this.context=new AudioContext();this.master=this.context.createGain();this.master.connect(this.context.destination);}await this.context.resume();return this.context;}
 async loadPack(pack){
  const ctx=await this.contextReady();if(pack.schema!=='suno-nbs-soundpack/1')throw Error('Unsupported soundpack');
  const bank=new Map();for(const s of pack.samples){if(s.audio.length>30000000)throw Error('Sample exceeds size limit');const buffer=await ctx.decodeAudioData(bytes(s.audio));bank.set(s.custom_file||s.id,buffer);}
  this.pause();this.bank=bank;if(this.song)this.extendTail(this.song);
 }
 sample(song,n){return n.instrument<song.vanilla?this.bank.get(n.instrument):this.bank.get(song.customs[n.instrument-song.vanilla]?.file);}
 check(song,predicate){const missing=new Set();for(const n of song.notes)if(predicate(n)&&!this.sample(song,n))missing.add(NBS.name(song,n.instrument));if(missing.size)throw Error('Missing samples: '+[...missing].join(', '));}
 current(){return this.playing?Math.min(this.song.duration,this.context.currentTime-this.started):this.position;}
 pause(invalidate=true){if(invalidate)this.generation++;if(this.playing)this.position=this.current();this.playing=false;clearInterval(this.timer);for(const source of this.active){try{source.stop();}catch(error){if(error.name!=='InvalidStateError')throw error;}}this.active.clear();}
 setSong(song,keep=false){const position=keep?this.current():0;this.pause();this.song=song;this.extendTail(song);this.position=Math.min(position,song.duration);}
 extendTail(song){for(const n of song.notes){const sample=this.sample(song,n);if(sample)song.duration=Math.max(song.duration,n.time+sample.duration/NBS.effective(song,n,this.profile).rate);}}
 create(ctx,destination,song,n,when,offset,profile){
  const sample=this.sample(song,n),v=NBS.effective(song,n,profile);if(!sample||!v.gain)return null;
  const consumed=offset*v.rate;if(consumed>=sample.duration)return null;
  const source=ctx.createBufferSource();source.buffer=sample;source.playbackRate.value=v.rate;
  const gain=ctx.createGain();gain.gain.value=v.gain;const pan=ctx.createStereoPanner();pan.pan.value=v.pan;
  source.connect(gain);gain.connect(pan);pan.connect(destination);
  source.onended=()=>{this.active.delete(source);source.disconnect();gain.disconnect();pan.disconnect();};
  source.start(when,consumed);return source;
 }
 async play(){
  if(!this.song)throw Error('No NBS loaded');const token=++this.generation;await this.contextReady();if(token!==this.generation)return;
  this.check(this.song,this.predicate);this.pause(false);if(this.position>=this.song.duration)this.position=0;
  this.master.gain.value=this.volume;this.started=this.context.currentTime-this.position;this.playing=true;
  this.queue=this.song.notes.filter(this.predicate);this.index=0;
  while(this.index<this.queue.length&&this.queue[this.index].time<this.position){const n=this.queue[this.index++];const src=this.create(this.context,this.master,this.song,n,this.context.currentTime,this.position-n.time,this.profile);if(src)this.active.add(src);}
  const schedule=()=>{const now=this.current();while(this.index<this.queue.length&&this.queue[this.index].time<=now+.15){const n=this.queue[this.index++];const source=this.create(this.context,this.master,this.song,n,Math.max(this.context.currentTime,this.started+n.time),Math.max(0,now-n.time),this.profile);if(source)this.active.add(source);}if(now>=this.song.duration){this.pause();this.position=this.song.duration;}};
  schedule();this.timer=setInterval(schedule,40);
 }
 async seek(time){const playing=this.playing;this.pause();this.position=Math.max(0,Math.min(time,this.song.duration));if(playing)await this.play();}
 async filter(predicate){const playing=this.playing;this.pause();this.predicate=predicate;if(playing)await this.play();}
 async render(){
  if(!this.song)throw Error('No NBS loaded');this.check(this.song,this.predicate);
  const song=this.song,rate=44100;let duration=song.duration;
  for(const n of song.notes)if(this.predicate(n)){const s=this.sample(song,n);duration=Math.max(duration,n.time+s.duration/NBS.effective(song,n,this.profile).rate);}
  if(duration>900)throw Error('Offline render exceeds 15 minute memory limit');
  const ctx=new OfflineAudioContext(2,Math.ceil(duration*rate),rate),master=ctx.createGain();master.gain.value=this.volume;master.connect(ctx.destination);
  for(const n of song.notes)if(this.predicate(n))this.create(ctx,master,song,n,n.time,0,this.profile);
  const buffer=await ctx.startRendering();let peak=0,clipped=0;
  for(let channel=0;channel<2;channel++)for(const value of buffer.getChannelData(channel)){peak=Math.max(peak,Math.abs(value));if(Math.abs(value)>=1)clipped++;}
  return {buffer,peak,clipped};
 }
}
function wav(buffer){
 const channels=buffer.numberOfChannels,frames=buffer.length,out=new ArrayBuffer(44+frames*channels*2),view=new DataView(out);
 function str(p,s){for(let i=0;i<s.length;i++)view.setUint8(p+i,s.charCodeAt(i));}
 str(0,'RIFF');view.setUint32(4,out.byteLength-8,true);str(8,'WAVE');str(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,channels,true);view.setUint32(24,buffer.sampleRate,true);view.setUint32(28,buffer.sampleRate*channels*2,true);view.setUint16(32,channels*2,true);view.setUint16(34,16,true);str(36,'data');view.setUint32(40,out.byteLength-44,true);
 const data=Array.from({length:channels},(_,c)=>buffer.getChannelData(c));let pos=44;for(let i=0;i<frames;i++)for(let c=0;c<channels;c++){const v=Math.max(-1,Math.min(1,data[c][i]));view.setInt16(pos,Math.round(v*(v<0?32768:32767)),true);pos+=2;}return new Blob([out],{type:'audio/wav'});
}
root.NBSAudio={Player,bytes,wav};
})(globalThis);
