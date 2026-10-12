"""Portable TLK and archive helpers. Python 3.10+, standard library."""
import argparse
import collections
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
HAN = re.compile(r'[\u3400-\u9fff]')
TOKENS = re.compile(r'<[^<>\r\n]+>|%[sdif]|\{[^{}\r\n]+\}')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

class TLK:
    def __init__(self, path, encoding):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:8] != b'TLK V3.0':
            raise ValueError(f'Unsupported TLK: {path}')
        self.language, self.count, self.offset = struct.unpack_from('<III', self.data, 8)
        if self.offset < 20 + self.count * 40 or self.offset > len(self.data):
            raise ValueError('Invalid TLK table bounds')
        self.entries = []
        self.texts = []
        self.raws = []
        for i in range(self.count):
            e = struct.unpack_from('<I16sIIIIf', self.data, 20 + 40 * i)
            start, size = e[4:6]
            if self.offset + start + size > len(self.data):
                raise ValueError(f'Invalid TLK text bounds at {i}')
            raw = self.data[self.offset + start:self.offset + start + size]
            self.entries.append(e)
            self.raws.append(raw)
            self.texts.append(raw.decode(encoding, errors='strict'))
        self.encoding = encoding

    def sound(self, i):
        return self.entries[i][1].rstrip(b'\x00 ').decode('ascii', errors='strict')

    def summary(self):
        return dict(path=str(self.path), sha256=sha(self.data), bytes=len(self.data),
                    language=self.language, entries=self.count, encoding=self.encoding,
                    nonempty=sum(bool(t.strip()) for t in self.texts),
                    chinese_entries=sum(bool(HAN.search(t)) for t in self.texts),
                    sound_entries=sum(bool(self.sound(i)) for i in range(self.count)))

    def build(self, destination, replacements, encoding):
        # Preserve original record metadata including sound, flags, lengths and duration.
        table, strings = bytearray(), bytearray()
        for i, e in enumerate(self.entries):
            text = replacements[i] if i in replacements else self.texts[i]
            raw = text.encode(encoding, errors='strict')
            if raw and not e[0] & 1:
                raise ValueError(f'Replacement into entry without text flag: {i}')
            table += struct.pack('<I16sIIIIf', e[0], e[1], e[2], e[3], len(strings), len(raw), e[6])
            strings += raw
        data = b'TLK V3.0' + struct.pack('<III', self.language, self.count, 20 + len(table)) + table + strings
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return data

def archive_members(path):
    b = path.read_bytes()
    if b[:4] == b'RIM ':
        count, offset = struct.unpack_from('<II', b, 12)
        for i in range(count):
            name, kind, _, start, size = struct.unpack_from('<16sIIII', b, offset+32*i)
            if start+size > len(b):
                raise ValueError(f'Archive bounds: {path}')
            yield name.rstrip(b'\x00').decode('ascii'), kind, b[start:start+size]
    elif b[:4] in (b'ERF ', b'MOD ', b'HAK ', b'SAV '):
        count = struct.unpack_from('<I', b, 16)[0]
        key_offset, res_offset = struct.unpack_from('<II', b, 24)
        for i in range(count):
            name, resource_id, kind, _ = struct.unpack_from('<16sIHH', b, key_offset+24*i)
            start, size = struct.unpack_from('<II', b, res_offset+8*resource_id)
            if start+size > len(b):
                raise ValueError(f'Archive bounds: {path}')
            yield name.rstrip(b'\x00').decode('ascii'), kind, b[start:start+size]
