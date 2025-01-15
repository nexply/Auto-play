import unittest

class TestMidiPlayer(unittest.TestCase):
    def setUp(self):
        self.player = MidiPlayer()
        
    def test_note_adjustment(self):
        # 测试音符调整
        self.assertEqual(self.player._adjust_note(60), 60 + self.player.note_offset) 