#!/usr/bin/env python3
"""独立NBS采样渲染和音区响度表，默认无额外后级增益。"""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave
import numpy as np
from nbs import decode,BASE_PITCH
RATE=44100

class Samples:
    def __init__(self,path):
        data=json.loads(Path(path).read_text())
        if data['schema']!='suno-nbs-soundpack/1':raise ValueError('Unsupported soundpack')
        self.samples={row.get('custom_file',row['id']):row for row in data['samples']};self.cache={}
    def get(self,instrument,key,fine=0):
        identity=(instrument,key,fine)
        if identity not in self.cache:
            if instrument not in self.samples:raise ValueError(f'Missing sample: {instrument}')
            row=self.samples[instrument];pitched=round(RATE*2**((key-45+fine/100)/12))
            result=subprocess.run(['ffmpeg','-v','error','-i','-','-af',f'aresample={RATE},asetrate={pitched},aresample={RATE}','-ac','1','-f','f32le','-'],input=base64.b64decode(row['audio']),capture_output=True,check=True)
            self.cache[identity]=np.frombuffer(result.stdout,dtype='<f4')
        return self.cache[identity]

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('levels');p.add_argument('--pack',required=True);p.add_argument('--instrument',type=int,required=True);p.add_argument('--pitches',type=int,nargs='+',required=True);p.add_argument('-o','--output',required=True)
    p=sub.add_parser('render');p.add_argument('nbs');p.add_argument('--pack',required=True);p.add_argument('-o','--output',required=True);p.add_argument('--profile',choices=['game','nbs'],default='game');p.add_argument('--gain-db',type=float,default=0);p.add_argument('--instrument',type=int);p.add_argument('--layer',type=int)
    args=parser.parse_args();bank=Samples(args.pack);output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    if args.command=='levels':
        if not 0<=args.instrument<16:raise ValueError('Levels table requires a vanilla instrument')
        rows=[]
        for pitch in args.pitches:
            key=pitch-BASE_PITCH[args.instrument]+45
            if not 0<=key<=87:raise ValueError('Pitch exceeds NBS storage range')
            data=bank.get(args.instrument,key);rms=math.sqrt(float(np.sum(data[:round(.4*RATE)].astype(float)**2))/(.4*RATE))
            rows.append(dict(pitch=pitch,key=key,rms_first_400ms=rms,peak=float(np.max(np.abs(data)))))
        output.write_text(json.dumps(rows,indent=2));print(f'Wrote {len(rows)} calibrated pitch levels');return
    song=decode(Path(args.nbs).read_bytes());events=[];frames=math.ceil(song['length']/song['tempo']*RATE)
    for n in song['notes']:
        if args.instrument is not None and n['instrument']!=args.instrument:continue
        if args.layer is not None and n['layer']!=args.layer:continue
        layer=song['layers'][n['layer']];volume=layer['volume']/100*(1 if args.profile=='game' else n['velocity']/100)
        if not volume:continue
        sample=n['instrument'] if n['instrument']<song['vanilla'] else song['customs'][n['instrument']-song['vanilla']]['file']
        data=bank.get(sample,n['key'],0 if args.profile=='game' else n['fine']);start=round(n['tick']/song['tempo']*RATE)
        pan=max(-1,min(1,(layer['pan']-100+(0 if args.profile=='game' else n['pan']-100))/100));angle=(pan+1)*math.pi/4
        events.append((data,start,volume,np.array([math.cos(angle),math.sin(angle)],np.float32)));frames=max(frames,start+len(data))
    if frames>RATE*900:raise ValueError('Render exceeds 15 minute memory limit')
    signal=np.zeros((frames,2),np.float32)
    for data,start,volume,pan in events:signal[start:start+len(data)]+=data[:,None]*volume*pan
    signal*=10**(args.gain_db/20);peak=float(np.max(np.abs(signal))) if frames else 0;clipped=int(np.count_nonzero(np.abs(signal)>=1))
    report=dict(nbs_sha256=hashlib.sha256(Path(args.nbs).read_bytes()).hexdigest(),rendered_from_final_nbs=True,profile=args.profile,post_gain_db=args.gain_db,peak_dbfs=20*math.log10(peak) if peak else None,clipped_samples=clipped,frames=frames,selected_notes=len(events))
    Path(str(output)+'.json').write_text(json.dumps(report,indent=2))
    if clipped:raise ValueError('Clipped output; lower NBS layer levels or explicitly request preview attenuation')
    with wave.open(str(output),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(RATE);wav.writeframes(np.rint(signal*32767).astype('<i2').tobytes())
    print(json.dumps(report))

if __name__=='__main__':main()
