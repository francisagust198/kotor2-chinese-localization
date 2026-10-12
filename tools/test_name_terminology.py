import json, unittest
from pathlib import Path
from name_terminology import compile_rules, correct

class NameTerminologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=compile_rules(json.loads((Path(__file__).resolve().parents[1]/'glossary/person-name-rules.json').read_text(encoding='utf-8')))
    def fix(self,source,zh):return correct(source,zh,self.rules)[0]
    def test_components_keep_their_original_scope(self):
        self.assertEqual(self.fix('Chodo talks to Habat.', '长堂和黑贝谈话。'), '乔多和哈巴特谈话。')
        self.assertEqual(self.fix('Loppak meets Slusk.', '罗帕克见到斯拉克斯。'), '洛帕克见到斯拉斯克。')
    def test_full_name_does_not_repeat_surname(self):
        self.assertEqual(self.fix('Loppak Slusk greets Loppak Slusk.', '洛帕克·斯拉斯克·斯拉克斯向洛帕克·斯拉斯克·斯拉克斯问好。'), '洛帕克·斯拉斯克向洛帕克·斯拉斯克问好。')
    def test_source_gate_and_notes(self):
        text='{Chodo enters}长堂 <FullName> %s'
        self.assertEqual(self.fix('{Chodo enters}Hello.',text),text)
        self.assertEqual(self.fix('Chodo greets <FullName> %s.',text),'{Chodo enters}乔多 <FullName> %s')
        self.assertEqual(self.fix('Open Starport Visas.', '开放星港签证。'),'开放星港签证。')
        self.assertEqual(self.fix('Random shadow.', '随机暗影。'),'随机暗影。')
        self.assertEqual(self.fix('Set 203TEL_Habat to 11.', '将黑贝变量设为 11。'),'将黑贝变量设为 11。')
        self.assertEqual(self.fix('Jekk Jekk Tarr.', '杰克·杰克·塔尔。'),'杰克·杰克·塔尔。')
    def test_family_surname_is_not_expanded_to_an_individual(self):
        self.assertEqual(self.fix('Ulic Qel Droma.', '乌里克奎卓马'), '乌利克·凯尔-德罗马')
    def test_idempotent(self):
        source='Loppak Slusk and Chodo Habat.'
        first=self.fix(source,'洛帕克·斯拉斯克·斯拉克斯和长堂黑贝。')
        self.assertEqual(self.fix(source,first),first)

if __name__=='__main__':unittest.main()
