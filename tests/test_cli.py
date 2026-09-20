"""通过公开命令行验证路由、补丁、归档和交付，而非只测试内部函数。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import mido
ROOT=Path(__file__).resolve().parents[1]

class CliTests(unittest.TestCase):
    def run_cli(self,*args,ok=True):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/toolkit.py'),*map(str,args)],capture_output=True,text=True)
        self.assertEqual(result.returncode==0,ok,result.stderr)
        return result
    def test_full_pipeline_and_guarded_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            r=Path(folder);m=mido.MidiFile();t=mido.MidiTrack();m.tracks.append(t)
            t.extend([mido.Message('note_on',note=84,velocity=80),mido.Message('note_off',note=84,time=480)])
            midi=r/'Song (Synth).mid';m.save(midi)
            self.run_cli('inspect',midi,'-o',r/'midi.json')
            (r/'rules.json').write_text(json.dumps({'rules':[{'select':{'source':'Synth'},'instrument':14,'role':'sparkle','volume':30}]}))
            self.run_cli('arrange',r/'midi.json','--rules',r/'rules.json','-o',r/'a.json')
            self.run_cli('encode',r/'a.json','-o',r/'a.nbs')
            event=json.loads((r/'a.json').read_text())['events'][0]
            (r/'patch.json').write_text(json.dumps([{'id':event['id'],'expect':{'pitch':84,'instrument':14},'set':{'instrument':7},'reason':'High sparkle verified'}]))
            self.run_cli('patch',r/'a.json','--changes',r/'patch.json','-o',r/'b.json')
            self.run_cli('encode',r/'b.json','-o',r/'b.nbs')
            self.run_cli('diff',r/'a.nbs',r/'b.nbs','-o',r/'diff.json')
            diff=json.loads((r/'diff.json').read_text());self.assertEqual(len(diff['added']),1);self.assertEqual(len(diff['removed']),1)
            self.run_cli('patch',r/'b.json','--changes',r/'patch.json','-o',r/'bad.json',ok=False)
            self.run_cli('build-web','--nbs',r/'a.nbs',r/'b.nbs','-o',r/'player.html')
            html=(r/'player.html').read_text();self.assertNotIn('<script src=',html);self.assertIn('window.BOOT=',html)
    def test_zip_and_unassigned_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            r=Path(folder)
            with zipfile.ZipFile(r/'bad.zip','w') as z:z.writestr('../escape.txt','bad')
            self.run_cli('extract',r/'bad.zip','-o',r/'output',ok=False);self.assertFalse((r/'output').exists())
            with zipfile.ZipFile(r/'good.zip','w') as z:z.writestr('notes.txt','ok')
            self.run_cli('extract',r/'good.zip','-o',r/'output');self.assertEqual((r/'output/notes.txt').read_text(),'ok')
            self.run_cli('extract',r/'good.zip','-o',r/'output',ok=False)
    def test_invalid_key_metadata_is_isolated_without_source_mutation(self):
        sys.path.insert(0,str(ROOT/'scripts'));from midi_reader import inspect_file
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'invalid.mid';m=mido.MidiFile();t=mido.MidiTrack();m.tracks.append(t)
            t.extend([mido.MetaMessage('key_signature',key='C'),mido.Message('note_on',note=60),mido.Message('note_off',note=60,time=480)]);m.save(p)
            raw=p.read_bytes().replace(b'\xff\x59\x02\x00\x00',b'\xff\x59\x02\x08\x09');p.write_bytes(raw)
            summary,notes=inspect_file(p);self.assertEqual(len(summary['repairs']),1);self.assertEqual(notes[0]['pitch'],60);self.assertEqual(p.read_bytes(),raw)

if __name__=='__main__':unittest.main()
