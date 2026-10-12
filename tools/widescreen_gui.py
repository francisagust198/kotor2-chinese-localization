"""Read GFF GUI trees and patch fields without rewriting unrelated resources."""
import struct
from pathlib import Path

class Gui:
    def __init__(self, data):
        self.data=bytearray(data)
        if data[:8]!=b'GUI V3.2': raise ValueError('Expected GUI V3.2')
        self.so,self.sc,self.fo,self.fc,self.lo,self.lc,self.do,self.dc,self.io,self.ic,self.lio,self.lic=struct.unpack_from('<12I',data,8)
        self.labels=[data[self.lo+i*16:self.lo+(i+1)*16].split(b'\0')[0].decode('ascii') for i in range(self.lc)]
    def fields(self,index):
        _,value,count=struct.unpack_from('<III',self.data,self.so+index*12)
        indices=[] if not count else [value] if count==1 else struct.unpack_from('<'+'I'*count,self.data,self.io+value)
        return {self.labels[struct.unpack_from('<III',self.data,self.fo+i*12)[1]]:i for i in indices}
    def value(self,field):
        kind,_,v=struct.unpack_from('<III',self.data,self.fo+field*12)
        if kind==5:return struct.unpack('<i',struct.pack('<I',v))[0]
        if kind in (0,1,2,3,4,14):return v
        if kind==8:return struct.unpack('<f',struct.pack('<I',v))[0]
        if kind in (10,11):
            q=self.do+v
            if kind==10:n=struct.unpack_from('<I',self.data,q)[0];q+=4
            else:n=self.data[q];q+=1
            return bytes(self.data[q:q+n]).decode('latin1')
        if kind==15:
            q=self.lio+v;n=struct.unpack_from('<I',self.data,q)[0]
            return list(struct.unpack_from('<'+'I'*n,self.data,q+4))
        return {'type':kind,'offset':v}
    def get(self,index,key,default=None):
        f=self.fields(index).get(key)
        return default if f is None else self.value(f)
    def set_number(self,index,key,value):
        field=self.fields(index)[key];kind=struct.unpack_from('<I',self.data,self.fo+field*12)[0]
        assert kind in (4,5,8)
        struct.pack_into('<f' if kind==8 else '<i' if kind==5 else '<I',self.data,self.fo+field*12+8,value)
    def set_resref(self,index,key,value):
        field=self.fields(index)[key];kind,_,offset=struct.unpack_from('<III',self.data,self.fo+field*12)
        assert kind==11
        raw=value.encode('ascii');assert len(raw)<=16
        # Append field data before index tables and adjust their absolute offsets.
        q=self.do+self.dc
        self.data[q:q]=bytes([len(raw)])+raw
        struct.pack_into('<I',self.data,self.fo+field*12+8,self.dc)
        added=len(raw)+1;self.dc+=added;self.io+=added;self.lio+=added
        struct.pack_into('<I',self.data,36,self.dc)
        struct.pack_into('<I',self.data,40,self.io)
        struct.pack_into('<I',self.data,48,self.lio)
    def controls(self):return self.get(0,'CONTROLS',[])
    def summary(self):
        rows=[]
        for index in [0]+self.controls():
            extent=self.get(index,'EXTENT');text=self.get(index,'TEXT')
            rows.append({'index':index,'tag':self.get(index,'TAG'),'parent':self.get(index,'Obj_Parent'),
                'extent':{k:self.get(extent,k) for k in ('LEFT','TOP','WIDTH','HEIGHT')} if extent is not None else None,
                'font':self.get(text,'FONT') if isinstance(text,int) else None})
        return rows

def extract_gui(game):
    key=(game/'chitin.key').read_bytes()
    assert key[:8]==b'KEY V1  '
    bc,kc,bo,ko=struct.unpack_from('<4I',key,8)
    files=[]
    for i in range(bc):
        _,offset,length,_=struct.unpack_from('<IIHH',key,bo+i*12)
        files.append(key[offset:offset+length].rstrip(b'\0').decode('ascii').replace('\\','/'))
    cache={};result={}
    for i in range(kc):
        name,kind,res=struct.unpack_from('<16sHI',key,ko+i*22)
        if kind!=2047:continue
        bifindex=res>>20;entry=res&0xfffff
        if bifindex not in cache:cache[bifindex]=(game/files[bifindex]).read_bytes()
        bif=cache[bifindex];count,_,off=struct.unpack_from('<III',bif,8)
        assert entry<count
        _,start,size,bkind=struct.unpack_from('<4I',bif,off+entry*16)
        assert bkind==kind
        result[name.rstrip(b'\0').decode('ascii')+'.gui']=bytes(bif[start:start+size])
    return result
