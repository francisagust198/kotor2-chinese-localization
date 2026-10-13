import io,json,os,tempfile,threading,unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from mod_translation_ai import request_batch,translate,endpoint_url,protect,save_config,load_config
class FakeClient:
    def __init__(self,reply):self.reply=reply;self.requests=[]
    def open(self,request,timeout):
        self.requests.append(json.loads(request.data));return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps({'translations':self.reply},ensure_ascii=False)}}]}).encode())
class AiTests(unittest.TestCase):
    def setUp(self):self.config=dict(endpoint='https://example.test/v1',model='test-model',api_key='not-a-real-key',batch_size=1);self.rows=[dict(key='one',source='Hello <CUSTOM0>',zh=''),dict(key='two',source='Soldier',zh='existing')]
    def test_request_preserves_ids_and_tokens(self):
        client=FakeClient([dict(id='one',zh='你好 <CUSTOM0>')]);result=request_batch(self.rows[:1],self.config,client);self.assertEqual(result['one'],'你好 <CUSTOM0>');self.assertEqual(client.requests[0]['model'],'test-model');self.assertNotIn('not-a-real-key',json.dumps(client.requests[0]))
    def test_actual_loopback_http_roundtrip(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append((self.path,self.headers['Authorization'],data));result={'choices':[{'message':{'content':json.dumps({'translations':[{'id':'one','zh':'你好 <CUSTOM0>'}]})}}]};body=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            config=dict(self.config,endpoint='http://127.0.0.1:'+str(server.server_port)+'/v1');result=request_batch(self.rows[:1],config);self.assertEqual(result['one'],'你好 <CUSTOM0>');self.assertEqual(seen[0][0],'/v1/chat/completions');self.assertEqual(seen[0][1],'Bearer not-a-real-key')
        finally:server.shutdown();server.server_close();thread.join()
    def test_missing_tokens_and_unknown_ids_rejected(self):
        for reply in [[dict(id='one',zh='你好')],[dict(id='other',zh='你好')],[]]:
            with self.assertRaises(ValueError):request_batch(self.rows[:1],self.config,FakeClient(reply))
    def test_only_untranslated_rows_sent_and_cancel_after_batch_keeps_result(self):
        rows=self.rows+[dict(key='three',source='Text',zh='')];cancel=threading.Event();got=[]
        def batch(values,done,total):got.append(values);cancel.set()
        report=translate(rows,self.config,batch,cancel,FakeClient([dict(id='one',zh='你好 <CUSTOM0>')]))
        self.assertEqual(report,dict(translated=1,total=2,cancelled=True));self.assertEqual(len(got),1);self.assertEqual(rows[1]['zh'],'existing')
    def test_plaintext_remote_http_and_credential_urls_rejected(self):
        for value in ['http://example.test/v1','https://key:pass@example.test','https://example.test?api_key=secret']:
            with self.assertRaises(ValueError):endpoint_url(value)
        self.assertEqual(endpoint_url('http://127.0.0.1:8080/v1'),'http://127.0.0.1:8080/v1/chat/completions')
    def test_session_key_not_saved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json';save_config(self.config,False,p);self.assertNotIn('not-a-real-key',p.read_text());self.assertFalse(load_config(p)['api_key'])
    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_windows_encrypted_key_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json';save_config(self.config,True,p);self.assertNotIn('not-a-real-key',p.read_text());self.assertEqual(load_config(p)['api_key'],'not-a-real-key')
if __name__=='__main__':unittest.main()
