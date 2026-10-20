import asyncio
import importlib.util
import tempfile
import unittest
from pathlib import Path

try:
    import telethon  # noqa: F401
    HAVE_TELETHON = True
except Exception:
    HAVE_TELETHON = False

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "update_poller.py"


def _load():
    spec = importlib.util.spec_from_file_location("update_poller", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeNet:
    def __init__(self):
        self.polled = []
        self.account_calls = 0
        self.flood = False


def _make_client(channel_ids, net, account_state=True, next_deadline="loaded"):
    from datetime import datetime, timezone
    from telethon import TelegramClient, errors
    from telethon.sessions import StringSession
    from telethon.tl import functions, types

    client = TelegramClient(StringSession(), 1, "0" * 32)
    client.is_connected = lambda: True
    client._catch_up = False
    now = datetime.now(timezone.utc)
    from telethon._updates import SessionState

    mb = client._message_box
    mb.load(SessionState(0, 0, False, 100 if account_state else 0, 0, int(now.timestamp()), 0, None), [])
    for cid in channel_ids:
        client._mb_entity_cache.extend(users=[], chats=[types.Channel(
            id=cid, title=f"c{cid}", photo=types.ChatPhotoEmpty(), date=now, access_hash=cid * 7)])
        mb.try_set_channel_state(cid, 50)
        mb.reset_channel_deadline(cid, None)
    if next_deadline is None:
        mb.next_deadline = None

    async def call(self_, request, *a, **k):
        if isinstance(request, functions.updates.GetDifferenceRequest):
            net.account_calls += 1
            return types.updates.DifferenceEmpty(date=request.date, seq=0)
        if isinstance(request, functions.updates.GetChannelDifferenceRequest):
            if net.flood:
                raise errors.FloodWaitError(request=request, capture=5)
            net.polled.append(request.channel.channel_id)
            return types.updates.ChannelDifferenceEmpty(final=True, pts=request.pts + 1, timeout=None)
        raise AssertionError(f"unexpected request {request}")

    type(client).__call__ = call
    return client, mb


@unittest.skipUnless(HAVE_TELETHON and MODULE_PATH.exists(), "telethon or module missing")
class UpdatePollerTest(unittest.TestCase):
    def setUp(self):
        self.up = _load()
        self.up.TICK_S = 0.05
        self.up.POLL_EVERY_S = 0.2
        from telethon import TelegramClient
        orig = TelegramClient.__call__
        self.addCleanup(lambda: setattr(TelegramClient, "__call__", orig))

    def _scenario(self, channels, seconds, flood=False, **client_kwargs):
        net = _FakeNet()
        net.flood = flood

        async def main():
            client, mb = _make_client(channels, net, **client_kwargs)
            loop = asyncio.get_running_loop()
            update_task = loop.create_task(client._update_loop())
            poll_task = loop.create_task(self.up.poller_loop(client))
            await asyncio.sleep(seconds)
            poll_task.cancel()
            update_task.cancel()
            await asyncio.gather(poll_task, update_task, return_exceptions=True)

        asyncio.run(main())
        return net

    def test_idle_rooms_are_polled_repeatedly_without_the_15_minute_timer(self):
        net = self._scenario([11, 12, 13], 1.5)
        self.assertEqual(set(net.polled), {11, 12, 13})
        self.assertGreaterEqual(len(net.polled), 6, "rooms must be re-polled, not polled once")

    def test_polls_even_when_account_entry_is_missing_like_a_fresh_string_session(self):
        net = self._scenario([51, 52], 1.5, account_state=False)
        self.assertEqual(set(net.polled), {51, 52})

    def test_polls_even_when_next_deadline_pointer_is_unset(self):
        net = self._scenario([61, 62], 1.5, next_deadline=None)
        self.assertEqual(set(net.polled), {61, 62})

    def test_rooms_with_fresh_activity_are_not_polled(self):
        self.up.POLL_EVERY_S = 3600.0
        net = self._scenario([21, 22], 0.6)
        self.assertEqual(net.polled, [])
        self.assertEqual(net.account_calls, 0)

    def test_batch_limit_and_oldest_first(self):
        net = _FakeNet()

        async def main():
            client, mb = _make_client([31, 32, 33, 34], net)
            now = asyncio.get_running_loop().time()
            for i, cid in enumerate([31, 32, 33, 34]):
                mb.map[cid].deadline = now + 900 - (50 + i * 10)
            return self.up.due_entries(mb, now, poll_every=40, limit=2)

        self.assertEqual(asyncio.run(main()), [34, 33])

    def test_floodwait_pauses_polling(self):
        net = self._scenario([41, 42], 1.5, flood=True)
        self.assertEqual(net.polled, [])
        self.assertGreaterEqual(net.account_calls, 1, "poller must have tried before the FloodWait")
        self.assertLessEqual(net.account_calls, 6, "must stop nudging soon after a FloodWait")

    def test_install_is_idempotent_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "utils.py"
            p.write_text("async def resolve_room(handle):\n    " + self.up.OLD_HOOK + "\n    return 1\n")
            self.assertEqual(self.up.install(p), "installed")
            ns = {}
            exec(compile(p.read_text(), "utils.py", "exec"), ns)
            self.assertIn("update_poller", p.read_text())
            self.assertTrue(Path(str(p) + ".bak_update_poller").exists())
            self.assertEqual(self.up.install(p), "already installed")

    def test_install_refuses_when_hook_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "utils.py"
            p.write_text("async def resolve_room(handle):\n    pass\n")
            self.assertIn("not found", self.up.install(p))
            self.assertEqual(p.read_text(), "async def resolve_room(handle):\n    pass\n")


if __name__ == "__main__":
    unittest.main()
