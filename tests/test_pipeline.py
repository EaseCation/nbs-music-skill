"""验证实际转换不变量，包含独立库和跨语言读回。"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nbs import encode,decode,canonical,audit,BASE_PITCH
from midi_reader import TempoMap,inspect_file
import mido

class PipelineTests(unittest.TestCase):
    def event(self,**values):return dict(id='a',time=.501,pitch=72,instrument=14,volume=73,pan=100,source='Guitar',role='lead',**values)
    def test_layer_dynamics_collision_and_no_unintended_doubling(self):
        events=[self.event(),{**self.event(),'id':'b','pitch':76},{**self.event(),'id':'c','time':1,'volume':40}]
        raw,sidecar=encode({'events':events,'duration':3},'Test');song=decode(raw)
        self.assertEqual(len(song['notes']),3);self.assertEqual(len(song['layers']),3)
        self.assertEqual([n['velocity'] for n in song['notes']],[100]*3)
        self.assertEqual(audit(song)['duplicate_groups'],[])
        self.assertLessEqual(sidecar['max_timing_error_ms'],10)
    def test_instrument_switch_preserves_actual_pitch(self):
        e=self.event();a,_=encode({'events':[e]},'A');b,_=encode({'events':[{**e,'instrument':7}]},'B')
        na,nb=decode(a)['notes'][0],decode(b)['notes'][0]
        self.assertEqual(na['key']+BASE_PITCH[14],nb['key']+BASE_PITCH[7])
        self.assertEqual(na['key']-nb['key'],24)
    def test_empty_song_and_bounds(self):
        raw,_=encode({'events':[],'duration':2},'Empty');self.assertEqual(decode(raw)['notes'],[])
        with self.assertRaises(ValueError):encode({'events':[{**self.event(),'pitch':127,'instrument':1}]},'Bad')
        with self.assertRaises(ValueError):encode({'events':[self.event()],'duration':2000},'Bad')
        with self.assertRaises(ValueError):decode(raw[:15])
    def test_diff_ignores_layer_reorder_and_detects_real_change(self):
        events=[self.event(),{**self.event(),'id':'b','time':1,'volume':30}]
        a=decode(encode({'events':events},'A')[0]);b=decode(encode({'events':events[::-1]},'B')[0]);self.assertEqual(canonical(a),canonical(b))
        c=copy.deepcopy(b);c['layers'][0]['volume']+=1;self.assertNotEqual(canonical(a),canonical(c))
    def test_variable_tempo_and_source_untouched(self):
        self.assertAlmostEqual(TempoMap(480,[(0,500000),(480,1000000)]).at(960),1.5)
        with self.assertRaises(ValueError):TempoMap(480,[(0,500000),(0,1000000)])
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'Test (Keyboard).mid';m=mido.MidiFile();t=mido.MidiTrack();m.tracks.append(t)
            t.extend([mido.MetaMessage('set_tempo',tempo=500000),mido.Message('note_on',note=72,velocity=90),mido.MetaMessage('set_tempo',tempo=1000000,time=480),mido.Message('note_off',note=72,time=480)])
            m.save(p);before=p.read_bytes();summary,notes=inspect_file(p)
            self.assertEqual(p.read_bytes(),before);self.assertEqual(notes[0]['duration'],1.5)
    def test_independent_pynbs(self):
        try:import pynbs
        except ImportError:self.skipTest('Install pynbs for independent verification')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'all.nbs';events=[{**self.event(),'id':str(i),'instrument':i,'pitch':BASE_PITCH[i]+12,'time':i*.2} for i in range(16)]
            p.write_bytes(encode({'events':events},'Independent')[0]);s=pynbs.read(str(p))
            self.assertEqual(len(s.notes),16);self.assertEqual({n.key for n in s.notes},{57});self.assertEqual({l.volume for l in s.layers},{73})
    def test_exact_duplicate_is_reported(self):
        raw,_=encode({'events':[self.event(),{**self.event(),'id':'b'}]},'Duplicate')
        self.assertEqual(audit(decode(raw))['duplicate_groups'][0]['count'],2)
    def test_full_profile_microtone_and_velocity(self):
        e={**self.event(),'pitch':72.25};raw,_=encode({'events':[e]},'Fine','nbs');n=decode(raw)['notes'][0]
        self.assertEqual((n['fine'],n['velocity']),(25,73))
        with self.assertRaises(ValueError):encode({'events':[e]},'Fine','game')

if __name__=='__main__':unittest.main()
