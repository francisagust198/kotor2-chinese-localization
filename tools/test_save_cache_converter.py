import collections,struct,unittest,gzip,json,tempfile
from pathlib import Path
from unittest.mock import patch
from save_cache_converter import Converter,GFF,digest,convert,load_catalog

class CatalogSelectionRegression(unittest.TestCase):
    def test_workshop_catalog_overrides_bundled_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=Path(tmp)/'app';bundle=Path(tmp)/'bundle';app.mkdir();bundle.mkdir()
            for folder,version in [(app,'current'),(bundle,'old')]:
                with gzip.open(folder/'save-cache-catalog.json.gz','wt',encoding='utf-8') as f:json.dump({'version':version},f)
            with patch('save_cache_converter.application_dir',return_value=app),patch('save_cache_converter.resource_dir',return_value=bundle):
                self.assertEqual(load_catalog()['version'],'current')
                (app/'save-cache-catalog.json.gz').unlink()
                self.assertEqual(load_catalog()['version'],'old')

    def test_explicit_catalog_is_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            explicit=Path(tmp)/'chosen.json.gz'
            with gzip.open(explicit,'wt',encoding='utf-8') as f:json.dump({'version':'chosen'},f)
            self.assertEqual(load_catalog(explicit)['version'],'chosen')
def local(ref,text,lang=0):
    body=struct.pack('<II',ref,1)+struct.pack('<II',lang,len(text))+text
    return struct.pack('<I',len(body))+body
def gff(rows):
    labels=b''.join(name.encode().ljust(16,b'\0') for name,k,value in rows);data=bytearray();fields=bytearray()
    for i,(name,k,value) in enumerate(rows):
        if isinstance(value,bytes):v=len(data);data+=value
        else:v=value
        fields+=struct.pack('<III',k,i,v)
    indices=b''.join(struct.pack('<I',i) for i in range(len(rows))) if len(rows)>1 else b''
    sections=[struct.pack('<III',0,0,len(rows)),fields,labels,data,indices,b'']
    out=bytearray(b'UTC V3.2'+b'\0'*48)
    for i,s in enumerate(sections):struct.pack_into('<II',out,8+8*i,len(out),[1,len(rows),len(rows),len(data),len(indices),0][i]);out+=s
    return bytes(out)
class Table:
    def raw(self,ref):return {7:b'new-name',8:b'new-description'}.get(ref,b'')
def converter():return Converter(Table(),{'hashes_by_strref':{'7':[digest(b'old-name')],'8':[digest(b'old-description')]}})
class SaveConverterRegression(unittest.TestCase):
    def test_old_cache_cleared_custom_unknown_and_invalid_preserved(self):
        b=gff([('FirstName',12,local(7,b'old-name')),('Description',12,local(8,b'custom-description')),('LocName',12,local(0xffffffff,b'custom-name')),('Text',12,local(999,b'old-name')),('Experience',4,54321),('HP',8,0x42c80000),('Rotation',9,struct.pack('<d',2.5))])
        c=converter();new=c.transform(b,'test');after=GFF(new);before=GFF(b)
        self.assertEqual(after.local(0),(7,[]))
        for i in range(1,len(before.rows)):
            self.assertEqual(after.rows[i][3] if after.rows[i][3] is not None else after.rows[i][2],before.rows[i][3] if before.rows[i][3] is not None else before.rows[i][2])
        again=converter();self.assertEqual(again.transform(new,'test'),new);self.assertFalse(again.events)
    def test_player_name_protected(self):
        b=gff([('FirstName',12,local(7,b'old-name')),('IsPC',0,1)])
        self.assertEqual(converter().transform(b,'player'),b)
    def test_language_and_history_preserved(self):
        for b in [gff([('Text',12,local(7,b'old-name',2))]),gff([('HistoryText',12,local(7,b'old-name'))])]:self.assertEqual(converter().transform(b,'test'),b)
    def test_malformed_string_rejected(self):
        b=gff([('FirstName',12,local(7,b'old-name'))]);out=bytearray(b);data=struct.unpack_from('<I',out,32)[0];struct.pack_into('<I',out,data+8,900)
        with self.assertRaises(ValueError):converter().transform(bytes(out),'bad')
    def test_archive_identity_and_untouched_resource(self):
        changed=gff([('FirstName',12,local(7,b'old-name'))]);unchanged=b'original script bytes'
        b=bytearray(b'SAV V1.0'+b'\0'*152);struct.pack_into('<I',b,16,2);struct.pack_into('<II',b,24,160,208)
        for i,name in enumerate((b'creature',b'script')):b+=struct.pack('<16sIHH',name,i,2027,0)
        for i,body in enumerate((changed,unchanged)):b+=struct.pack('<II',224+(0 if i==0 else len(changed)),len(body))
        b+=changed+unchanged;result=converter().transform(bytes(b),'sav')
        self.assertEqual(result[:208],b[:208]);offset,size=struct.unpack_from('<II',result,216);self.assertEqual(result[offset:offset+size],unchanged)
        offset,size=struct.unpack_from('<II',result,208);self.assertEqual(GFF(result[offset:offset+size]).local(0),(7,[]))
    def test_running_game_refuses_before_any_write(self):
        with patch('save_cache_converter.running_game',return_value=True):
            with self.assertRaisesRegex(ValueError,'退出游戏'):convert('missing','missing',{})
    def test_same_resource_name_has_unique_event_identity(self):
        body=gff([('FirstName',12,local(7,b'old-name'))]);b=bytearray(b'SAV V1.0'+b'\0'*152)
        struct.pack_into('<I',b,16,2);struct.pack_into('<II',b,24,160,208)
        for i in range(2):b+=struct.pack('<16sIHH',b'same',i,2027+i,0)
        for i in range(2):b+=struct.pack('<II',224+i*len(body),len(body))
        b+=body+body;c=converter();c.transform(bytes(b),'sav')
        self.assertEqual(len(c.events),2);self.assertNotEqual(c.events[0]['path'],c.events[1]['path'])
if __name__=='__main__':unittest.main()
