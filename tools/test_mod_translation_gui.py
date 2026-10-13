"""UI-controller regressions without desktop automation or live API calls."""
import queue,threading,time,unittest
from mod_translation_gui import Editor
class Value:
    def __init__(self,value=''):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value
class Text:
    def __init__(self,value=''):self.value=value;self.state='normal'
    def configure(self,**kw):self.state=kw.get('state',self.state)
    def delete(self,*args):self.value=''
    def insert(self,index,text):self.value=text
    def get(self,*args):return self.value
class Tree:
    def __init__(self):self.rows={};self.order=[];self.chosen=();self.deleted=[]
    def get_children(self):return tuple(self.order)
    def delete(self,*ids):
        for iid in ids:
            self.deleted.append(iid);self.rows.pop(iid);self.order.remove(iid)
            if iid in self.chosen:self.chosen=()
    def insert(self,parent,where,iid,values):self.rows[iid]=values;self.order.append(iid)
    def item(self,iid,**kw):self.rows[iid]=kw['values']
    def move(self,iid,parent,position):self.order.remove(iid);self.order.insert(position,iid)
    def selection(self):return self.chosen
class Progress:
    def configure(self,**kw):self.value=kw.get('value')
class ForbiddenWorkerRoot:
    def after(self,*args):raise AssertionError('worker must not access Tk')
def editor():
    e=Editor.__new__(Editor);e.project={'rows':[dict(key='one',source='First',zh=''),dict(key='two',source='Second',zh='')]};e.project_file=None;e.selected=0;e.page=0;e.busy=True;e.job_id=1;e.events=queue.Queue();e.root=ForbiddenWorkerRoot();e.tree=Tree();e.source=Text('First');e.translation=Text('');e.search=Value();e.only_empty=Value(False);e.status=Value();e.mod_id=Value('test');e.title=Value('Test');e.original_url=Value();e.ai_cancel=threading.Event();e.ai_progress=Progress();e.refresh();e.tree.chosen=('0',);return e
class GuiTests(unittest.TestCase):
    def test_first_batch_visible_before_job_finishes_and_selection_retained(self):
        e=editor();e.events.put((1,e.apply_ai_batch,({'one':'第一条'},1,2)));e.drain_events()
        self.assertTrue(e.busy);self.assertEqual(e.tree.rows['0'][2],'第一条');self.assertEqual(e.translation.value,'第一条');self.assertEqual(e.tree.chosen,('0',));self.assertEqual(e.tree.deleted,[]);self.assertEqual(e.ai_progress.value,1)
    def test_navigation_during_translation_is_readonly_and_does_not_erase_draft(self):
        e=editor();e.apply_ai_batch({'one':'第一条'},1,2);e.translation.value='stale editor value';e.tree.chosen=('1',);e.select();self.assertEqual(e.project['rows'][0]['zh'],'第一条');self.assertEqual(e.selected,1);self.assertEqual(e.translation.state,'disabled');e.apply_ai_batch({'two':'第二条'},2,2);self.assertEqual(e.translation.value,'第二条')
    def test_untranslated_filter_updates_but_completed_selected_preview_remains(self):
        e=editor();e.only_empty.set(True);e.apply_ai_batch({'one':'第一条'},1,2);self.assertEqual(e.tree.get_children(),('1',));self.assertEqual(e.translation.value,'第一条');self.assertTrue(e.busy)
    def test_queued_batches_before_completion_keep_latest_preview(self):
        e=editor();e.selected=1;e.events.put((1,e.apply_ai_batch,({'one':'第一条'},1,2)));e.events.put((1,e.apply_ai_batch,({'two':'第二条'},2,2)));e.events.put((1,e.finished,(lambda report:e.refresh(),{},None)));e.drain_events();self.assertFalse(e.busy);self.assertEqual(e.translation.value,'第二条');self.assertEqual(e.translation.state,'normal')
    def test_unselected_editor_previews_first_completed_translation(self):
        e=editor();e.selected=None;e.apply_ai_batch({'two':'第二条'},1,2);self.assertEqual(e.selected,1);self.assertEqual(e.source.value,'Second');self.assertEqual(e.translation.value,'第二条')
    def test_worker_uses_queue_and_never_tk_after(self):
        e=editor();e.busy=False;gate=threading.Event();e.run(lambda:'ready',lambda value:gate.set())
        for _ in range(100):
            if not e.events.empty():break
            time.sleep(.005)
        self.assertFalse(gate.is_set());e.drain_events();self.assertTrue(gate.is_set());self.assertFalse(e.busy)
if __name__=='__main__':unittest.main()
