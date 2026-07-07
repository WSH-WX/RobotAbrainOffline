import unittest

from rabbitbot.guide.routing import (
    classify_task_by_rule,
    has_navigation_action,
    is_chat_info_request,
    is_next_board_request,
    is_visual_request,
    normalize_nav_text,
    resolve_navigation_entity_by_fuzzy,
)


class GuideRoutingTest(unittest.TestCase):
    def test_normalize_nav_text_keeps_existing_misrecognition_rules(self):
        self.assertEqual(normalize_nav_text("去复新合营资源原区"), "去复星合影智元园区")
        self.assertEqual(normalize_nav_text("骑士板块。"), "起始板块")
        self.assertEqual(normalize_nav_text("趣奇石"), "去起始")

    def test_visual_request_classifies_as_v(self):
        self.assertTrue(is_visual_request("你现在看到什么"))
        self.assertEqual(classify_task_by_rule("帮我看一下前面"), "V")

    def test_chat_info_request_classifies_as_c_without_navigation_action(self):
        self.assertTrue(is_chat_info_request("介绍一下复星集团板块"))
        self.assertEqual(classify_task_by_rule("了解一下园区布局"), "C")

    def test_navigation_action_takes_priority_over_chat_info(self):
        self.assertTrue(has_navigation_action("带我去复星集团板块介绍一下"))
        self.assertFalse(is_chat_info_request("带我去复星集团板块介绍一下"))
        self.assertEqual(classify_task_by_rule("带我去复星集团板块介绍一下"), "N")

    def test_next_board_request_matches_existing_phrases(self):
        self.assertTrue(is_next_board_request("去下一个板块"))
        self.assertTrue(is_next_board_request("下一站"))
        self.assertTrue(is_next_board_request("继续下一个"))
        self.assertFalse(is_next_board_request("介绍一下这个板块"))

    def test_resolve_navigation_entity_by_fuzzy_exact_and_replacement_match(self):
        entities = ["起始板块", "复星集团板块", "合影板块"]
        entity, score = resolve_navigation_entity_by_fuzzy("带我去福星集团", entities)
        self.assertEqual(entity, "复星集团板块")
        self.assertGreaterEqual(score, 0.85)
        self.assertEqual(resolve_navigation_entity_by_fuzzy("去骑士板块", entities), ("起始板块", 1.0))

    def test_resolve_navigation_entity_by_fuzzy_threshold_and_empty_cases(self):
        entity, score = resolve_navigation_entity_by_fuzzy("合影", ["合影板块"])
        self.assertEqual(entity, "合影板块")
        self.assertGreaterEqual(score, 0.85)

        entity, score = resolve_navigation_entity_by_fuzzy("咖啡", ["合影板块", "复星集团板块"])
        self.assertIsNone(entity)
        self.assertLess(score, 0.62)

        self.assertEqual(resolve_navigation_entity_by_fuzzy("", ["合影板块"]), (None, 0.0))
        self.assertEqual(resolve_navigation_entity_by_fuzzy("去合影", []), (None, 0.0))


if __name__ == "__main__":
    unittest.main()
