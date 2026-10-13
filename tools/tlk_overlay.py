"""Compile small, source-guarded translation overlays; never write dialog.tlk.

Prototype v1 replaces existing StrRefs. New virtual references are intentionally
excluded until script/save/reference handling has been tested in the engine.
"""
import argparse,collections,hashlib,json,mmap,re,struct
from pathlib import Path
TOKENS=re.compile(r'<[^<>\r\n]+>|%[sdif]|\{[^{}\r\n]+\}')
class TextTable:
    def __init__(self,path):
        self.file=path.open('rb');self.data=None
        try:
            self.data=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ)
            if len(self.data)<20 or self.data[:8]!=b'TLK V3.0':raise ValueError('Invalid TLK')
            self.count,self.offset=struct.unpack_from('<II',self.data,12)
            if not 20+40*self.count<=self.offset<=len(self.data):raise ValueError('Invalid TLK index')
        except Exception:self.close();raise
    def raw(self,ref):
        if not 0<=ref<self.count:return b''
        start,size=struct.unpack_from('<II',self.data,20+40*ref+28)
        if self.offset+start+size>len(self.data):raise ValueError('TLK text out of bounds')
        return self.data[self.offset+start:self.offset+start+size]
    def close(self):
        if self.data is not None:self.data.close()
        self.file.close()
def encode(text,mapping):
    out=bytearray()
    for chunk in re.split(r'(<[\x20-\x7e]+?>)',text):
        if chunk.startswith('<') and chunk.endswith('>') and chunk.isascii():out.extend(chunk.encode('ascii'));continue
        for c in chunk:
            if c==' ':out.extend((251,32))
            elif ord(c)<128:out.append(ord(c))
            else:out.extend(mapping[c])
    return bytes(out)

MAGIC=b'CHSOVL1\0';HEADER=struct.Struct('<8sII32s');RECORD=struct.Struct('<IIIII')
MAX_PACK=64*1024*1024;MAX_TEXT=1024*1024
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical_mapping(path):
    value=json.loads(path.read_text(encoding='utf8'))
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')
    return value,hashlib.sha256(raw).digest()
def compile_pack(spec,source,map_path,current=None,verified_sources=None):
    if spec.get('schema')!=1:raise ValueError('Unsupported schema')
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}',spec.get('mod_id','')):raise ValueError('Invalid mod_id')
    mapping,mapping_sha=canonical_mapping(map_path);mapping={k:bytes.fromhex(v) for k,v in mapping.items()}
    table=TextTable(source);localized=TextTable(current) if current else None
    sources=verified_sources or {};records=[];seen=set();report=[]
    try:
        for row in spec['entries']:
            ref=row['strref']
            if isinstance(ref,bool) or not isinstance(ref,int) or not 0<=ref<min(table.count,0x1000000):raise ValueError('StrRef outside original table')
            if ref in seen:raise ValueError('Duplicate StrRef in pack')
            seen.add(ref);original=table.raw(ref);text=original.decode('cp1252')
            if not original or sha(text.encode('utf8'))!=row['source_sha256']:raise ValueError(f'Source changed at {ref}')
            zh=row['zh']
            if not isinstance(zh,str) or not zh.strip() or '\0' in zh:raise ValueError('Invalid translation')
            if collections.Counter(TOKENS.findall(text))!=collections.Counter(TOKENS.findall(zh)):raise ValueError(f'Variables/notes changed at {ref}')
            try:after=encode(zh,mapping)
            except KeyError as exc:raise ValueError(f'Character missing from current map: {exc}') from exc
            before=[original]
            if localized:
                # A ref alone is never proof that two tables share a source.
                if sources.get(ref)!=row['source_sha256']:raise ValueError(f'Current Chinese source identity unverified at {ref}')
                raw=localized.raw(ref)
                if not raw:raise ValueError('Current Chinese table lacks this reference')
                if raw not in before:before.append(raw)
            if any(not 0<len(b)<=MAX_TEXT or b'\0' in b for b in before+[after]):raise ValueError('Text size or NUL invalid')
            records.extend((ref,b,after) for b in before)
            report.append(dict(strref=ref,source_sha256=row['source_sha256'],accepted_versions=len(before),encoded_bytes=len(after)))
    finally:
        table.close()
        if localized:localized.close()
    records.sort(key=lambda r:(r[0],r[1]));blob=bytearray();index=[];start=HEADER.size+RECORD.size*len(records)
    for ref,b,a in records:
        bo=start+len(blob);blob+=b+b'\0';ao=start+len(blob);blob+=a+b'\0';index.append(RECORD.pack(ref,bo,len(b),ao,len(a)))
    result=HEADER.pack(MAGIC,1,len(records),mapping_sha)+b''.join(index)+blob
    if len(result)>MAX_PACK:raise ValueError('Pack too large')
    return result,dict(schema=1,mod_id=spec['mod_id'],status='prototype_not_installed',entries=report,records=len(records),bytes=len(result),mapping_sha256=mapping_sha.hex(),pack_sha256=sha(result),source_tlk_sha256=sha(source.read_bytes()),dialog_tlk_written=False)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',type=Path,required=True);p.add_argument('--source-tlk',type=Path,required=True);p.add_argument('--map',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--current-tlk',type=Path);p.add_argument('--source-manifest',type=Path);a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.report.json').exists():raise ValueError('Preserve previous output; choose a fresh path')
    verified={}
    if a.source_manifest:
        for line in a.source_manifest.read_text(encoding='utf8').splitlines():
            r=json.loads(line);verified[int(r['id'].rsplit(':',1)[1])]=r['source_sha256']
    data,report=compile_pack(json.loads(a.spec.read_text(encoding='utf8')),a.source_tlk,a.map,a.current_tlk,verified)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(data);a.output.with_suffix('.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
