#!/usr/bin/env python3
"""命令行入口；所有输入输出均由参数指定，原始文件保持只读。"""
import argparse
import base64
import hashlib
import io
import wave
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from nbs import NAMES, BASE_PITCH, encode, decode, audit, canonical

ROOT=Path(__file__).resolve().parent.parent

def load(path):return json.loads(Path(path).read_text())
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def extract(args):
    destination=Path(args.output)
    if destination.exists():raise ValueError('Output directory already exists')
    with zipfile.ZipFile(args.zip) as archive:
        files=[x for x in archive.infolist() if not x.is_dir()]
        if sum(x.file_size for x in files)>args.max_gb*1024**3:raise ValueError('Archive exceeds extraction size limit')
        seen=set()
        for info in files:
            path=Path(info.filename)
            if info.filename == 'manifest.json':raise ValueError('ZIP uses reserved manifest path')
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename or (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe ZIP member')
            if info.filename in seen:raise ValueError('Duplicate ZIP path')
            seen.add(info.filename)
        destination.mkdir(parents=True)
        manifest=[]
        for info in files:
            target=destination/info.filename;target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(info) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)
            manifest.append(dict(path=info.filename,bytes=target.stat().st_size,sha256=digest(target)))
        save(destination/'manifest.json',dict(archive_sha256=digest(args.zip),files=manifest))
    print(f'Extracted {len(files)} files')

def inspect(args):
    from midi_reader import inspect_file
    source=Path(args.input);files=[source] if source.is_file() else sorted(p for p in source.rglob('*') if p.suffix.lower() in ('.mid','.midi'))
    if not files:raise ValueError('No MIDI files found')
    records=[];notes=[]
    for path in files:
        record,events=inspect_file(path);record['path']=str(path.resolve());records.append(record);notes.extend(events)
    ids=[n['source_id'] for n in notes]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate MIDI input detected')
    save(args.output,dict(schema='suno-nbs-midi/1',files=records,notes=notes))
    print(json.dumps(dict(files=len(files),notes=len(notes),issues=sum(len(r['issues']) for r in records))))

def matches(note, selector):
    allowed={'source','track','channel','program','pitch_min','pitch_max','time_start','time_end','ids'}
    if set(selector)-allowed:raise ValueError('Unknown rule selector')
    return all(note[k]==selector[k] for k in ('source','track','channel','program') if k in selector) and note['pitch']>=selector.get('pitch_min',-999) and note['pitch']<=selector.get('pitch_max',999) and note['time']>=selector.get('time_start',-1) and note['time']<selector.get('time_end',float('inf')) and ('ids' not in selector or note['source_id'] in selector['ids'])

def arrange(args):
    data=load(args.input);config=load(args.rules);events=[];dispositions={}
    rules=config['rules'];offsets=config.get('offsets',{})
    for n in data['notes']:
        time=n['start']+offsets.get(n['source'],config.get('offset',0));note={**n,'time':time}
        matched=[r for r in rules if matches(note,r['select'])]
        if len(matched)>1:raise ValueError(f"Overlapping routing rules for {n['source_id']}")
        if not matched:
            dispositions[n['source_id']]={'action':'unassigned'};continue
        rule=matched[0]
        if rule.get('exclude'):
            if not rule.get('reason'):raise ValueError('Exclusion requires a reason')
            dispositions[n['source_id']]={'action':'excluded','reason':rule['reason']};continue
        if time<0:raise ValueError('Offset produces negative onset; inspect alignment')
        volume=rule.get('volume')
        if volume is None:volume=round(n['velocity']/127*n['channel_volume']/127*n['expression']/127*100*rule.get('gain',1))
        if not 0<=volume<=100:raise ValueError('Volume exceeds 0..100; adjust gain explicitly')
        events.append(dict(id=n['source_id'],source_ids=[n['source_id']],source=n['source'],role=rule.get('role','unclassified'),time=time,duration=n['duration'],pitch=n['pitch']+rule.get('transpose',0),instrument=rule['instrument'],volume=volume,pan=rule.get('pan',round(n['pan']/127*200))))
        dispositions[n['source_id']]={'action':'kept','reason':rule.get('reason','explicit routing')}
    missing=sum(d['action']=='unassigned' for d in dispositions.values())
    if missing and not args.allow_unassigned:raise ValueError(f'{missing} notes are unassigned; add routing/exclusion rules or use --allow-unassigned for a draft')
    if args.merge_exact:
        combined={}
        for e in events:
            key=(round(e['time']*args.tps),e['instrument'],e['pitch'],e['pan'])
            if key in combined:
                other=combined[key];other['source_ids']+=e['source_ids'];other['volume']=max(other['volume'],e['volume'])
                dispositions[e['id']]={'action':'merged','into':other['id']}
            else:combined[key]=e
        events=list(combined.values())
    duration=max((n['end']+offsets.get(n['source'],config.get('offset',0)) for n in data['notes']),default=0)+config.get('tail',2)
    save(args.output,dict(schema='suno-nbs-arrangement/1',input_sha256=digest(args.input),rules_sha256=digest(args.rules),duration=duration,events=events,dispositions=dispositions,draft=bool(missing)))
    print(json.dumps(dict(events=len(events),unassigned=missing)))

def write(args):
    arrangement=load(args.input)
    if arrangement.get('draft') and not args.allow_draft:raise ValueError('Draft arrangement requires --allow-draft')
    data,sidecar=encode(arrangement,args.title,args.profile,args.tps)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
    sidecar['nbs_sha256']=digest(output);sidecar['title']=args.title
    save(str(output)+'.json',sidecar);print(json.dumps(audit(decode(data))))

def diff(args):
    before=decode(Path(args.before).read_bytes());after=decode(Path(args.after).read_bytes())
    left,right=canonical(before),canonical(after)
    result=dict(before=audit(before),after=audit(after),header_changes={k:[before[k],after[k]] for k in ('tempo','length','title','vanilla','customs') if before[k]!=after[k]},removed=[dict(note=list(k),count=v) for k,v in (left-right).items()],added=[dict(note=list(k),count=v) for k,v in (right-left).items()])
    save(args.output,result)
    print(json.dumps(dict(removed=sum((left-right).values()),added=sum((right-left).values()))))

def patch(args):
    data=load(args.input);changes=load(args.changes);lookup={e['id']:e for e in data['events']}
    if len(lookup)!=len(data['events']):raise ValueError('Duplicate event IDs')
    if len({x['id'] for x in changes})!=len(changes):raise ValueError('Repeated patch ID')
    audit_log=[]
    for change in changes:
        event=lookup[change['id']]
        if not change.get('reason'):raise ValueError('Patch requires evidence/reason')
        for k,v in change['expect'].items():
            if event.get(k)!=v:raise ValueError('Patch precondition failed')
        if set(change['set'])-{'instrument','volume','role','pitch','time','pan'}:raise ValueError('Unsupported patch field')
        before=dict(event);event.update(change['set']);audit_log.append(dict(id=event['id'],before=before,after=dict(event),reason=change['reason']))
    data['revision']=dict(baseline_sha256=digest(args.input),changes=audit_log)
    save(args.output,data);print(f'Patched {len(changes)} explicit events')

def audio(args):
    import numpy as np
    command=['ffmpeg','-v','error','-i',args.input,'-ac','1','-ar','16000','-f','f32le','-']
    result=subprocess.run(command,capture_output=True,check=True);pcm=np.frombuffer(result.stdout,dtype='<f4')
    hop=320;frames=len(pcm)//hop;energy=np.sqrt(np.mean(pcm[:frames*hop].reshape(frames,hop).astype(float)**2,axis=1)) if frames else np.array([])
    measured=subprocess.run(['ffmpeg','-hide_banner','-i',args.input,'-af','loudnorm=I=-18:TP=-1:LRA=11:print_format=json','-f','null','-'],capture_output=True,check=True)
    stderr=measured.stderr.decode();levels,_=json.JSONDecoder().raw_decode(stderr[stderr.rfind('{'):])
    report=dict(sha256=digest(args.input),duration=len(pcm)/16000,levels=levels,window_seconds=.02,rms_windows=energy.tolist())
    if args.midi:
        notes=load(args.midi)['notes'];onset=np.maximum(0,np.diff(energy,prepend=0));scores=[]
        if args.source:notes=[n for n in notes if n['source']==args.source]
        if not notes:raise ValueError('No matching MIDI notes for alignment')
        for shift in range(-100,101):
            indexes=[round(n['start']/.02)+shift for n in notes];indexes=np.array([i for i in indexes if 0<=i<len(onset)],dtype=int)
            scores.append((float(np.sum(onset[indexes]))/max(1,len(notes)),shift*.02))
        report['alignment_candidates']=[dict(offset_seconds=t,score=s) for s,t in sorted(scores,reverse=True)[:8]]
        report['alignment_warning']='Candidate offsets only; inspect matching stems and phrase onsets before applying.'
    save(args.output,report);print(json.dumps({k:v for k,v in report.items() if k!='rms_windows'}))

def focus(args):
    data=load(args.input);events=data['events'];selected=[]
    for e in events:
        if args.start<=e['time']<args.end:
            selected.append({k:e.get(k) for k in ('id','source_ids','time','pitch','instrument','source','role','volume')})
    selected.sort(key=lambda e:(-e['pitch'],e['time']))
    groups={}
    for e in selected:
        key=f"{e['source']} / {e['role']} / {NAMES[e['instrument']]}"
        groups.setdefault(key,[]).append(e['pitch'])
    save(args.output,dict(window=[args.start,args.end],groups={k:dict(notes=len(v),pitch_min=min(v),pitch_max=max(v)) for k,v in groups.items()},notes=selected))
    print(json.dumps(dict(notes=len(selected),groups=len(groups))))

def soundpack(args):
    if args.index:
        index=load(args.index)
        if isinstance(index,list):objects={Path(x['name']).stem:dict(path=Path(x['path']),hash=x['hash']) for x in index}
        else:
            if not args.assets:raise ValueError('--assets is required with a Minecraft asset index')
            objects={Path(k).stem:dict(path=Path(args.assets)/'objects'/v['hash'][:2]/v['hash'],hash=v['hash']) for k,v in index['objects'].items() if '/sounds/note/' in k}
    else:raise ValueError('A local sample index is required')
    samples=[]
    for i,name in enumerate(NAMES):
        obj=objects[name];raw=obj['path'].read_bytes()
        if hashlib.sha1(raw).hexdigest()!=obj['hash']:raise ValueError('Sample SHA-1 mismatch')
        result=subprocess.run(['ffmpeg','-v','error','-i',str(obj['path']),'-ar','44100','-ac','1','-c:a','pcm_s16le','-f','s16le','-'],capture_output=True,check=True)
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(result.stdout)
        samples.append(dict(id=i,name=name,base_pitch=BASE_PITCH[i],sha1=obj['hash'],audio=base64.b64encode(buffer.getvalue()).decode()))
    save(args.output,dict(schema='suno-nbs-soundpack/1',label='Minecraft local samples',samples=samples))
    print(f'Packed {len(samples)} verified local samples')

def build(args):
    pack=load(args.pack) if args.pack else None;songs=[]
    for file in args.nbs:
        path=Path(file);decode(path.read_bytes());sidecar=Path(str(path)+'.json')
        meta=load(sidecar) if sidecar.exists() else None
        if meta and meta.get('nbs_sha256')!=digest(path):raise ValueError('Sidecar does not match NBS')
        songs.append(dict(name=path.name,data=base64.b64encode(path.read_bytes()).decode(),meta=meta))
    initial=json.dumps(dict(pack=pack,songs=songs),ensure_ascii=False).replace('</','<\\/')
    html=(ROOT/'web/index.html').read_text()
    html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(ROOT/'web/style.css').read_text()+'</style>')
    html=html.replace('<script src="nbs.js"></script>','<script>window.BOOT='+initial+';</script>\n<script>'+(ROOT/'web/nbs.js').read_text()+'</script>')
    for name in ('audio.js','app.js'):html=html.replace(f'<script src="{name}"></script>','<script>'+(ROOT/'web'/name).read_text()+'</script>')
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(html)
    print(f'Built standalone player: {output} ({output.stat().st_size} bytes)')

def prompt(args):
    template=(ROOT/'references/prompt-template.txt').read_text()
    print(template.replace('{theme}',args.theme).replace('{arc}',args.arc).replace('{setting}',args.setting))

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('extract');p.add_argument('zip');p.add_argument('-o','--output',required=True);p.add_argument('--max-gb',type=float,default=20);p.set_defaults(run=extract)
    p=sub.add_parser('inspect');p.add_argument('input');p.add_argument('-o','--output',required=True);p.set_defaults(run=inspect)
    p=sub.add_parser('arrange');p.add_argument('input');p.add_argument('--rules',required=True);p.add_argument('-o','--output',required=True);p.add_argument('--allow-unassigned',action='store_true');p.add_argument('--merge-exact',action='store_true');p.add_argument('--tps',type=float,default=50);p.set_defaults(run=arrange)
    p=sub.add_parser('encode');p.add_argument('input');p.add_argument('-o','--output',required=True);p.add_argument('--title',default='Untitled');p.add_argument('--profile',choices=['game','nbs'],default='game');p.add_argument('--tps',type=float,default=50);p.add_argument('--allow-draft',action='store_true');p.set_defaults(run=write)
    p=sub.add_parser('audit');p.add_argument('input');p.set_defaults(run=lambda a:print(json.dumps(audit(decode(Path(a.input).read_bytes())),ensure_ascii=False,indent=2)))
    p=sub.add_parser('diff');p.add_argument('before');p.add_argument('after');p.add_argument('-o','--output',required=True);p.set_defaults(run=diff)
    p=sub.add_parser('patch');p.add_argument('input');p.add_argument('--changes',required=True);p.add_argument('-o','--output',required=True);p.set_defaults(run=patch)
    p=sub.add_parser('audio');p.add_argument('input');p.add_argument('-o','--output',required=True);p.add_argument('--midi');p.add_argument('--source');p.set_defaults(run=audio)
    p=sub.add_parser('focus');p.add_argument('input');p.add_argument('--start',type=float,required=True);p.add_argument('--end',type=float,required=True);p.add_argument('-o','--output',required=True);p.set_defaults(run=focus)
    p=sub.add_parser('soundpack');p.add_argument('--index',required=True);p.add_argument('--assets');p.add_argument('-o','--output',required=True);p.set_defaults(run=soundpack)
    p=sub.add_parser('build-web');p.add_argument('--pack');p.add_argument('--nbs',nargs='*',default=[]);p.add_argument('-o','--output',required=True);p.set_defaults(run=build)
    p=sub.add_parser('prompt');p.add_argument('--theme',required=True);p.add_argument('--arc',default='quiet anticipation, playful growth, warm triumphant return');p.add_argument('--setting',default='a farming game lobby and seasonal award ceremony');p.set_defaults(run=prompt)
    args=parser.parse_args();args.run(args)

if __name__=='__main__':main()
