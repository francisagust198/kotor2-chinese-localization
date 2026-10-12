"""Build data-only Chinese resources from exact local English originals."""
import argparse,collections,json,shutil
from pathlib import Path
from public_project import ROOT,CFG,sha,translations,locations,english_sources,resources
from build_uniform_font import encode
from embedded_patch import patch_archive,patch_gff,read_local
from widescreen_gui import Gui,extract_gui
from composite_font_resources import make_tpc,verify_tpc
from name_terminology import compile_rules,correct

def main(output):
    output=output.resolve();assert not output.exists(),'Preserve previous builds; use a new output directory'
    assert not output.is_relative_to(Path(CFG['game']).resolve()) and not output.is_relative_to(Path(CFG['workshop']).resolve()),'Build outside installed game resources'
    data=translations();tables,sources,cache=english_sources(data)
    name_rules=compile_rules(json.loads((ROOT/'glossary/person-name-rules.json').read_text(encoding='utf-8')))
    for rows_ in data.values():
        for row in rows_:
            assert correct(sources[row['id']],row['zh'],name_rules)[0]==row['zh'],(row['id'],'Known name variant or repeated surname; run the source-gated name correction review')
    mapping={c:bytes.fromhex(h) for c,h in json.loads((ROOT/'data/current-map.json').read_text(encoding='utf-8')).items()}
    content=output/'content';content.mkdir(parents=True);front=Path(CFG['workshop'])/'1402798020'
    summaries={}
    for profile,dest in [('base',output/'base-reference/dialog.tlk'),('mod',content/'dialog.tlk')]:
        table=tables[profile];assigned={int(r['id'].rsplit(':',1)[1]):r for r in data[profile]};replacements={}
        for ref,text in enumerate(table.texts):
            if ref in assigned:text=assigned[ref]['zh']
            else:assert not text.strip(),(profile,ref,'Unassigned nonempty source')
            replacements[ref]=encode(text,mapping).decode('latin1')
        table.build(dest,replacements,'latin1')
        from localization import TLK
        after=TLK(dest,'latin1')
        for ref in range(table.count):
            assert after.raws[ref]==replacements[ref].encode('latin1')
            assert after.entries[ref][:4]==table.entries[ref][:4] and after.entries[ref][6]==table.entries[ref][6]
        summaries[profile]=dict(verified_records=table.count,bytes=dest.stat().st_size)
    by_id={r['id']:r for r in data['gff']};containers=collections.defaultdict(list)
    for group in locations():
        for loc in group['occurrences']:containers[loc['container']].append((group['id'],loc))
    checked=0
    for relative,entries in containers.items():
        src=front/relative;grouped=collections.defaultdict(list)
        for identity,loc in entries:
            raw=cache[relative][(loc['resource'],loc['resource_type'])];_,strings=read_local(raw,loc['field_index'])
            if dict(strings)[loc['language_gender']]!=encode(by_id[identity]['zh'],mapping):
                grouped[(loc['resource'],loc['resource_type'])].append(dict(loc,candidate_zh=by_id[identity]['zh'],preserve_translation=True))
        dest=content/relative
        if grouped:
            options=dict(encoder=lambda s:encode(s,mapping),preserve_unselected=True,allow_tlk_backed=True)
            if src.suffix.lower() in ('.mod','.rim','.erf'):patch_archive(src,grouped,dest,**options)
            else:
                assert len(grouped)==1;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(patch_gff(src.read_bytes(),next(iter(grouped.values())),**options))
        result=resources(dest) if dest.exists() else cache[relative]
        for identity,loc in entries:
            ref,strings=read_local(result[(loc['resource'],loc['resource_type'])],loc['field_index'])
            assert ref==loc['strref'] and dict(strings)[loc['language_gender']]==encode(by_id[identity]['zh'],mapping);checked+=1
    override=content/'override';override.mkdir(exist_ok=True)
    for name,spec in json.loads((ROOT/'data/font-recipes.json').read_text(encoding='utf-8')).items():
        tga=override/(name+'.tga');txi=override/(name+'.txi')
        shutil.copy2(ROOT/'fonts/atlases'/spec['atlas'],tga);shutil.copy2(ROOT/'fonts/recipes'/(name+'.txi'),txi)
        raw=make_tpc(tga,txi);verify_tpc(raw,tga,txi);assert sha(raw)==spec['tpc_sha256'];(override/(name+'.tpc')).write_bytes(raw)
    guis=extract_gui(Path(CFG['game']))
    for folder in [Path(CFG['game'])/'override',front/'override']:
        for path in folder.glob('*.gui'):guis[path.name]=path.read_bytes()
    gui_results={}
    for name,recipe in json.loads((ROOT/'data/gui-recipes.json').read_text(encoding='utf-8')).items():
        raw=guis[name];assert sha(raw)==recipe['source_sha256'],(name,'GUI baseline mismatch')
        g=Gui(raw);original=Gui(raw);changed={(e['struct'],e['field']):e for e in recipe['edits']}
        for e in recipe['edits']:
            assert g.get(e['struct'],e['field'])==e['before']
            if e['field']=='FONT':g.set_resref(e['struct'],e['field'],e['after'])
            else:g.set_number(e['struct'],e['field'],e['after'])
        after=Gui(bytes(g.data))
        for i in range(g.sc):
            for key in g.fields(i):assert after.get(i,key)==(changed[(i,key)]['after'] if (i,key) in changed else original.get(i,key))
        (override/name).write_bytes(g.data);gui_results[name]=dict(fields_verified=True,byte_identical_to_published=sha(bytes(g.data))==recipe['output_sha256'])
    assert checked==7022
    report=dict(status='offline_verified_gameplay_pending',tlk=summaries,gff_locations_verified=checked,gui=gui_results,files={p.relative_to(content).as_posix():sha(p.read_bytes()) for p in content.rglob('*') if p.is_file()},installed=False)
    (output/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=report['status'],tlk=summaries,gff_locations=checked,files=len(report['files']),output=str(output)),ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
