/* NBS解析与声部索引，不读取网络或本地固定目录。 */
(function(root){
'use strict';
const names=['钢琴','低音提琴','底鼓','小军鼓','点击','吉他','长笛','铃铛','风铃','木琴','铁琴','牛铃','迪吉里杜管','Bit','班卓琴','Pling'];
const bases=[66,42,66,66,66,54,78,90,90,90,66,78,42,66,66,66];
function parse(buffer){
 const view=new DataView(buffer);let pos=0;
 function read(kind,size){if(pos+size>view.byteLength)throw Error('Truncated NBS');const value=view[kind](pos,true);pos+=size;return value;}
 const u8=()=>read('getUint8',1),u16=()=>read('getUint16',2),i16=()=>read('getInt16',2),i32=()=>read('getInt32',4);
 function text(){const size=i32();if(size<0||pos+size>view.byteLength)throw Error('Invalid NBS string length');const value=new TextDecoder().decode(new Uint8Array(buffer,pos,size));pos+=size;return value;}
 let length=u16(),version=0,vanilla=10;
 if(!length){version=u8();vanilla=u8();if(version<1||version>5)throw Error('Unsupported NBS version');length=version>=3?u16():0;}
 const height=u16(),title=text(),author=text(),originalAuthor=text(),description=text(),tempo=u16()/100;
 if(!tempo)throw Error('Invalid NBS tempo');
 u8();u8();u8();for(let i=0;i<5;i++)i32();text();
 const loop=version>=4?{enabled:u8(),count:u8(),start:u16()}:null;
 let tick=-1;const notes=[];
 for(let jump;(jump=u16());){tick+=jump;let layer=-1;
  for(let step;(step=u16());){layer+=step;const instrument=u8(),key=u8(),velocity=version>=4?u8():100,pan=version>=4?u8():100,fine=version>=4?i16():0;
   if(layer>=height||key>87||velocity>100||pan>200)throw Error('Invalid NBS note');
   notes.push({tick,time:tick/tempo,layer,instrument,key,velocity,pan,fine});
  }
 }
 const layers=[];
 for(let i=0;i<height;i++){const name=text(),locked=version>=4?u8():0,volume=u8(),pan=version>=2?u8():100;if(volume>100||pan>200)throw Error('Invalid NBS layer');layers.push({name,locked,volume,pan});}
 const customs=[];const count=u8();for(let i=0;i<count;i++)customs.push({name:text(),file:text(),key:u8(),press:u8()});
 if(notes.some(n=>n.instrument>=vanilla+count))throw Error('Undefined NBS instrument');
 length=Math.max(length,tick+1);
 return {version,vanilla,length,title,author,originalAuthor,description,tempo,loop,layers,notes,customs,duration:length/tempo};
}
function name(song,id){return id<song.vanilla?(names[id]||`音色 ${id}`):(song.customs[id-song.vanilla]?.name||`自定义 ${id}`);}
function effective(song,n,profile){
 const layer=song.layers[n.layer];return {gain:layer.volume/100*(profile==='game'?1:n.velocity/100),pan:Math.max(-1,Math.min(1,(layer.pan-100+(profile==='game'?0:n.pan-100))/100)),rate:2**((n.key-45+(profile==='game'?0:n.fine/100))/12)};
}
function groups(song,type){
 const rows=new Map();for(const n of song.notes){const id=type==='layer'?String(n.layer):type==='role'?(n.role||'未标注'):String(n.instrument);
  if(!rows.has(id))rows.set(id,{id,name:type==='layer'?song.layers[n.layer].name:type==='role'?id:name(song,n.instrument),notes:[],volumes:[]});
  const row=rows.get(id);row.notes.push(n);row.volumes.push(song.layers[n.layer].volume);
 }
 return [...rows.values()];
}
function duplicates(song){const map=new Map();for(const n of song.notes){if(!song.layers[n.layer].volume||!n.velocity)continue;const key=[n.tick,n.instrument,n.key,n.fine].join(':');map.set(key,(map.get(key)||0)+1);}return [...map.values()].filter(v=>v>1).length;}
const api={parse,names,bases,name,effective,groups,duplicates};root.NBS=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
