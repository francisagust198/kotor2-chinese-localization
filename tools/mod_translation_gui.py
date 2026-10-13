"""KOTOR II MOD translation editor, tkinter desktop app. MIT."""
import argparse,json,os,sys,threading,queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import mod_translation_core as core
import mod_translation_ai as ai
class Editor:
    def __init__(self,root):
        self.root=root;self.project=None;self.project_file=None;self.selected=None;self.page=0;self.busy=False;self.events=queue.Queue();self.job_id=0
        root.title('KOTOR II 汉化工作台 0.2.1');root.geometry('1220x880');root.minsize(1050,780);root.configure(bg='#edf2f7')
        style=ttk.Style(root);style.theme_use('clam');style.configure('.',font=('Microsoft YaHei UI',10));style.configure('TFrame',background='#edf2f7');style.configure('TLabel',background='#edf2f7',foreground='#23344b');style.configure('TButton',padding=(10,5));style.configure('Accent.TButton',background='#1f6feb',foreground='white',padding=(14,6));style.map('Accent.TButton',background=[('active','#1659b6')]);style.configure('Treeview',rowheight=29,background='white',fieldbackground='white');style.configure('Treeview.Heading',font=('Microsoft YaHei UI',10,'bold'),padding=6)
        self.api=ai.load_config();self.ai_cancel=threading.Event();self.folder=tk.StringVar();self.tlk=tk.StringVar();self.current=tk.StringVar();self.mod_id=tk.StringVar();self.title=tk.StringVar();self.original_url=tk.StringVar();self.mode=tk.StringVar(value='MOD 局部文本');self.search=tk.StringVar();self.only_empty=tk.BooleanVar();self.status=tk.StringVar(value='1 选择工作模式与来源   →   2 提取 / 翻译   →   3 打包独立汉化 MOD')
        header=ttk.Frame(root,padding=(16,12));header.pack(fill='x');ttk.Label(header,text='KOTOR II 汉化工作台',font=('Microsoft YaHei UI',17,'bold')).pack(side='left');ttk.Button(header,text='教程',command=self.help).pack(side='right')
        modes=ttk.Frame(root,padding=(16,0));modes.pack(fill='x');ttk.Radiobutton(modes,text='MOD 汉化',variable=self.mode,value='MOD 局部文本',command=self.change_mode).pack(side='left',padx=(0,28));ttk.Radiobutton(modes,text='原版文本修正',variable=self.mode,value='本体文本修正',command=self.change_mode).pack(side='left');self.mode_hint=ttk.Label(modes,text='提取原 MOD 的局部文本，生成独立汉化资源 MOD。');self.mode_hint.pack(side='left',padx=24)
        top=ttk.Frame(root,padding=(16,8));top.pack(fill='x');self.input_panel=top
        def path_row(row,label,var,choose):
            lab=ttk.Label(top,text=label);lab.grid(row=row,column=0,sticky='w',pady=3);ttk.Entry(top,textvariable=var).grid(row=row,column=1,sticky='ew',padx=8);ttk.Button(top,text='选择',command=choose).grid(row=row,column=2)
            if row==1:self.tlk_label=lab
        top.columnconfigure(1,weight=1)
        path_row(0,'MOD 文件夹',self.folder,lambda:self.folder.set(filedialog.askdirectory() or self.folder.get()))
        path_row(1,'原文文本表（仅编号文本需要）',self.tlk,lambda:self.tlk.set(filedialog.askopenfilename(filetypes=[('英文文本表','*.tlk')]) or self.tlk.get()))
        path_row(2,'当前主汉化 TLK（本体修正用）',self.current,lambda:self.current.set(filedialog.askopenfilename(filetypes=[('TLK','*.tlk')]) or self.current.get()))
        line=ttk.Frame(top);line.grid(row=3,column=0,columnspan=3,sticky='ew',pady=8)
        ttk.Label(line,text='工程标识').pack(side='left');ttk.Entry(line,textvariable=self.mod_id,width=24).pack(side='left',padx=8);ttk.Label(line,text='独立 MOD 名称').pack(side='left');ttk.Entry(line,textvariable=self.title,width=32).pack(side='left',padx=8);ttk.Button(line,text='提取文本',style='Accent.TButton',command=self.extract).pack(side='right')
        ttk.Label(top,text='原 MOD 链接').grid(row=4,column=0,sticky='w');ttk.Entry(top,textvariable=self.original_url).grid(row=4,column=1,columnspan=2,sticky='ew',padx=8)
        toolbar=ttk.Frame(root,padding=(12,0));toolbar.pack(fill='x')
        for text,command in [('打开工程',self.open),('保存工程',self.save),('导出 CSV',self.export_csv),('导入 CSV',self.import_csv)]:ttk.Button(toolbar,text=text,command=command).pack(side='left',padx=(0,5))
        ttk.Button(toolbar,text='打包独立 MOD',style='Accent.TButton',command=self.build).pack(side='right')
        aibar=ttk.Frame(root,padding=(16,8));aibar.pack(fill='x');ttk.Button(aibar,text='API 设置',command=self.api_settings).pack(side='left');ttk.Button(aibar,text='AI 一键翻译未译条目',command=self.ai_translate).pack(side='left',padx=8);ttk.Button(aibar,text='停止 AI',command=self.ai_cancel.set).pack(side='left');self.ai_progress=ttk.Progressbar(aibar,length=160,mode='determinate');self.ai_progress.pack(side='right');ttk.Label(aibar,text='原文发送到你配置的服务；AI 译文需复核。').pack(side='left',padx=8)
        ttk.Label(root,textvariable=self.status,relief='sunken',anchor='w',padding=6).pack(side='bottom',fill='x')
        filterbar=ttk.Frame(root,padding=(12,0));filterbar.pack(fill='x');ttk.Label(filterbar,text='搜索').pack(side='left');entry=ttk.Entry(filterbar,textvariable=self.search,width=40);entry.pack(side='left',padx=6);entry.bind('<Return>',lambda e:self.refresh(reset=True));ttk.Button(filterbar,text='查找',command=lambda:self.refresh(reset=True)).pack(side='left');ttk.Checkbutton(filterbar,text='只显示未翻译',variable=self.only_empty,command=lambda:self.refresh(reset=True)).pack(side='left',padx=8);ttk.Button(filterbar,text='下一页',command=lambda:self.turn(1)).pack(side='right');ttk.Button(filterbar,text='上一页',command=lambda:self.turn(-1)).pack(side='right')
        pane=ttk.Panedwindow(root,orient='vertical');pane.pack(fill='both',expand=True,padx=12,pady=8)
        frame=ttk.Frame(pane);pane.add(frame,weight=3);self.tree=ttk.Treeview(frame,columns=('where','source','zh'),show='headings',height=6);self.tree.heading('where',text='资源 / 字段 / 编号');self.tree.heading('source',text='英文原文');self.tree.heading('zh',text='译文');self.tree.column('where',width=260);self.tree.column('source',width=360);self.tree.column('zh',width=350);self.tree.pack(side='left',fill='both',expand=True);scroll=ttk.Scrollbar(frame,command=self.tree.yview);scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set);self.tree.bind('<<TreeviewSelect>>',self.select)
        edit=ttk.Frame(pane);pane.add(edit,weight=2);edit.columnconfigure(0,weight=1);edit.columnconfigure(1,weight=1);edit.rowconfigure(1,weight=1);ttk.Label(edit,text='英文原文（只读）').grid(row=0,column=0,sticky='w',pady=6);ttk.Label(edit,text='中文译文（保留 <CUSTOM0>、%d 等变量）').grid(row=0,column=1,sticky='w',pady=6,padx=8);self.source=tk.Text(edit,height=5,width=35,wrap='word',font=('Microsoft YaHei UI',10));self.source.grid(row=1,column=0,sticky='nsew');self.source.configure(state='disabled');self.translation=tk.Text(edit,height=5,width=35,wrap='word',undo=True,font=('Microsoft YaHei UI',11));self.translation.grid(row=1,column=1,sticky='nsew',padx=(8,0));ttk.Button(edit,text='应用译文（Ctrl+Enter）',command=self.apply).grid(row=2,column=1,sticky='e',pady=5)
        root.bind('<Control-Return>',lambda e:self.apply());root.bind('<Control-s>',lambda e:self.save());root.protocol('WM_DELETE_WINDOW',self.close);self.show_mode();root.after(50,self.poll_events)
    def show_mode(self):
        body=self.mode.get()=='本体文本修正'
        if not hasattr(self,'source_controls'):self.source_controls={row:[w for w in self.input_panel.winfo_children() if int(w.grid_info().get('row',-1))==row] for row in [0,2,4]}
        for row,controls in self.source_controls.items():
            visible=(body if row==2 else not body)
            for w in controls:w.grid() if visible else w.grid_remove()
        self.mode_hint.configure(text='修正已有编号文字，生成独立译文包 MOD。' if body else '提取原 MOD 的局部文本，生成独立汉化资源 MOD。')
        self.tlk_label.configure(text='英文原文文本表（TLK）' if body else '原文文本表（仅编号文本需要）')
    def change_mode(self):
        if self.busy:self.mode.set('本体文本修正' if self.project and self.project['mode']=='tlk' else 'MOD 局部文本');return
        if self.project:
            if not messagebox.askyesno('切换工作模式','当前工程不会自动保存。确认已保存需要保留的译文后切换？'):
                self.mode.set('本体文本修正' if self.project['mode']=='tlk' else 'MOD 局部文本');return
            self.project=None;self.project_file=None;self.selected=None;self.tree.delete(*self.tree.get_children());self.translation.delete('1.0','end')
        for row,controls in self.source_controls.items():
            for w in controls:w.grid()
        self.show_mode()
    def api_settings(self):
        if self.busy:return
        dialog=tk.Toplevel(self.root);dialog.title('AI 翻译 API 设置');dialog.geometry('670x550');dialog.transient(self.root);dialog.grab_set();frame=ttk.Frame(dialog,padding=18);frame.pack(fill='both',expand=True)
        values={k:tk.StringVar(value=self.api.get(k,'')) for k in ['endpoint','model','api_key']};remember=tk.BooleanVar(value=bool(self.api.get('remember',False)));json_mode=tk.BooleanVar(value=self.api.get('json_mode',False));batch=tk.IntVar(value=self.api.get('batch_size',8))
        ttk.Label(frame,text='支持 OpenAI 兼容 Chat Completions API',font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w')
        for key,label in [('endpoint','服务基础地址（通常以 /v1 结尾）'),('model','模型名称（按服务商提供的名称填写）'),('api_key','API 密钥')]:
            ttk.Label(frame,text=label).pack(anchor='w',pady=(8,2));ttk.Entry(frame,textvariable=values[key],show='●' if key=='api_key' else '').pack(fill='x')
        options=ttk.Frame(frame);options.pack(fill='x',pady=8);ttk.Label(options,text='每批条数').pack(side='left');ttk.Spinbox(options,from_=1,to=20,textvariable=batch,width=5).pack(side='left',padx=8);ttk.Checkbutton(options,text='JSON 模式（需服务支持）',variable=json_mode).pack(side='left');ttk.Checkbutton(frame,text='在本机加密记住密钥（Windows 用户保护）',variable=remember).pack(anchor='w')
        ttk.Label(frame,text='翻译提示词').pack(anchor='w',pady=(8,2));prompt=tk.Text(frame,height=5,wrap='word',font=('Microsoft YaHei UI',10));prompt.pack(fill='both',expand=True);prompt.insert('1.0',self.api.get('prompt',ai.DEFAULT_PROMPT))
        ttk.Label(frame,text='配置只保存在本机，不进入工程或打包文件。请求可能按服务商规则计费。',wraplength=610).pack(anchor='w',pady=8)
        def accept():
            try:
                config={k:v.get().strip() for k,v in values.items()};config.update(prompt=prompt.get('1.0','end-1c'),batch_size=batch.get(),json_mode=json_mode.get(),remember=remember.get());ai.endpoint_url(config['endpoint'])
                if not config['model']:raise ValueError('请填写模型名称')
                if not 1<=config['batch_size']<=20:raise ValueError('每批条数应为1至20')
                ai.save_config(config,remember.get());self.api=config;dialog.destroy();self.status.set('API 配置已保存，密钥不进入补丁。')
            except Exception as e:messagebox.showerror('配置未保存',str(e),parent=dialog)
        buttons=ttk.Frame(frame);buttons.pack(fill='x');ttk.Button(buttons,text='保存配置',style='Accent.TButton',command=accept).pack(side='right');ttk.Button(buttons,text='取消',command=dialog.destroy).pack(side='right',padx=8)
    def ai_translate(self):
        if not self.guard():return
        self.commit()
        if not self.api.get('api_key') or not self.api.get('model') or not self.api.get('endpoint'):
            self.api_settings();return
        pending=[dict(r) for r in self.project['rows'] if not r.get('zh','').strip()]
        if not pending:messagebox.showinfo('已完成','没有未翻译条目');return
        self.ai_cancel.clear();self.ai_progress.configure(maximum=len(pending),value=0);config=dict(self.api);self.translation.configure(state='disabled')
        next_job=self.job_id+1
        def on_batch(values,done,total):self.events.put((next_job,self.apply_ai_batch,(values,done,total)))
        self.run(lambda:ai.translate(pending,config,on_batch,self.ai_cancel),lambda report:(self.refresh(),self.status.set(f"AI {'已停止' if report['cancelled'] else '翻译完成'}：{report['translated']}/{report['total']} 条；请复核并保存工程。")))
        self.status.set(f'AI 正在翻译：0/{len(pending)} 条；每批完成后刷新，可选择条目查看。')
    def apply_ai_batch(self,values,done,total):
        first=None
        for index,r in enumerate(self.project['rows']):
            if r['key'] in values and not r['zh'].strip():
                r['zh']=values[r['key']];r['translation_origin']='ai_draft'
                if first is None:first=index
        if self.selected is None and first is not None:self.selected=first
        self.refresh()
        if self.selected is not None:self.show_row(self.selected)
        self.ai_progress.configure(value=done);self.status.set(f'AI 已译 {done}/{total} 条；可边译边查看，译文为待复核草稿。')
        if self.project_file:core.save_project(self.project,self.project_file)
    def drain_events(self):
        for _ in range(100):
            try:job,callback,args=self.events.get_nowait()
            except queue.Empty:break
            if job!=self.job_id:continue
            try:callback(*args)
            except Exception as error:
                self.ai_cancel.set();self.job_id+=1;self.finished(lambda value:None,None,str(error))
    def poll_events(self):
        self.drain_events();self.root.after(50,self.poll_events)
    def run(self,task,done):
        if self.busy:return
        self.busy=True;self.job_id+=1;job=self.job_id;self.status.set('处理中，请稍候…')
        def work():
            try:value=task();self.events.put((job,self.finished,(done,value,None)))
            except Exception as exc:self.events.put((job,self.finished,(done,None,str(exc))))
        threading.Thread(target=work,daemon=True).start()
    def finished(self,done,value,error):
        self.busy=False;self.translation.configure(state='normal')
        if error:self.status.set('操作未完成');messagebox.showerror('请检查',error)
        else:done(value)
    def guard(self):
        if self.busy:return False
        if self.project is None:messagebox.showinfo('提示','请先提取文本或打开工程');return False
        return True
    def extract(self):
        if self.busy:return
        if self.project and not messagebox.askyesno('新工程','重新提取会替换当前工程。请确认已经保存需要保留的译文。继续？'):return
        folder=self.folder.get();tlk=self.tlk.get();mode='tlk' if self.mode.get()=='本体文本修正' else 'mod'
        if mode=='tlk':folder=str(Path(tlk).parent)
        if not tlk and (Path(folder)/'dialog.tlk').is_file():tlk=str(Path(folder)/'dialog.tlk');self.tlk.set(tlk)
        def done(p):
            self.project=p;self.project_file=None;self.selected=None;p['mod_id']=self.mod_id.get();self.refresh(reset=True)
            if p['warnings']:messagebox.showinfo('提取提示','\n'.join(p['warnings'][:20])+('\n更多提示保存在工程中。' if len(p['warnings'])>20 else ''))
            if not p['rows']:messagebox.showinfo('没有文本','未找到支持的文本。检查目录或英文TLK选择；模块容器需先提取资源。')
        self.run(lambda:core.extract(folder,tlk or None,mode),done)
    def apply(self):
        if not self.guard() or self.selected is None:return
        self.project['rows'][self.selected]['zh']=self.translation.get('1.0','end-1c');self.refresh()
    def commit(self):
        if not self.busy and self.project and self.selected is not None:self.project['rows'][self.selected]['zh']=self.translation.get('1.0','end-1c')
        if self.project:self.project.update(mod_id=self.mod_id.get(),title=self.title.get(),original_mod_url=self.original_url.get())
    def refresh(self,reset=False):
        if self.project is None:return
        if reset:self.page=0
        query=self.search.get().casefold();matches=[i for i,r in enumerate(self.project['rows']) if (not self.only_empty.get() or not r['zh'].strip()) and (not query or query in (r['key']+' '+r['source']+' '+r['zh']).casefold())];last=max(0,(len(matches)-1)//250);self.page=min(max(self.page,0),last)
        visible=matches[self.page*250:(self.page+1)*250];wanted={str(i) for i in visible};existing=set(self.tree.get_children())
        for iid in existing-wanted:self.tree.delete(iid)
        for position,i in enumerate(visible):
            r=self.project['rows'][i];values=(r['key'],r['source'].replace('\n',' ')[:160],r['zh'].replace('\n',' ')[:160]);iid=str(i)
            if iid in existing:self.tree.item(iid,values=values)
            else:self.tree.insert('', 'end',iid=iid,values=values)
            self.tree.move(iid,'',position)
        translated=sum(bool(r['zh'].strip()) for r in self.project['rows']);self.status.set(f"共 {len(self.project['rows'])} 条，已译 {translated} 条；筛选 {len(matches)} 条，第 {self.page+1}/{last+1} 页。")
    def turn(self,delta):
        if self.guard():self.commit();self.page+=delta;self.refresh()
    def select(self,event=None):
        sel=self.tree.selection()
        if not sel:return
        index=int(sel[0])
        if index==self.selected:return
        self.commit();self.selected=index;self.show_row(index)
    def show_row(self,index):
        r=self.project['rows'][index];self.source.configure(state='normal');self.source.delete('1.0','end');self.source.insert('1.0',r['source']);self.source.configure(state='disabled');self.translation.configure(state='normal');self.translation.delete('1.0','end');self.translation.insert('1.0',r['zh']);self.translation.configure(state='disabled' if self.busy else 'normal')
    def save(self):
        if not self.guard():return
        self.commit();p=self.project_file or filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('翻译工程','*.json')])
        if p:
            try:core.save_project(self.project,p);self.project_file=p;self.status.set('工程已保存：'+p)
            except Exception as e:messagebox.showerror('保存失败',str(e))
    def open(self):
        if self.busy:return
        p=filedialog.askopenfilename(filetypes=[('翻译工程','*.json')])
        if not p:return
        if self.project and not messagebox.askyesno('打开工程','当前译文不会自动保存。确定打开其他工程？'):return
        try:
            self.project=core.load_project(p);self.project_file=p;self.selected=None;self.folder.set(self.project['source_root']);self.tlk.set(self.project['source_tlk']);self.mod_id.set(self.project['mod_id']);self.title.set(self.project.get('title',''));self.original_url.set(self.project.get('original_mod_url',''));self.mode.set('本体文本修正' if self.project['mode']=='tlk' else 'MOD 局部文本');self.show_mode();self.refresh(reset=True)
        except Exception as e:messagebox.showerror('打开失败',str(e))
    def export_csv(self):
        if not self.guard():return
        self.commit();p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('翻译表','*.csv')])
        if p:core.export_csv(self.project,p);self.status.set('CSV 已导出：'+p)
    def import_csv(self):
        if not self.guard():return
        p=filedialog.askopenfilename(filetypes=[('翻译表','*.csv')])
        if p:
            try:self.commit();core.import_csv(self.project,p);self.selected=None;self.translation.delete('1.0','end');self.refresh(reset=True)
            except Exception as e:messagebox.showerror('导入失败',str(e))
    def build(self):
        if not self.guard():return
        self.commit();parent=filedialog.askdirectory(title='选择补丁输出的父目录（不要选择原MOD内）')
        if not parent:return
        name=self.mod_id.get()
        if not name:messagebox.showinfo('提示','请填写工程标识，例如 effix.carthjacket.chs');return
        output=Path(parent)/(name+'-chs');project=json.loads(json.dumps(self.project));current=self.current.get()
        self.run(lambda:core.build(project,output,current_tlk=current or None),lambda report:(self.status.set('补丁已生成：'+str(output)+'.zip'),messagebox.showinfo('打包完成',f"已生成 {report['translated_entries']} 条译文的补丁和ZIP。\n{output}\n\n原MOD未修改，输出不含DLL。请先实际测试再发布。")))
    def help(self):
        import webbrowser
        webbrowser.open('https://github.com/francisagust198/kotor2-chinese-localization/blob/main/docs/MOD_TRANSLATION_TUTORIAL.md')
    def close(self):
        if self.busy:messagebox.showinfo('处理中','请等待当前操作完成');return
        if self.project:
            answer=messagebox.askyesnocancel('退出','退出前保存翻译工程？')
            if answer is None:return
            if answer:
                self.save()
                if not self.project_file:return
        self.root.destroy()
def main():
    p=argparse.ArgumentParser();p.add_argument('--selfcheck',type=Path);a=p.parse_args()
    if a.selfcheck:
        a.selfcheck.write_text(json.dumps(dict(version=core.VERSION,tkinter=tk.TkVersion,map_available=core.resource_path('current-map.json').is_file(),source_catalog_available=core.resource_path('overlay-current-sources.json.gz').is_file())),encoding='utf8');return
    root=tk.Tk();Editor(root);root.mainloop()
if __name__=='__main__':main()
