"""Source-gated person-name corrections; never expand a name part into a full name.

Only reviewed variants are changed. Engine placeholders and authoring notes remain
byte-for-byte intact. The correction pass is idempotent and runs on final tables.
"""
import argparse, collections, hashlib, json, re, shutil
from pathlib import Path

PROTECTED = re.compile(r'<[^<>\r\n]+>|\{[^{}]*\}|%(?:\d+\$)?[-+0-9.]*[sdif]')

def source_text(source):
    for _ in range(8):
        new = re.sub(r'\{[^{}]*\}', '', source)
        if new == source: break
        source = new
    return source

def compile_rules(rules):
    compiled = []
    for rule in rules:
        en = re.compile(r'(?<![A-Za-z0-9_])(?:' + '|'.join(re.escape(x) for x in rule['en_forms']) + r')(?![A-Za-z0-9_])', re.I)
        replacements = rule['replacements']
        assert all(k != v for k,v in replacements.items())
        old = re.compile('|'.join(re.escape(x) for x in sorted(replacements,key=len,reverse=True)))
        compiled.append((rule, en, old))
    return compiled

def correct(source, text, compiled):
    visible_source = source_text(source)
    changes=[]
    pieces = PROTECTED.split(text)
    protected = PROTECTED.findall(text)
    for rule,en,old in compiled:
        if not en.search(visible_source): continue
        for i,piece in enumerate(pieces):
            def replace(match):
                before=match.group(); after=rule['replacements'][before]
                changes.append(dict(rule=rule['name'],before=before,after=after))
                return after
            pieces[i]=old.sub(replace,piece)
    result=''.join(piece + (protected[i] if i<len(protected) else '') for i,piece in enumerate(pieces))
    assert PROTECTED.findall(result)==protected
    return result,changes

def load(path):
    return [json.loads(l) for l in path.read_text(encoding='utf-8-sig').splitlines() if l.strip()]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    root=args.root.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    compiled=compile_rules(json.loads((root/'glossary/person-name-rules.json').read_text(encoding='utf-8')))
    data={p:load(root/f'translations/final/{p}.jsonl') for p in ['base','mod','gff']}
    recovered={}
    if any('source' not in r for rows in data.values() for r in rows):
        try:
            from public_project import english_sources
            _,recovered,_=english_sources(data)
        except ImportError as exc:
            raise RuntimeError('Recover hash-verified English sources from a legitimate installation before applying source-gated name rules.') from exc
    all_changes=[];counts=collections.Counter();hits=collections.Counter()
    for profile in ['base','mod','gff']:
        path=root/f'translations/final/{profile}.jsonl';rows=data[profile]
        for row in rows:
            source=row.get('source',recovered.get(row['id']))
            assert isinstance(source,str) and hashlib.sha256(source.encode('utf-8')).hexdigest()==row['source_sha256']
            previous=row['zh'];new,changes=correct(source,previous,compiled)
            if new==previous:continue
            assert correct(source,new,compiled)[0]==new,'Rule cascade: '+row['id']
            all_changes.append(dict(profile=profile,id=row['id'],source_sha256=row['source_sha256'],before=previous,after=new,changes=changes))
            row['zh']=new;row['status']='reviewed'
            row['notes']=(row.get('notes','')+'；按原文人名全称/拆分短称统一术语，去除重复姓氏（2026-10-13）').strip('；')
            counts[profile]+=1;hits.update(c['rule'] for c in changes)
        if args.apply:
            backup=out/'before-final'/path.name;backup.parent.mkdir(exist_ok=True)
            if backup.exists():raise RuntimeError('Preserve backup; choose fresh output')
            shutil.copy2(path,backup)
            tmp=path.with_suffix('.jsonl.new');tmp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');tmp.replace(path)
    (out/'corrections.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in all_changes),encoding='utf-8')
    summary=dict(applied=args.apply,rows=dict(counts),changed_records=len(all_changes),rule_occurrences=dict(hits),rules=len(compiled))
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
