import unittest

from rabbitbot.guide.controls import (
    build_control_commands,
    is_continue_text,
    matches_control_command,
    normalize_control_text,
)


class GuideControlsTest(unittest.TestCase):
    def test_normalize_control_text_handles_punctuation_and_case(self):
        self.assertEqual(normalize_control_text(" 开始，Guide!? "), "开始guide")

    def test_continue_text_matches_normalized_text(self):
        self.assertTrue(is_continue_text(" 好的。"))
        self.assertTrue(is_continue_text("接着讲！"))
        self.assertFalse(is_continue_text("介绍一下园区"))

    def test_command_matching_uses_contains_semantics(self):
        commands = build_control_commands("开始导览,启动导览", ["开始导览"])
        self.assertTrue(matches_control_command("我们现在开始导览吧", commands))
        self.assertFalse(matches_control_command("返回起点", commands))

    def test_empty_command_config_falls_back_to_default(self):
        self.assertEqual(build_control_commands("", ["返回起点"]), ["返回起点"])


if __name__ == "__main__":
    unittest.main()
