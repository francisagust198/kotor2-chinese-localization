"""Local translation projects and small source-guarded KOTOR II patches. MIT."""
import collections,csv,gzip,hashlib,json,os,shutil,struct,sys,tempfile,zipfile
from pathlib import Path
from save_cache_converter import GFF
from tlk_overlay import TextTable,TOKENS,encode,canonical_mapping,compile_pack
VERSION='0.2.0'
EXTENSIONS={'.uti','.utc','.dlg','.utp','.utm','.utt','.uts','.ute','.utd','.utw','.are','.git','.ifo','.gui','.gff','.jrl','.bic'}
def sha(b):return hashlib.sha256(b).hexdigest()
def resource_path(name):
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    for p in [base/name,base.parent/'data'/name,base.parent/'github/kotor2-chinese-localization/data'/name]:
        if p.exists():return p
    raise ValueError('缺少工具配套数据：'+name)
def save_project(project,path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.new');temp.write_text(json.dumps(project,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(p)
def load_project(path):
    value=json.loads(Path(path).read_text(encoding='utf8'))
    if value.get('schema')!=1 or value.get('tool')!='kotor2.mod-translator':raise ValueError('不是本工具的翻译工程')
    ids=[r['key'] for r in value['rows']]
    if len(ids)!=len(set(ids)):raise ValueError('工程包含重复条目')
    return value
def extract(folder,tlk=None,mode='mod'):
    root=Path(folder).resolve();table=TextTable(Path(tlk)) if tlk else None;rows=[];warnings=[];resources={}
    if not root.is_dir():raise ValueError('请选择解压后的 MOD 文件夹')
    try:
        if mode=='tlk':
            if table is None:raise ValueError('本体文本修正需要选择英文 TLK')
            for ref in range(table.count):
                raw=table.raw(ref)
                if raw:rows.append(dict(key='tlk:'+str(ref),kind='tlk',strref=ref,source=raw.decode('cp1252'),source_sha256=sha(raw.decode('cp1252').encode('utf8')),zh=''))
        else:
            for p in sorted(root.rglob('*')):
                if not p.is_file():continue
                if p.is_symlink():raise ValueError('MOD 包含链接，请复制为普通文件后再提取')
                relative=p.relative_to(root).as_posix()
                if p.suffix.lower() in {'.mod','.rim','.erf'}:warnings.append(relative+'：模块容器暂不支持，请先提取其中 GFF 资源');continue
                if p.suffix.lower() not in EXTENSIONS:continue
                raw=p.read_bytes()
                try:g=GFF(raw)
                except Exception as e:warnings.append(relative+'：无法解析 GFF，'+str(e));continue
                resources[relative]=sha(raw)
                for i,row in enumerate(g.rows):
                    if row[0]!=12:continue
                    ref,slots=g.local(i);english=[(lang,text) for lang,text in slots if lang in (0,1) and text]
                    if not slots and ref!=0xffffffff:
                        if table is None:warnings.append(relative+' / '+row[4]+'：引用 TLK，需选择该 MOD 的英文 TLK');continue
                        text=table.raw(ref)
                        if text:english=[(0,text)]
                        else:warnings.append(relative+' / '+row[4]+'：TLK 中未找到编号 '+str(ref))
                    for lang,text in english:
                        original=text.decode('cp1252');rows.append(dict(key=relative+':'+str(i)+':'+str(lang),kind='gff',resource=relative,field=i,label=row[4],language_gender=lang,strref=ref,source=original,source_sha256=sha(original.encode('utf8')),zh=''))
    finally:
        if table:table.close()
    return dict(schema=1,tool='kotor2.mod-translator',tool_version=VERSION,mode=mode,mod_id='',source_root=str(root),source_tlk=str(Path(tlk).resolve()) if tlk else '',source_tlk_sha256=sha(Path(tlk).read_bytes()) if tlk else '',resources=resources,rows=rows,warnings=warnings)
def export_csv(project,path):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['key','source','zh']);w.writeheader();w.writerows({k:r[k] for k in w.fieldnames} for r in project['rows'])
def import_csv(project,path):
    known={r['key']:r for r in project['rows']};pending={}
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r.get('key') not in known or r.get('source')!=known[r['key']]['source']:raise ValueError('CSV 原文或条目标识不匹配；请从当前工程重新导出')
            if r['key'] in pending:raise ValueError('CSV 重复条目')
            pending[r['key']]=r.get('zh','')
    for key,text in pending.items():known[key]['zh']=text
    return len(pending)
def current_sources(path=None):
    with gzip.open(path or resource_path('overlay-current-sources.json.gz'),'rt',encoding='utf8') as f:return {int(k):v for k,v in json.load(f).items()}
def build(project,output,map_path=None,current_tlk=None,sources_path=None):
    import re
    mod_id=project.get('mod_id','')
    if not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',mod_id):raise ValueError('工程标识请用小写英文、数字、点、短横线，例如 effix.carthjacket.chs')
    root=Path(project['source_root']).resolve();dest=Path(output).resolve()
    if dest.exists():raise ValueError('输出目录已存在，请选择一个新目录，避免覆盖之前的补丁')
    if dest.with_name(dest.name+'.zip').exists():raise ValueError('已有同名补丁 ZIP，请选择一个新输出目录')
    if dest==root or root in dest.parents:raise ValueError('输出目录不能位于原 MOD 内')
    mapping,fingerprint=canonical_mapping(map_path or resource_path('current-map.json'));mapping={k:bytes.fromhex(v) for k,v in mapping.items()}
    translated=[r for r in project['rows'] if r.get('zh','').strip()]
    if not translated:raise ValueError('请先输入至少一条译文')
    ids=[r['key'] for r in translated]
    if len(ids)!=len(set(ids)):raise ValueError('重复条目')
    for r in translated:
        if sha(r['source'].encode('utf8'))!=r['source_sha256']:raise ValueError('工程原文摘要不匹配：'+r['key'])
        if '\0' in r['zh'] or collections.Counter(TOKENS.findall(r['source']))!=collections.Counter(TOKENS.findall(r['zh'])):raise ValueError('译文变量或占位符不匹配：'+r['key'])
        missing=sorted(set(c for c in r['zh'] if ord(c)>=128 and c not in mapping))
        if missing:raise ValueError('当前字体缺少这些字符：'+''.join(missing)+'；请调整译文或向主汉化提交字形扩展请求')
    patch={};resource_reports=[]
    groups={}
    for r in translated:
        if r['kind']=='gff':groups.setdefault(r['resource'],[]).append(r)
    table=None
    if project.get('source_tlk'):
        p=Path(project['source_tlk'])
        if sha(p.read_bytes())!=project['source_tlk_sha256']:raise ValueError('英文 TLK 在提取后有变化，请重新提取')
        table=TextTable(p)
    try:
        for relative,edits in groups.items():
            source=(root/relative).resolve()
            if root not in source.parents or source.is_symlink():raise ValueError('资源路径越界')
            original=source.read_bytes()
            if sha(original)!=project['resources'][relative]:raise ValueError('原 MOD 资源已更新，请重新提取：'+relative)
            g=GFF(original);replacements={};by_field={}
            for r in edits:by_field.setdefault(r['field'],[]).append(r)
            for field,changes in by_field.items():
                ref,slots=g.local(field);existing=dict(slots)
                for r in changes:
                    if g.rows[field][4]!=r['label'] or ref!=r['strref']:raise ValueError('字段身份不匹配')
                    before=existing.get(r['language_gender'])
                    if before is None and not slots and table is not None:before=table.raw(ref)
                    if before is None or before.decode('cp1252')!=r['source']:raise ValueError('字段原文不匹配：'+r['key'])
                    existing[r['language_gender']]=encode(r['zh'],mapping)
                # Keep native StrRef, all other languages/genders and voice sources.
                data=struct.pack('<II',ref,len(existing))
                for lang,text in existing.items():data+=struct.pack('<II',lang,len(text))+text
                replacements[field]=struct.pack('<I',len(data))+data
            result=g.rebuild(replacements);parsed=GFF(result)
            for i,(a,b) in enumerate(zip(g.rows,parsed.rows)):
                if i not in replacements:assert a[:2]+a[3:]==b[:2]+b[3:] and (a[3] is not None or a[2]==b[2])
            # Loose resources placed in override. Refuse duplicate global names.
            out='override/'+source.name.lower()
            if out in patch:raise ValueError('不同目录有同名资源，不能安全合并到 override：'+source.name)
            patch[out]=result;resource_reports.append(dict(resource=relative,fields=len(by_field),original_sha256=sha(original),patch_sha256=sha(result)))
    finally:
        if table:table.close()
    tlk_rows=[r for r in translated if r['kind']=='tlk'];pack_report=None
    if tlk_rows:
        if not current_tlk:raise ValueError('本体文本修正需要选择当前主汉化的 dialog.tlk，用于校验原文对应关系')
        pack,pack_report=compile_pack(dict(schema=1,mod_id=mod_id,entries=tlk_rows),Path(project['source_tlk']),map_path or resource_path('current-map.json'),Path(current_tlk),current_sources(sources_path))
        patch['localization/translation.chsp']=pack
        patch['localization/chs-overlay.ini']=('[Interface]\r\nVersion=1\r\nFontProvider=3816191703\r\nPackCount=1\r\n[Pack0]\r\nFile=translation.chsp\r\nSHA256='+sha(pack)+'\r\n').encode('ascii')
    report=dict(tool_version=VERSION,mod_id=mod_id,translated_entries=len(translated),remaining_entries=len(project['rows'])-len(translated),mode=project['mode'],mapping_sha256=fingerprint.hex(),resources=resource_reports,tlk_pack=pack_report,source_files_unchanged=True,main_tlk_written=False,no_dll_in_patch=True,runtime_verification='pending',extraction_warnings=project['warnings'])
    report['ai_draft_entries']=sum(r.get('translation_origin')=='ai_draft' for r in translated)
    title=project.get('title') or mod_id+' 简体中文汉化'
    original_url=project.get('original_mod_url','')
    dependencies=['3816191703']+(['3816551034'] if tlk_rows else [])
    metadata=dict(schema=1,name=title,mod_id=mod_id,type='standalone_translation_mod',original_mod=original_url,dependencies=dependencies,contains_native_dll=False,runtime_verification='pending')
    patch['mod-manifest.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode('utf8')
    patch['workshop/title.txt']=title.encode('utf8')
    patch['workshop/description.txt']=(title+'\n\n原 MOD：'+(original_url or '请填写原MOD前置链接')+'\n需要主汉化3816191703，原MOD在前，汉化补丁在后。\n本补丁是独立汉化MOD，不附带DLL，不重打包主dialog.tlk。\n'+('独立文本包需要公共原生组件3816551034支持自动挂载的入口。\n' if tlk_rows else '')+'译文和游戏显示待实际验证，请按原作者要求发布并注明来源。\n').encode('utf8')
    patch['translation-report.json']=json.dumps(report,ensure_ascii=False,indent=2).encode('utf8')
    patch['README-CHS.txt']=('汉化补丁 '+mod_id+'\n\n需要原 MOD 及主汉化3816191703。让本补丁同名资源优先于原 MOD。\n'+('本体文本修正还需公共组件3816551034提供的支持自动挂载的dinput8.dll，重启后读取译文包。\n' if tlk_rows else '局部资源补丁直接使用主汉化字体，不包含DLL，无需逐MOD安装器。\n')+'没有替换主dialog.tlk；旧存档缓存可能保留旧文本，建议新获得物品或新进入区域测试。\n模块容器、2DA普通字符串、脚本内文本未自动处理；见提取警告。\n发布前检查资源冲突、作者授权与实际游戏显示。\n').encode('utf8')
    dest.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.chs-build-',dir=dest.parent))
    try:
        for name,data in patch.items():p=temp/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        temp.rename(dest)
    finally:
        if temp.exists():shutil.rmtree(temp)
    archive=dest.with_name(dest.name+'.zip')
    if archive.exists():raise ValueError('旁边已有同名ZIP；补丁目录已完成，请改名后手动压缩')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name in patch:z.write(dest/name,name)
    return report
