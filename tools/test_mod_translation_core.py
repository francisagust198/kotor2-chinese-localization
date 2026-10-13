import csv,gzip,hashlib,json,struct,tempfile,unittest
from pathlib import Path
from mod_translation_core import extract,build,save_project,load_project,export_csv,import_csv
from save_cache_converter import GFF
from tlk_overlay import encode
def fixture_gff(path):
    slots=[(0,b'Soldier'),(1,b'Female Soldier'),(2,b'Other language')];loc=struct.pack('<II',0xffffffff,len(slots))
    for lang,text in slots:loc+=struct.pack('<II',lang,len(text))+text
    loc=struct.pack('<I',len(loc))+loc;data=loc+b'\x05voice';labels=b'LocalizedName\0\0\0'+b'Accuracy'.ljust(16,b'\0')+b'Sound'.ljust(16,b'\0');assert len(labels)==48
    sections=[struct.pack('<III',0,0,3),struct.pack('<III',12,0,0)+struct.pack('<III',4,1,7)+struct.pack('<III',11,2,len(loc)),labels,data,struct.pack('<III',0,1,2),b''];out=bytearray(b'UTI V3.2'+b'\0'*48)
    for i,s in enumerate(sections):struct.pack_into('<II',out,8+8*i,len(out),[1,3,3][i] if i<3 else len(s));out+=s
    path.write_bytes(out)
def fixture_tlk(path,text):
    entries=bytearray(80);struct.pack_into('<I16sIIIIf',entries,40,1,b'voice',0,0,0,len(text),1.5);path.write_bytes(b'TLK V3.0'+struct.pack('<III',0,2,100)+entries+text)
class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name);self.source=self.r/'source';self.source.mkdir();fixture_gff(self.source/'item.uti');self.mapping=self.r/'map.json';self.mapping.write_text(json.dumps({'士':'80','兵':'81','女':'82'}));self.p=extract(self.source);self.p['mod_id']='test.item'
    def tearDown(self):self.tmp.cleanup()
    def test_inline_resource_preserves_gender_other_languages_stats_voice_and_source(self):
        before=(self.source/'item.uti').read_bytes();self.p['rows'][0]['zh']='士兵';report=build(self.p,self.r/'patch',self.mapping);a=GFF(before);b=GFF((self.r/'patch/override/item.uti').read_bytes());self.assertEqual(b.local(0),(0xffffffff,[(0,b'\x80\x81'),(1,b'Female Soldier'),(2,b'Other language')]));self.assertEqual(a.rows[1],b.rows[1]);self.assertEqual(a.rows[2][:2]+a.rows[2][3:],b.rows[2][:2]+b.rows[2][3:]);self.assertEqual((self.source/'item.uti').read_bytes(),before);self.assertFalse(report['main_tlk_written']);self.assertFalse((self.r/'patch/localization').exists());self.assertTrue((self.r/'patch.zip').exists())
    def test_projects_and_csv_roundtrip_reject_changed_source(self):
        save_project(self.p,self.r/'p.json');p=load_project(self.r/'p.json');export_csv(p,self.r/'p.csv');text=(self.r/'p.csv').read_text(encoding='utf-8-sig');(self.r/'p.csv').write_text(text.replace('Soldier,','Changed,'),encoding='utf-8-sig')
        with self.assertRaises(ValueError):import_csv(p,self.r/'p.csv')
        self.assertTrue(all(not r['zh'] for r in p['rows']))
    def test_source_updates_block_build(self):
        self.p['rows'][0]['zh']='士兵';(self.source/'item.uti').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'已更新'):build(self.p,self.r/'patch',self.mapping)
        self.assertFalse((self.r/'patch').exists())
    def test_missing_glyph_and_variables_block_build(self):
        for text in ['不存在','士兵 %d']:
            self.p['rows'][0]['zh']=text
            with self.assertRaises(ValueError):build(self.p,self.r/'patch',self.mapping)
    def test_duplicate_resource_names_and_existing_output_rejected(self):
        (self.source/'other').mkdir();fixture_gff(self.source/'other/item.uti');p=extract(self.source);p['mod_id']='test.item'
        for r in p['rows']:r['zh']='士兵'
        with self.assertRaisesRegex(ValueError,'同名'):build(p,self.r/'patch',self.mapping)
        (self.r/'already.zip').write_bytes(b'preserve')
        with self.assertRaises(ValueError):build(p,self.r/'already',self.mapping)
        self.assertEqual((self.r/'already.zip').read_bytes(),b'preserve')
    def test_tlk_correction_guard_accepts_english_and_current_chinese_without_writing_tables(self):
        original=self.r/'english.tlk';current=self.r/'current.tlk';fixture_tlk(original,b'Soldier');fixture_tlk(current,b'\x80\x81');catalog=self.r/'sources.json.gz'
        with gzip.open(catalog,'wt',encoding='utf8') as f:json.dump({'1':hashlib.sha256(b'Soldier').hexdigest()},f)
        p=extract(self.source,original,'tlk');p['mod_id']='test.correction';p['rows'][0]['zh']='女兵';before=(original.read_bytes(),current.read_bytes());report=build(p,self.r/'tlkpatch',self.mapping,current,catalog)
        self.assertEqual(report['tlk_pack']['records'],2);self.assertEqual(before,(original.read_bytes(),current.read_bytes()));self.assertTrue((self.r/'tlkpatch/localization/chs-overlay.ini').exists());self.assertFalse((self.r/'tlkpatch/dialog.tlk').exists())
    def test_unsupported_module_is_reported(self):
        (self.source/'dialog.mod').write_bytes(b'unsupported');p=extract(self.source);self.assertIn('模块容器',p['warnings'][0])
if __name__=='__main__':unittest.main()
