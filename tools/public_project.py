"""Read public data and recover exact English sources from a local installation."""
import collections,json
from pathlib import Path
from localization import ROOT,CFG,TLK,sha,archive_members,TOKENS
from embedded_patch import read_local

def rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def translations():
    return {p:rows(ROOT/f'translations/final/{p}.jsonl') for p in ('base','mod','gff')}
def locations():return rows(ROOT/'data/gff-locations.jsonl')
def resources(path):
    if path.suffix.lower() in ('.mod','.rim','.erf'):
        return {(n,k):b for n,k,b in archive_members(path)}
    return {(path.stem,None):path.read_bytes()}
def english_sources(data):
    tables={};sources={};front=Path(CFG['workshop'])/'1402798020'
    for profile,path in [('base',Path(CFG['game'])/'dialog.tlk'),('mod',front/'dialog.tlk')]:
        table=TLK(path,'cp1252');tables[profile]=table
        for row in data[profile]:
            ref=int(row['id'].rsplit(':',1)[1]);source=table.texts[ref]
            assert sha(source.encode('utf-8'))==row['source_sha256'],(row['id'],'English source mismatch')
            sources[row['id']]=source
    by_id={r['id']:r for r in data['gff']};cache={}
    for group in locations():
        row=by_id[group['id']];seen=set()
        for loc in group['occurrences']:
            relative=Path(loc['container']);assert not relative.is_absolute() and '..' not in relative.parts
            if loc['container'] not in cache:cache[loc['container']]=resources(front/relative)
            raw=cache[loc['container']][(loc['resource'],loc['resource_type'])]
            ref,strings=read_local(raw,loc['field_index']);source=dict(strings)[loc['language_gender']]
            assert ref==loc['strref'] and sha(source)==loc['raw_sha256']
            text=source.decode('cp1252')
            assert sha(text.encode('utf-8'))==row['source_sha256'],(row['id'],'GFF source mismatch')
            seen.add(text)
        assert len(seen)==1;sources[row['id']]=seen.pop()
    for rows_ in data.values():
        for row in rows_:
            source=sources[row['id']]
            assert collections.Counter(TOKENS.findall(source))==collections.Counter(TOKENS.findall(row['zh'])),(row['id'],'Placeholder mismatch')
            assert row['status']!='keep_original' or row['zh']==source
    return tables,sources,cache
