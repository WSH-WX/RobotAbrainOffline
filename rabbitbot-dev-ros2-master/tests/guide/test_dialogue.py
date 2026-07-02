import json
import tempfile
import unittest
from pathlib import Path

from rabbitbot.guide.dialogue import (
    DEFAULT_DIALOGUE_INDEX,
    dialogue_index,
    dialogue_path,
    extract_location_points,
    format_guide_text,
    guide_leader_calling,
    guide_variables,
    load_dialogue,
    load_script_steps,
    normalize_point_entity,
    opening_text,
    point_entities,
)


def sample_dialogue():
    return {
        "variables": {"leader_calling": "各位领导"},
        "opening": {"hello": "{leader_calling}您好"},
        "steps": [
            {"scene": "点位2", "entity_key": "point_2", "segments": [{"text": "欢迎"}]},
        ],
        "map_file": "test9.pcd",
        "points": {
            "point_2": {
                "name": "点位2",
                "summary": "点位2",
                "description": "说明",
                "location": [
                    {"x": "1", "y": 2, "z": 0, "ox": 0.1, "oy": 0.2, "oz": 0.3, "ow": 0.4, "mode": "1"}
                ],
            }
        },
    }


class GuideDialogueTest(unittest.TestCase):
    def write_dialogue(self, directory: Path, name="dialogue_0.json", data=None):
        path = directory / name
        path.write_text(json.dumps(sample_dialogue() if data is None else data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_dialogue_index_defaults_and_validates(self):
        self.assertEqual(dialogue_index({}, DEFAULT_DIALOGUE_INDEX), "0")
        self.assertEqual(dialogue_index({"RABBITBOT_DIALOGUE_INDEX": "3"}), "3")
        self.assertEqual(dialogue_index({"RABBITBOT_DOCX_GUIDE_DIALOGUE_INDEX": "2"}), "2")
        with self.assertRaises(ValueError):
            dialogue_index({"RABBITBOT_DIALOGUE_INDEX": "bad"})

    def test_explicit_dialogue_file_has_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            explicit = tmp_path / "custom.json"
            env = {"RABBITBOT_DOCX_GUIDE_DIALOGUE_FILE": str(explicit), "RABBITBOT_DIALOGUE_INDEX": "3"}
            self.assertEqual(dialogue_path(tmp_path, env), explicit)

    def test_load_dialogue_validates_top_level_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.write_dialogue(tmp_path)
            data = load_dialogue(tmp_path, env={})
            self.assertEqual(data["map_file"], "test9.pcd")

            cases = [
                ([], "根节点"),
                ({**sample_dialogue(), "variables": []}, "variables"),
                ({**sample_dialogue(), "opening": []}, "opening"),
                ({**sample_dialogue(), "steps": {}}, "steps"),
                ({**sample_dialogue(), "map_file": 123}, "map_file"),
                ({**sample_dialogue(), "points": []}, "points"),
            ]
            for index, (bad_data, _label) in enumerate(cases, start=1):
                self.write_dialogue(tmp_path, f"dialogue_{index}.json", bad_data)
                with self.assertRaises(ValueError):
                    load_dialogue(tmp_path, env={"RABBITBOT_DIALOGUE_INDEX": str(index)})

    def test_missing_leader_calling_raises(self):
        data = sample_dialogue()
        data["variables"] = {}
        with self.assertRaises(KeyError):
            guide_variables(data, Path("dialogue.json"))

    def test_format_and_opening_text(self):
        data = sample_dialogue()
        path = Path("dialogue.json")
        self.assertEqual(guide_leader_calling(data, path), "各位领导")
        self.assertEqual(format_guide_text(data, path, "{leader_calling}好"), "各位领导好")
        self.assertEqual(opening_text(data, path, "hello"), "各位领导您好")

    def test_normalize_point_entity_validates_location(self):
        path = Path("dialogue.json")
        entity = normalize_point_entity("point_2", sample_dialogue()["points"]["point_2"], path)
        self.assertEqual(entity["location"][0]["x"], 1.0)
        self.assertEqual(entity["location"][0]["mode"], 1)

        bad = sample_dialogue()["points"]["point_2"]
        bad_missing = {**bad, "location": [{"x": 1}]}
        with self.assertRaises(ValueError):
            normalize_point_entity("point_2", bad_missing, path)

        bad_number = {**bad, "location": [{**bad["location"][0], "x": "bad"}]}
        with self.assertRaises(ValueError):
            normalize_point_entity("point_2", bad_number, path)

        bad_mode = {**bad, "location": [{**bad["location"][0], "mode": "bad"}]}
        with self.assertRaises(ValueError):
            normalize_point_entity("point_2", bad_mode, path)

    def test_point_entities_support_key_and_name_lookup(self):
        entities = point_entities(sample_dialogue(), Path("dialogue.json"))
        self.assertIn("point_2", entities)
        self.assertIn("点位2", entities)

    def test_load_script_steps_resolves_entity_key_and_copies_segments(self):
        data = sample_dialogue()
        entities = point_entities(data, Path("dialogue.json"))
        steps = load_script_steps(data, Path("dialogue.json"), {"point_2": "点位2"}, entity_resolver=entities.get)
        self.assertEqual(steps[0]["entity"], "点位2")
        self.assertNotIn("entity_key", steps[0])
        self.assertEqual(steps[0]["segments"], [{"text": "欢迎"}])

    def test_extract_location_points_accepts_dict_list_tuple_and_string(self):
        entity = point_entities(sample_dialogue(), Path("dialogue.json"))["点位2"]
        self.assertEqual(extract_location_points(entity), [(1.0, 2.0, 0.1, 0.2, 0.3, 0.4)])
        self.assertEqual(extract_location_points([1, 2, 0.1, 0.2, 0.3, 0.4]), [(1.0, 2.0, 0.1, 0.2, 0.3, 0.4)])
        self.assertEqual(extract_location_points("[(1, 2, 0.1, 0.2, 0.3, 0.4)]"), [(1.0, 2.0, 0.1, 0.2, 0.3, 0.4)])


if __name__ == "__main__":
    unittest.main()
