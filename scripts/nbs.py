"""NBS 读取、力度分层编码与可审计比较；不依赖项目目录。"""
import io
import math
import struct
from collections import Counter
from pathlib import Path

NAMES = ['harp','bassattack','bd','snare','hat','guitar','flute','bell','icechime','xylobone','iron_xylophone','cow_bell','didgeridoo','bit','banjo','pling']
BASE_PITCH = [66,42,66,66,66,54,78,90,90,90,66,78,42,66,66,66]

def decode(data):
    stream = io.BytesIO(data)
    def read(fmt):
        size = struct.calcsize('<'+fmt)
        raw = stream.read(size)
        if len(raw) != size: raise ValueError('Truncated NBS')
        result = struct.unpack('<'+fmt, raw)
        return result[0] if len(result)==1 else result
    def string():
        size = read('i')
        if size < 0 or size > len(data)-stream.tell(): raise ValueError('Invalid NBS string length')
        return stream.read(size).decode('utf-8', errors='replace')
    length = read('H'); version = 0; vanilla = 10
    if length == 0:
        version, vanilla = read('BB')
        if not 1 <= version <= 5: raise ValueError('Unsupported NBS version')
        length = read('H') if version >= 3 else 0
    height = read('H')
    title, author, original_author, description = [string() for _ in range(4)]
    tempo = read('H')/100
    if tempo <= 0: raise ValueError('Invalid NBS tempo')
    read('BBB'); read('iiiii'); source = string()
    loop, loop_count, loop_start = read('BBH') if version >= 4 else (0,0,0)
    notes = []; tick = -1
    while True:
        jump = read('H')
        if not jump: break
        tick += jump; layer = -1
        while True:
            jump = read('H')
            if not jump: break
            layer += jump
            instrument, key = read('BB')
            velocity, pan, fine = read('BBh') if version >= 4 else (100,100,0)
            if layer >= height or key > 87 or velocity > 100 or pan > 200: raise ValueError('Invalid NBS note')
            notes.append(dict(tick=tick,layer=layer,instrument=instrument,key=key,velocity=velocity,pan=pan,fine=fine))
    layers = []
    for _ in range(height):
        name = string(); locked = read('B') if version >= 4 else 0
        volume = read('B'); pan = read('B') if version >= 2 else 100
        if volume > 100 or pan > 200: raise ValueError('Invalid NBS layer')
        layers.append(dict(name=name,locked=locked,volume=volume,pan=pan))
    customs = []
    count = read('B')
    for _ in range(count):
        name, file = string(), string(); key, press = read('BB')
        customs.append(dict(name=name,file=file,key=key,press=press))
    if any(n['instrument'] >= vanilla+count for n in notes): raise ValueError('Undefined NBS instrument')
    return dict(version=version,vanilla=vanilla,length=max(length,tick+1),tempo=tempo,title=title,author=author,original_author=original_author,description=description,source=source,loop=loop,loop_count=loop_count,loop_start=loop_start,layers=layers,notes=notes,customs=customs)

def encode(arrangement, title='', profile='game', tps=50):
    if profile not in ('game','nbs'): raise ValueError('Unknown playback profile')
    if not 0 < tps <= 655.35: raise ValueError('Invalid tick rate')
    events = arrangement['events']; notes=[]; layers=[]; buckets={}; occupied=set(); sidecar=[]
    for index, e in enumerate(events):
        instrument=int(e['instrument']); pitch=float(e['pitch']); time=float(e['time'])
        volume=int(e['volume']); pan=int(e.get('pan',100))
        if not all(math.isfinite(x) for x in (pitch,time)) or time<0: raise ValueError('Invalid event timing or pitch')
        if not 0<=instrument<16 or not 0<=volume<=100 or not 0<=pan<=200: raise ValueError('Invalid event instrument, volume or pan')
        key=round(pitch-BASE_PITCH[instrument]+45); fine=round((pitch-BASE_PITCH[instrument]+45-key)*100)
        if not 0<=key<=87: raise ValueError('Pitch exceeds NBS storage range; do not fold octaves')
        if profile=='game' and fine: raise ValueError('Game profile does not support fine pitch')
        tick=round(time*tps)
        if tick>65534: raise ValueError('Song exceeds NBS v5 tick range; lower tick rate')
        group=(str(e.get('source','')),str(e.get('role','unclassified')),instrument,volume if profile=='game' else 100,pan)
        candidates=buckets.setdefault(group,[])
        layer=next((i for i in candidates if (tick,i) not in occupied),None)
        if layer is None:
            layer=len(layers); candidates.append(layer)
            layers.append(dict(name=f'L{layer:04d}_I{instrument:02d}_V{group[3]:03d}',volume=group[3],pan=pan))
        occupied.add((tick,layer))
        notes.append(dict(tick=tick,layer=layer,instrument=instrument,key=key,velocity=100 if profile=='game' else volume,pan=100,fine=fine))
        sidecar.append({**e,'id':e.get('id',str(index)),'tick':tick,'layer':layer,'key':key})
    if len(layers)>65535: raise ValueError('Too many NBS layers')
    duration=float(arrangement.get('duration',max((e['time'] for e in events),default=0)+2))
    length=max(math.ceil(duration*tps),max((n['tick']+1 for n in notes),default=0))
    if length>65535: raise ValueError('Song exceeds NBS v5 length range')
    stream=io.BytesIO()
    def put(fmt,*values):stream.write(struct.pack('<'+fmt,*values))
    def string(text):
        raw=text.encode('ascii' if profile=='game' else 'utf-8');put('i',len(raw));stream.write(raw)
    put('HBBHH',0,5,16,length,len(layers))
    for text in (title,'NBS Music Skill',arrangement.get('original_author',''),'Layer-volume dynamics; no sustain emulation'):string(text)
    put('HBBBiiiii',round(tps*100),0,10,4,0,0,0,len(notes),0);string('');put('BBH',0,0,0)
    last_tick=-1;last_layer=-1
    for n in sorted(notes,key=lambda n:(n['tick'],n['layer'])):
        if n['tick']!=last_tick:
            if last_tick>=0:put('H',0)
            put('H',n['tick']-last_tick);last_tick=n['tick'];last_layer=-1
        put('HBBBBh',n['layer']-last_layer,n['instrument'],n['key'],n['velocity'],n['pan'],n['fine']);last_layer=n['layer']
    if notes:put('H',0)
    put('H',0)
    for layer in layers:string(layer['name']);put('BBB',0,layer['volume'],layer['pan'])
    put('B',0)
    data=stream.getvalue();song=decode(data)
    assert song['notes']==sorted(notes,key=lambda n:(n['tick'],n['layer']))
    return data,dict(profile=profile,tempo=tps,duration=length/tps,events=sidecar,max_timing_error_ms=max((abs(e['time']-e['tick']/tps)*1000 for e in sidecar),default=0))

def canonical(song):
    return Counter((round(n['tick']/song['tempo'],6),n['instrument'],n['key'],n['fine'],n['velocity'],n['pan'],song['layers'][n['layer']]['volume'],song['layers'][n['layer']]['pan']) for n in song['notes'])

def audit(song):
    groups=Counter((n['tick'],n['instrument'],n['key'],n['fine']) for n in song['notes'] if song['layers'][n['layer']]['volume'] and n['velocity'])
    return dict(title=song['title'],version=song['version'],notes=len(song['notes']),layers=len(song['layers']),tempo=song['tempo'],duration=song['length']/song['tempo'],custom_instruments=len(song['customs']),duplicate_groups=[dict(tick=k[0],instrument=k[1],key=k[2],fine=k[3],count=v) for k,v in groups.items() if v>1],max_layer_volume=max((l['volume'] for l in song['layers']),default=0))
