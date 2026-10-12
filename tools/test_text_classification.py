import unittest
from text_classification import structural_only, latin_designation

class ClassificationRegression(unittest.TestCase):
    def test_player_text_is_not_a_note(self):
        for text in ('Oh no!{Fight starts}', 'Door{Entrance}', '{turns around}What?',
                     '[Atton has learned Force Sight.]', '[Next Page]', 'Two.', '[Repair]', '[Computer]',
                     '{Gameplay Programmer: fade out}You are not alone.'):
            self.assertFalse(structural_only(text),text)

    def test_actual_markers_remain(self):
        for text in ('{Fight starts}','{Beat}{turns around}', 'wp_atton_free',
                     '<FullName>', '<CUSTOM0> <CUSTOM1>', '%d',
                     '[GP: Cut to the next scene.]',
                     'T3M4 **Do Not Translate This**'):
            self.assertTrue(structural_only(text),text)

    def test_english_dialogue_cannot_be_a_designation(self):
        for text in ('Two.','Do it.','You cannot.','[Leave.]','Master'):
            self.assertFalse(latin_designation(text),text)
        for text in ('HK-47','T3-M4','<CUSTOM0>','Dee-deet, reee-deet?'):
            # Placeholders are handled by the separate placeholder validator.
            if text!='<CUSTOM0>': self.assertTrue(latin_designation(text),text)

if __name__=='__main__': unittest.main()
