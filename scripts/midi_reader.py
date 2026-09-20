"""核对Suno分轨的绝对时间，并隔离非法调号元数据。"""

import bisect
import hashlib
import io
import json
import shutil
import struct
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

import mido


def variable_length(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if position >= len(data):
            raise ValueError("Truncated MIDI variable-length integer")
        byte = data[position]
        position += 1
        value = value * 128 + (byte & 127)
        if byte < 128:
            return value, position
    raise ValueError("MIDI variable-length integer exceeds four bytes")


def isolate_invalid_keys(data: bytes) -> tuple[bytes, list[dict]]:
    if data[:4] != b"MThd":
        raise ValueError("Invalid MIDI header")
    patched = bytearray(data)
    changes = []
    header_length = struct.unpack_from(">I", data, 4)[0]
    position = 8 + header_length
    track_index = 0
    while position < len(data):
        if data[position:position + 4] != b"MTrk":
            raise ValueError("Expected MIDI track chunk")
        size = struct.unpack_from(">I", data, position + 4)[0]
        position += 8
        end = position + size
        running_status = None
        absolute_tick = 0
        while position < end:
            delta, position = variable_length(data, position)
            absolute_tick += delta
            status = data[position]
            if status >= 128:
                position += 1
                if status < 240:
                    running_status = status
            elif running_status is None:
                raise ValueError("Missing MIDI running status")
            else:
                status = running_status
            if status == 255:
                type_offset = position
                meta_type = data[position]
                position += 1
                length, position = variable_length(data, position)
                payload = data[position:position + length]
                if meta_type == 89:
                    sharps = struct.unpack("b", payload[:1])[0] if payload else 128
                    valid = length == 2 and -7 <= sharps <= 7 and payload[1] in (0, 1)
                    if not valid:
                        # 原字节保留为厂商元数据，不猜测调性，也不修改任何时间或音符。
                        patched[type_offset] = 127
                        changes.append({"track": track_index, "tick": absolute_tick, "offset": type_offset, "raw_key_signature": payload.hex(), "action": "Reclassify invalid key metadata as sequencer-specific"})
                position += length
            elif status in (240, 247):
                length, position = variable_length(data, position)
                position += length
            elif 128 <= status < 240:
                position += 1 if status & 240 in (192, 208) else 2
            else:
                raise ValueError(f"Unexpected MIDI status byte {status}")
        if position != end:
            raise ValueError("MIDI track length mismatch")
        track_index += 1
    return bytes(patched), changes


class TempoMap:
    def __init__(self, ticks_per_beat: int, changes: list[tuple[int, int]]) -> None:
        by_tick = {}
        for tick, tempo in changes:
            if tempo <= 0: raise ValueError("Invalid MIDI tempo")
            if tick in by_tick and tempo != by_tick[tick]:
                raise ValueError("Conflicting simultaneous MIDI tempo values")
            by_tick[tick] = tempo
        by_tick.setdefault(0, 500000)
        self.ticks_per_beat = ticks_per_beat
        self.ticks = sorted(by_tick)
        self.tempos = [by_tick[tick] for tick in self.ticks]
        self.seconds = [0.0]
        for index in range(1, len(self.ticks)):
            delta = self.ticks[index] - self.ticks[index - 1]
            self.seconds.append(self.seconds[-1] + delta * self.tempos[index - 1] / (ticks_per_beat * 1_000_000))

    def at(self, tick: int) -> float:
        index = bisect.bisect_right(self.ticks, tick) - 1
        return self.seconds[index] + (tick - self.ticks[index]) * self.tempos[index] / (self.ticks_per_beat * 1_000_000)


def inspect_file(path: Path) -> tuple[dict, list[dict]]:
    data = path.read_bytes()
    sanitized, repairs = isolate_invalid_keys(data)
    midi_file = mido.MidiFile(file=io.BytesIO(sanitized))
    if midi_file.type == 2 or midi_file.ticks_per_beat <= 0:
        raise ValueError('MIDI type 2 and SMPTE time division are not supported')
    tempo_events = []
    tracks = []
    all_events = []
    for index, track in enumerate(midi_file.tracks):
        absolute_tick = 0
        absolute = []
        for msg in track:
            absolute_tick += msg.time
            absolute.append((absolute_tick, msg))
            if msg.type == "set_tempo":
                tempo_events.append((absolute_tick, msg.tempo))
        tracks.append(absolute)
    tempo_map = TempoMap(midi_file.ticks_per_beat, tempo_events)
    summaries = []
    issues = []
    for index, track in enumerate(tracks):
        active = defaultdict(deque)
        programs = defaultdict(int)
        channel_volume = defaultdict(lambda: 127)
        channel_expression = defaultdict(lambda: 127)
        channel_pan = defaultdict(lambda: 64)
        sustain = defaultdict(bool)
        pending_sustain = defaultdict(list)
        controllers = Counter()
        program_list = []
        metadata = []
        notes = []

        def finish(event: dict, tick: int) -> None:
            event["end_tick"] = tick
            event["end"] = tempo_map.at(tick)
            event["duration"] = event["end"] - event["start"]
            notes.append(event)

        for tick, msg in track:
            if msg.type == "program_change":
                programs[msg.channel] = msg.program
                program_list.append([tick, msg.channel, msg.program])
            elif msg.type == "control_change":
                controllers[msg.control] += 1
                if msg.control == 7:
                    channel_volume[msg.channel] = msg.value
                elif msg.control == 11:
                    channel_expression[msg.channel] = msg.value
                elif msg.control == 10:
                    channel_pan[msg.channel] = msg.value
                elif msg.control == 64:
                    released = sustain[msg.channel] and msg.value < 64
                    sustain[msg.channel] = msg.value >= 64
                    if released:
                        for event in pending_sustain.pop(msg.channel, []):
                            finish(event, tick)
            elif msg.type == "note_on" and msg.velocity > 0:
                event = {"source": path.stem.split("(")[-1].rstrip(")"), "file": path.name, "track": index, "track_name": midi_file.tracks[index].name, "channel": msg.channel, "program": programs[msg.channel], "start_tick": tick, "start": tempo_map.at(tick), "pitch": msg.note, "velocity": msg.velocity, "channel_volume": channel_volume[msg.channel], "expression": channel_expression[msg.channel], "pan": channel_pan[msg.channel]}
                active[(msg.channel, msg.note)].append(event)
            elif msg.type == "note_off" or msg.type == "note_on" and msg.velocity == 0:
                queue = active[(msg.channel, msg.note)]
                if queue:
                    event = queue.popleft()
                    if sustain[msg.channel]:
                        pending_sustain[msg.channel].append(event)
                    else:
                        finish(event, tick)
                else:
                    issues.append({"track": index, "tick": tick, "issue": "Unmatched note-off"})
            elif msg.is_meta and msg.type != "end_of_track":
                metadata.append([tick, str(msg)])
            elif msg.type == "pitchwheel":
                issues.append({"track": index, "tick": tick, "issue": "Pitch bend", "value": msg.pitch})
        end_tick = track[-1][0] if track else 0
        for queue in active.values():
            for event in queue:
                issues.append({"track": index, "tick": end_tick, "issue": "Unterminated note"})
                finish(event, end_tick)
        for pending in pending_sustain.values():
            for event in pending:
                finish(event, end_tick)
        for event in notes:
            event["source_id"] = f"{hashlib.sha256(data).hexdigest()[:16]}:{index}:{len(all_events)}"
            all_events.append(event)
        summaries.append({"track": index, "name": midi_file.tracks[index].name, "notes": len(notes), "pitch_range": [min(event["pitch"] for event in notes), max(event["pitch"] for event in notes)] if notes else [], "first_note_seconds": min((event["start"] for event in notes), default=None), "last_note_end_seconds": max((event["end"] for event in notes), default=None), "end_tick": end_tick, "end_seconds": tempo_map.at(end_tick), "velocity_range": [min(event["velocity"] for event in notes), max(event["velocity"] for event in notes)] if notes else [], "programs": program_list, "meta": metadata, "controllers": dict(controllers)})
    summary = {"file": path.name, "sha256": hashlib.sha256(data).hexdigest(), "type": midi_file.type, "ticks_per_beat": midi_file.ticks_per_beat, "tempo_changes": [{"tick": tick, "tempo_us": tempo, "bpm": 60_000_000 / tempo, "seconds": tempo_map.at(tick)} for tick, tempo in zip(tempo_map.ticks, tempo_map.tempos)], "repairs": repairs, "issues": issues, "tracks": summaries, "note_count": len(all_events), "first_note": min((event["start"] for event in all_events), default=0), "last_note_end": max((event["end"] for event in all_events), default=0)}
    return summary, all_events
