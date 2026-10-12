"""Check public editorial data, exact glyph advances, and generated font payloads."""
import json,math,re
from pathlib import Path
from PIL import Image
from public_project import ROOT,sha,translations,locations
from composite_font_resources import make_tpc,verify_tpc

def metrics(lines):
    u=lines.index('upperleftcoords 256')+1;l=lines.index('lowerrightcoords 256')+1
    unit=float(next(s.split()[1] for s in lines if s.startswith('texturewidth ')))*100
    return [(float(lines[l+i].split()[0])-float(lines[u+i].split()[0]))*unit for i in range(256)]
def main():
    release=json.loads((ROOT/'data/release.json').read_text(encoding='utf-8'));data=translations();ids=set();counts={}
    mapping=json.loads((ROOT/'data/current-map.json').read_text(encoding='utf-8'))
    assert sha((ROOT/'data/current-map.json').read_bytes())==release['current_map_sha256']
    for name,digest in json.loads((ROOT/'data/text-checksums.json').read_text(encoding='utf-8')).items():
        assert sha((ROOT/name).read_bytes())==digest,name
    for profile,rows in data.items():
        counts[profile]=len(rows)
        for r in rows:
            assert r['id'] not in ids;ids.add(r['id'])
            assert re.fullmatch('[0-9a-f]{64}',r['source_sha256'])
            assert isinstance(r['zh'],str) and r['zh'].strip() and '\0' not in r['zh']
            assert r['status'] in ('reviewed','translated','approved','keep_original','needs_context')
            assert all(ord(c)<128 or c in mapping for c in r['zh']),r['id']
    assert counts==release['profiles'] and len(ids)==release['final_entries']
    gff=locations();assert len(gff)==counts['gff'] and sum(len(g['occurrences']) for g in gff)==7022
    assert {g['id'] for g in gff}=={r['id'] for r in data['gff']}
    for group in gff:
        for loc in group['occurrences']:
            p=Path(loc['container']);assert not p.is_absolute() and '..' not in p.parts
    recipes=json.loads((ROOT/'data/font-recipes.json').read_text(encoding='utf-8'))
    for name,spec in recipes.items():
        tga=ROOT/'fonts/atlases'/spec['atlas'];txi=ROOT/'fonts/recipes'/(name+'.txi')
        assert sha(tga.read_bytes())==spec['atlas_sha256'] and sha(txi.read_bytes())==spec['txi_sha256']
        raw=make_tpc(tga,txi);verify_tpc(raw,tga,txi);assert sha(raw)==spec['tpc_sha256']
        widths=metrics(txi.read_text(encoding='ascii').splitlines());target=24 if 'sub24' in name else 16
        for c,hexcode in mapping.items():
            code=bytes.fromhex(hexcode)
            assert code.count(128)==code.count(193)==8
            assert abs(sum(widths[b] for b in code)-target)<1e-4,(name,c)
            assert sum(math.trunc(widths[b]+.25) for b in code)==target,(name,c)
            if target==16:
                old=code.replace(bytes([193]),bytes([128]))
                assert all(abs(widths[a]-widths[b])<1e-5 for a,b in zip(old,code))
    print(json.dumps(dict(status='passed',profiles=counts,characters=len(mapping),font_aliases=len(recipes),gff_locations=7022,gameplay_test=False),indent=2))
if __name__=='__main__':main()
