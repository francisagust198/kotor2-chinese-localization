"""Portable, copy-only KOTOR II localized-cache converter (stdlib only)."""
import argparse,collections,ctypes,gzip,hashlib,json,mmap,os,re,struct,sys,time,uuid
from pathlib import Path

VERSION='1.0.0'
DISPLAY_LABELS={'FirstName','LastName','LocName','LocalizedName','Name','Description','DescIdentified','Text','MapNote'}
def digest(b):return hashlib.sha256(b).hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)
def resource_dir():return Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
def application_dir():return Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent
def load_catalog(path=None):
    with gzip.open(path or (resource_dir()/'save-cache-catalog.json.gz' if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]/'data/save-cache-catalog.json.gz'),'rt',encoding='utf-8') as f:return json.load(f)
def running_game():
    if os.name!='nt':return False
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('exe',wintypes.WCHAR*260)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    k.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    k.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    snap=k.CreateToolhelp32Snapshot(2,0)
    require(snap!=ctypes.c_void_p(-1).value,'无法检查游戏进程，请稍后重试。')
    e=Entry();e.size=ctypes.sizeof(e)
    try:
        ok=k.Process32FirstW(snap,ctypes.byref(e))
        while ok:
            if e.exe.lower()=='swkotor2.exe' and e.threads:return True
            ok=k.Process32NextW(snap,ctypes.byref(e))
    finally:k.CloseHandle(snap)
    return False

class GFF:
    def __init__(self,b):
        require(len(b)>=56 and b[4:8]==b'V3.2','GFF 格式不受支持。')
        self.b=b;self.pairs=[struct.unpack_from('<II',b,8+8*i) for i in range(6)]
        sizes=[self.pairs[0][1]*12,self.pairs[1][1]*12,self.pairs[2][1]*16]+[p[1] for p in self.pairs[3:]]
        for (o,n),size in zip(self.pairs,sizes):require(not size or (o>=56 and o+size<=len(b)),'GFF 数据范围无效。')
        self.sections=[b[o:o+size] for (o,n),size in zip(self.pairs,sizes)]
        self.rows=[];data=self.sections[3];labels=self.sections[2]
        for i in range(self.pairs[1][1]):
            kind,label,value=struct.unpack_from('<III',self.sections[1],12*i)
            require(kind<=17 and label<self.pairs[2][1],'GFF 字段或标签无效。')
            name=labels[16*label:16*label+16].rstrip(b'\0').decode('ascii')
            size=None
            if kind in (6,7,9):size=8
            elif kind in (10,12,13):
                require(value+4<=len(data),'GFF 文本长度无效。');size=4+struct.unpack_from('<I',data,value)[0]
            elif kind==11:
                require(value<len(data),'GFF 资源名无效。');size=1+data[value]
            elif kind==16:size=16
            elif kind==17:size=12
            require(size is None or value+size<=len(data),'GFF 字段数据越界。')
            self.rows.append((kind,label,value,data[value:value+size] if size is not None else None,name))
        # Identify player-owned name fields rather than guessing from names.
        self.player_names=set()
        for i in range(self.pairs[0][1]):
            _,index,count=struct.unpack_from('<III',self.sections[0],12*i)
            if count==0:continue
            if count==1:indices=[index]
            else:
                require(index+count*4<=len(self.sections[4]),'GFF 结构字段索引越界。')
                indices=struct.unpack_from('<'+'I'*count,self.sections[4],index)
            require(all(j<len(self.rows) for j in indices),'GFF 字段索引无效。')
            if any(self.rows[j][4]=='IsPC' and self.rows[j][0] in (0,2,4) and self.rows[j][2]!=0 for j in indices):
                self.player_names.update(j for j in indices if self.rows[j][4] in ('FirstName','LastName'))
    def local(self,i):
        raw=self.rows[i][3];require(self.rows[i][0]==12 and len(raw)>=12,'无效的本地化字段。')
        total,ref,n=struct.unpack_from('<III',raw);require(total+4==len(raw),'本地化文本长度无效。')
        q=12;strings=[]
        for _ in range(n):
            require(q+8<=len(raw),'本地化文本索引越界。');lang,size=struct.unpack_from('<II',raw,q);q+=8
            require(q+size<=len(raw),'本地化文本越界。');strings.append((lang,raw[q:q+size]));q+=size
        require(q==len(raw),'本地化文本含未知数据。');return ref,strings
    def rebuild(self,replacements):
        sections=list(self.sections);fb=bytearray(sections[1]);data=bytearray()
        for i,(kind,label,value,raw,name) in enumerate(self.rows):
            if raw is None:continue
            struct.pack_into('<I',fb,12*i+8,len(data));data+=replacements.get(i,raw)
        sections[1]=bytes(fb);sections[3]=bytes(data);out=bytearray(self.b[:56])
        for i,section in enumerate(sections):
            struct.pack_into('<II',out,8+8*i,len(out),len(section) if i>=3 else self.pairs[i][1]);out+=section
        result=bytes(out);after=GFF(result)
        require(len(after.rows)==len(self.rows),'转换改变了字段数。')
        for i,(old,new) in enumerate(zip(self.rows,after.rows)):
            require(old[:2]==new[:2] and old[4]==new[4],'转换改变了字段身份。')
            require(new[3]==replacements.get(i,old[3]) if old[3] is not None else old[2]==new[2],'非目标数据发生变化。')
        for i in (0,2,4,5):require(after.sections[i]==self.sections[i],'转换改变了存档结构。')
        return result

class TextTable:
    def __init__(self,path):
        self.path=Path(path);self.file=self.path.open('rb')
        try:
            self.data=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ)
            require(len(self.data)>=20 and self.data[:8]==b'TLK V3.0','请选择有效的 dialog.tlk。')
            self.count,self.offset=struct.unpack_from('<II',self.data,12)
            require(20+self.count*40<=self.offset<=len(self.data),'TLK 索引无效。');self.cache={}
        except Exception:self.close();raise
    def raw(self,ref):
        if ref not in self.cache:
            if ref>=self.count:return b''
            start,size=struct.unpack_from('<II',self.data,20+40*ref+28)
            require(self.offset+start+size<=len(self.data),'TLK 文本越界。')
            self.cache[ref]=self.data[self.offset+start:self.offset+start+size]
        return self.cache[ref]
    def close(self):
        if hasattr(self,'data'):self.data.close()
        self.file.close()

class Converter:
    def __init__(self,tlk,catalog):
        self.tlk=tlk;self.known=catalog['hashes_by_strref'];self.events=[];self.stats=collections.Counter()
    def transform(self,b,path,depth=0):
        require(depth<20,'存档嵌套层数异常。')
        if b[:4] in (b'ERF ',b'MOD ',b'SAV ',b'HAK '):
            require(len(b)>=160,'存档资源包过短。')
            n=struct.unpack_from('<I',b,16)[0];ko,ro=struct.unpack_from('<II',b,24)
            require(160<=ko and ko+n*24<=len(b) and 160<=ro and ro+n*8<=len(b),'资源包索引越界。')
            if not n:return b
            members=[]
            for i in range(n):
                name,rid,kind,_=struct.unpack_from('<16sIHH',b,ko+24*i);require(rid<n,'资源编号无效。')
                off,size=struct.unpack_from('<II',b,ro+8*rid)
                require(off>=max(ko+24*n,ro+8*n) and off+size<=len(b),'资源内容越界。')
                identity=name.rstrip(b'\0').decode('ascii')+'#'+str(kind)+':'+str(rid)
                old=b[off:off+size];new=self.transform(old,path+'!'+identity,depth+1)
                members.append((rid,off,old,new))
            require(len({r for r,_,_,_ in members})==n,'资源编号重复。')
            if all(old==new for _,_,old,new in members):return b
            out=bytearray(b[:min(o for _,o,_,_ in members)])
            for rid,_,old,new in members:struct.pack_into('<II',out,ro+8*rid,len(out),len(new));out+=new
            require(out[:ro]==b[:ro],'资源包身份改变。')
            for rid,_,old,new in members:
                off,size=struct.unpack_from('<II',out,ro+8*rid);require(out[off:off+size]==new,'资源重建失败。')
            return bytes(out)
        if len(b)<56 or b[4:8]!=b'V3.2':return b
        g=GFF(b);replacements={};self.stats['validated_fields']+=len(g.rows)
        for i,(kind,label,value,raw,name) in enumerate(g.rows):
            if kind!=12:continue
            ref,ss=g.local(i)
            if not ss:continue
            if name not in DISPLAY_LABELS or i in g.player_names or ref==0xffffffff:
                self.stats['preserved_custom_or_history']+=1;continue
            canonical=self.tlk.raw(ref)
            if not canonical:self.stats['preserved_invalid_or_empty_reference']+=1;continue
            known=set(self.known.get(str(ref),[]));known.add(digest(canonical))
            if canonical.endswith(b'\xfc\xf9 '):known.add(digest(canonical[:-1]))
            if not all(lang==0 and digest(s) in known for lang,s in ss):
                self.stats['preserved_unrecognized']+=1;continue
            replacements[i]=struct.pack('<III',8,ref,0)
            self.events.append(dict(path=path,field=i,label=name,strref=ref,old_hashes=[digest(s) for _,s in ss],cached_bytes=sum(len(s) for _,s in ss),outdated=any(s!=canonical and s!=canonical[:-1] for _,s in ss)))
        if not replacements:return b
        new=g.rebuild(replacements);self.stats['cleared_fields']+=len(replacements)
        self.stats['storage_bytes_reclaimed']+=len(b)-len(new)
        after=GFF(new)
        for i in replacements:require(after.local(i)==(g.local(i)[0],[]),'文本编号改变。')
        return new

def rename_save(b,name):
    g=GFF(b);targets=[i for i,r in enumerate(g.rows) if r[0]==10 and r[4]=='SAVEGAMENAME']
    require(len(targets)==1,'找不到唯一的存档显示名称。');raw=name.encode('ascii')
    return g.rebuild({targets[0]:struct.pack('<I',len(raw))+raw})
def discover():
    roots=[];here=application_dir()
    for p in (here,here.parent):
        if (p/'swkotor2.exe').is_file():roots.append(p)
    if os.name=='nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as k:steam=Path(winreg.QueryValueEx(k,'SteamPath')[0])
            libraries=[steam];vdf=steam/'steamapps/libraryfolders.vdf'
            if vdf.exists():libraries += [Path(s.replace('\\\\','\\')) for s in re.findall(r'"path"\s+"([^"]+)"',vdf.read_text('utf-8'))]
            for library in libraries:
                manifest=library/'steamapps/appmanifest_208580.acf'
                if manifest.exists():
                    m=re.search(r'"installdir"\s+"([^"]+)"',manifest.read_text('utf-8'))
                    if m:roots.append(library/'steamapps/common'/m[1])
        except (OSError,ValueError):pass
    for game in roots:
        if (game/'saves').is_dir():
            # This item's TLK is authoritative; root dialog.tlk may be English.
            tlk=game.parent.parent/'workshop/content/208580/3816191703/dialog.tlk'
            return game,tlk if tlk.is_file() else None
    return None,None
def prepare(source,tlk_path,catalog):
    source=Path(source).resolve();require(source.is_dir(),'请选择一个存档文件夹。')
    require(source.parent.name.lower() in ('saves','cloudsaves'),'存档必须位于 saves 或 cloudsaves 文件夹内。')
    require((source/'SAVEGAME.sav').is_file() and (source/'savenfo.res').is_file(),'所选文件夹不是完整存档。')
    files=sorted(p for p in source.rglob('*') if p.is_file())
    require(not any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in [source,*source.rglob('*')]),'存档包含链接，无法安全转换。')
    before={p.relative_to(source).as_posix():digest(p.read_bytes()) for p in files}
    table=TextTable(tlk_path)
    try:
        converter=Converter(table,catalog)
        prepared={p.relative_to(source):converter.transform(p.read_bytes(),p.name) if p.name=='SAVEGAME.sav' else p.read_bytes() for p in files}
        tlk_hash=digest(table.data)
    finally:table.close()
    require(before=={p.relative_to(source).as_posix():digest(p.read_bytes()) for p in files},'扫描时原存档发生变化，请退出游戏后重试。')
    return prepared,before,converter,tlk_hash
def convert(source,tlk_path,catalog,label=None,report_root=None,scan=False):
    require(not running_game(),'请先保存并退出游戏，再转换存档。')
    source=Path(source).resolve();prepared,before,converter,tlk_hash=prepare(source,tlk_path,catalog)
    record=dict(tool_version=VERSION,source=str(source),tlk=str(Path(tlk_path).resolve()),tlk_sha256=tlk_hash,catalog_version=catalog['version'],stats=dict(converter.stats),changes=converter.events,original_checksums=before,gameplay_verification='pending')
    if scan:return record
    require(not running_game(),'游戏正在运行，请退出后重试。')
    require(bool(converter.events),'没有可确认、可清理的文本缓存，无需生成副本。')
    old=source.name.split(' - ',1)[-1];label=label or ('CHS '+re.sub('[^A-Za-z0-9 _-]','_',old))[:64]
    require(re.fullmatch('[A-Za-z0-9 _-]{1,64}',label) is not None,'副本名称需为 1–64 位英文字母、数字、空格或短横线。')
    root=source.parent
    index=max([int(p.name[:6]) for p in root.iterdir() if p.is_dir() and re.match(r'^\d{6} - ',p.name)]+[0])+1
    require(index<1000000,'存档编号已满。');target=root/f'{index:06d} - {label}'
    require(not target.exists(),'副本已存在，请修改名称。')
    prepared[Path('savenfo.res')]=rename_save(prepared[Path('savenfo.res')],label)
    # Only save archive and the new copy's display name may change.
    require(all(digest(b)==before[p.as_posix()] for p,b in prepared.items() if p.name not in ('SAVEGAME.sav','savenfo.res')),'其他存档文件发生变化。')
    require(before=={p.relative_to(source).as_posix():digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()},'原存档已变化，请重新扫描。')
    reports=Path(report_root or application_dir()/'conversion-reports');reports.mkdir(parents=True,exist_ok=True)
    report=reports/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json')
    # A failed/preflighted copy must not appear in the game's save list.
    staging_root=root.parent/'CHSConversionTemp';staging_root.mkdir(exist_ok=True)
    staging=staging_root/uuid.uuid4().hex;staging.mkdir()
    for p,b in prepared.items():
        out=staging/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b);require(digest(out.read_bytes())==digest(b),'副本写入校验失败。')
    require(not running_game(),'游戏已启动；未完成副本保留于 '+str(staging))
    require(before=={p.relative_to(source).as_posix():digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()},'原存档已变化；未完成副本保留于 '+str(staging))
    # os.rename refuses an existing target on Windows; originals are never replaced.
    record.update(target=str(target),display_name=label,originals_unchanged=True,output_checksums={p.as_posix():digest(b) for p,b in prepared.items()})
    record['status']='prepared';report.write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf-8')
    staging.rename(target)
    try:staging_root.rmdir()
    except OSError:pass  # Other conversions or a preserved failed copy may exist.
    record['status']='completed';report.write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf-8');record['report']=str(report)
    return record

def gui(smoke=False):
    import threading,tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    try:ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError,OSError):pass
    root=tk.Tk();root.title('KOTOR II 汉化存档转换工具');root.geometry('760x590');root.minsize(700,540)
    catalog=load_catalog();game,tlk=discover();source=tk.StringVar();table=tk.StringVar(value=str(tlk or ''));name=tk.StringVar();busy=False
    frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='更新旧存档的汉化文本',font=('Microsoft YaHei UI',16)).pack(anchor='w')
    ttk.Label(frame,text='生成新副本，原存档保留。仅清理已核对来源的文本缓存。').pack(anchor='w',pady=(5,15))
    def choose_save():
        p=filedialog.askdirectory(title='选择单个存档文件夹',initialdir=str(game/'saves') if game else None)
        if p:source.set(p);name.set(('CHS '+re.sub('[^A-Za-z0-9 _-]','_',Path(p).name.split(' - ',1)[-1]))[:64])
    def line(title,var,command=None):
        ttk.Label(frame,text=title).pack(anchor='w',pady=(8,3));row=ttk.Frame(frame);row.pack(fill='x')
        ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
        if command:ttk.Button(row,text='选择…',command=command).pack(side='right',padx=(8,0))
    line('原存档文件夹',source,choose_save)
    line('当前汉化的 dialog.tlk',table,lambda:table.set(filedialog.askopenfilename(title='选择汉化 dialog.tlk',initialdir=str(tlk.parent) if tlk else None,filetypes=[('游戏文本','*.tlk')]) or table.get()))
    line('新副本名称（英文或数字）',name)
    ttk.Label(frame,text='自定义名称、未知来源文本和对话历史会保留；文本更新后可能需要再次转换。',wraplength=700).pack(anchor='w',pady=12)
    buttons=ttk.Frame(frame);buttons.pack(fill='x');output=tk.Text(frame,height=12,wrap='word',font=('Microsoft YaHei UI',10));output.pack(fill='both',expand=True,pady=12)
    def finish(result,error):
        nonlocal busy
        busy=False
        for button in (scan_button,convert_button):button.config(state='normal')
        output.delete('1.0','end')
        if error:output.insert('end','未完成：'+str(error));messagebox.showerror('未完成',str(error));return
        stats=result['stats'];outdated=sum(e['outdated'] for e in result['changes'])
        output.insert('end',f"可清理缓存：{stats.get('cleared_fields',0)} 处，其中旧译文 {outdated} 处。\n回收存储：{stats.get('storage_bytes_reclaimed',0):,} 字节。\n保留未知缓存：{stats.get('preserved_unrecognized',0)} 处。\n")
        if 'target' in result:output.insert('end','\n转换完成，原存档未改动。\n请在游戏中读取：'+result['display_name']+'\n\n副本：'+result['target']+'\n记录：'+result['report']+'\n游戏内读取结果尚待检查。')
        else:output.insert('end','\n这是扫描结果，未写入存档。')
    def run(scan):
        nonlocal busy
        if busy:return
        # Snapshot Tk values on the UI thread.
        arguments=(source.get(),table.get(),name.get());busy=True
        for button in (scan_button,convert_button):button.config(state='disabled')
        output.delete('1.0','end');output.insert('end','正在检查存档，请稍候…')
        def worker():
            try:result=convert(arguments[0],arguments[1],catalog,label=arguments[2] or None,scan=scan);root.after(0,finish,result,None)
            except Exception as e:root.after(0,finish,None,str(e))
        threading.Thread(target=worker,daemon=True).start()
    scan_button=ttk.Button(buttons,text='扫描缓存',command=lambda:run(True));scan_button.pack(side='left')
    convert_button=ttk.Button(buttons,text='转换为新副本',command=lambda:run(False));convert_button.pack(side='left',padx=10)
    def close():
        if busy:messagebox.showinfo('正在处理','请等待当前检查或写入完成。')
        else:root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    if smoke:root.after(800,root.destroy)
    root.mainloop()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);p.add_argument('--tlk',type=Path);p.add_argument('--catalog',type=Path);p.add_argument('--report-root',type=Path);p.add_argument('--name');p.add_argument('--scan',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--gui-smoke',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    if not a.source:
        gui(smoke=a.gui_smoke)
        if a.output:a.output.write_text(json.dumps({'ui_smoke':'passed','version':VERSION}),'utf-8')
        return
    require(a.tlk is not None,'命令行模式需要 --tlk。')
    result=json.dumps(convert(a.source,a.tlk,load_catalog(a.catalog),label=a.name,report_root=a.report_root,scan=a.scan),ensure_ascii=False,indent=2)
    if a.output:a.output.write_text(result,'utf-8')
    if sys.stdout is not None:print(result)
if __name__=='__main__':main()
