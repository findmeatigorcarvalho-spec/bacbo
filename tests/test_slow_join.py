import asyncio
import importlib.util
import unittest
from types import SimpleNamespace
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "slow_join.py"


def _load():
    spec = importlib.util.spec_from_file_location("slow_join", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SlowJoinHelpersTest(unittest.TestCase):
    def setUp(self):
        self.sj = _load()

    def test_dialog_usernames_normalised(self):
        dialogs = [
            SimpleNamespace(entity=SimpleNamespace(username="@RoomA")),
            SimpleNamespace(entity=SimpleNamespace(username="roomb")),
            SimpleNamespace(entity=SimpleNamespace(username=None)),
            SimpleNamespace(username="roomc"),
        ]
        self.assertEqual(self.sj._dialog_usernames(dialogs), {"rooma", "roomb", "roomc"})

    def test_mark_joined_moves_only_targets_not_done_or_skipped(self):
        st = {"done": ["rooma"], "skip": {"roomb": "dead"}, "defer": {"roomc": 1.0}}
        n = self.sj._mark_joined(["rooma", "roomb", "roomc", "roomd"], {"rooma", "roomb", "roomc"}, st)
        self.assertEqual(n, 1)
        self.assertEqual(st["done"], ["rooma", "roomc"])
        self.assertNotIn("roomc", st["defer"])

    def test_pick_pending_skips_deferred_head(self):
        now = 1000.0
        picked = self.sj._pick_pending(
            ["heada", "nextb", "thirdc"], done=[], skip={},
            defer={"heada": now + 7200}, now=now)
        self.assertEqual(picked, "nextb", "a deferred head must not block the queue")

    def test_pick_pending_none_when_all_deferred_or_finished(self):
        now = 1000.0
        self.assertIsNone(self.sj._pick_pending(
            ["a", "b"], done=["a"], skip={}, defer={"b": now + 10}, now=now))
        self.assertEqual(self.sj._pick_pending(
            ["a", "b"], done=["a"], skip={}, defer={"b": now - 10}, now=now), "b")

    def test_refresh_joined_uses_dialogs_and_marks_bulk(self):
        self.sj._joined_cache["at"] = 0.0
        self.sj._joined_cache["names"] = set()
        st = {"done": [], "skip": {}, "defer": {}}

        class FakeClient:
            async def get_dialogs(self):
                return [SimpleNamespace(entity=SimpleNamespace(username="RoomA")),
                        SimpleNamespace(entity=SimpleNamespace(username="roomb"))]

        n = asyncio.run(self.sj._refresh_joined(FakeClient(), ["rooma", "roomb", "roomc"], st))
        self.assertEqual(n, 2)
        self.assertEqual(sorted(st["done"]), ["rooma", "roomb"])

    def test_refresh_joined_falls_back_to_session_cache(self):
        self.sj._joined_cache["at"] = 0.0
        self.sj._joined_cache["names"] = set()
        st = {"done": [], "skip": {}, "defer": {}}

        class FakeClient:
            async def get_dialogs(self):
                raise RuntimeError("no network")

            session = SimpleNamespace(
                get_entity_rows_by_username=lambda h: [1] if h == "rooma" else [])

        n = asyncio.run(self.sj._refresh_joined(FakeClient(), ["rooma", "roomb"], st))
        self.assertEqual(n, 1)
        self.assertEqual(st["done"], ["rooma"])


if __name__ == "__main__":
    unittest.main()
