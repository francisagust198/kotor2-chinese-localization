import unittest
from dialogue_corrections import apply_approved,digest
class DialogueCorrectionsTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(id='test:1',source_sha256='verified-source',zh='奖励任务：<FullName> {cue}')
        self.edit=dict(id='test:1',source_sha256='verified-source',before=self.row['zh'],before_sha256=digest(self.row['zh']),after='附加任务：<FullName> {cue}')
    def test_approved_and_idempotent(self):
        revised,changed=apply_approved(self.row,self.edit);self.assertTrue(changed)
        self.assertEqual(revised['zh'],'附加任务：<FullName> {cue}')
        self.assertFalse(apply_approved(revised,self.edit)[1])
    def test_source_and_id_guard(self):
        for row in [dict(self.row,id='other'),dict(self.row,source_sha256='changed')]:
            with self.assertRaises(ValueError):apply_approved(row,self.edit)
    def test_new_translation_preserved(self):
        with self.assertRaises(ValueError):apply_approved(dict(self.row,zh='另一份人工修订'),self.edit)
    def test_variables_and_notes_preserved(self):
        with self.assertRaises(ValueError):apply_approved(self.row,dict(self.edit,after='附加任务'))
if __name__=='__main__':unittest.main()
