"""Offline owner-gated Netlify release safety: never leave live auto-publishing unlocked."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import one_shot_locked_netlify_deploy as release


class MockNetlify:
    def __init__(self, fails=False):
        self.prev = "a" * 24
        self.new = "b" * 24
        self.current = self.prev
        self.locks = {self.prev: True, self.new: False}
        self.events = []
        self.fail = fails

    def request(self, token, path, method="GET"):
        assert token == "secret"
        self.events.append((method, path))
        if path == "/sites/" + release.SITE:
            return {"published_deploy": {"id": self.current}}
        if path.startswith("/deploys/"):
            did = path.split("/")[2]
            if path.endswith("/unlock"):
                assert did == self.current and method == "POST"
                self.locks[did] = False
                return {"id": did}
            if path.endswith("/lock"):
                assert method == "POST"
                self.current = did
                self.locks[did] = True
                return {"id": did}
            return {"id": did, "site_id": release.SITE,
                    "state": "ready", "locked": self.locks[did]}
        raise AssertionError("Unexpected Netlify API path")

    def cli(self, args, **kw):
        assert self.locks[self.prev] is False
        assert args[0:4] == ["npx", "-y", "netlify-cli@latest", "deploy"]
        if self.fail:
            return SimpleNamespace(returncode=1, stdout="", stderr="masked")
        self.current = self.new
        return SimpleNamespace(returncode=0,
                               stdout=json.dumps({"deploy_id": self.new}),
                               stderr="")


class SafeReleaseTests(unittest.TestCase):
    def test_success_relocks_exact_new_deploy(self):
        mock = MockNetlify()
        with tempfile.TemporaryDirectory() as d, patch.object(release, "request", mock.request):
            out = Path(d) / "netlify-production-deploy.json"
            self.assertEqual(release.release(mock.cli, "secret", out), mock.new)
            self.assertTrue(mock.locks[mock.new])
            self.assertEqual(mock.current, mock.new)
            self.assertEqual(json.loads(out.read_text())["deploy_id"], mock.new)
            self.assertEqual(sum(m == "POST" and p.endswith("/unlock")
                                 for m, p in mock.events), 1)

    def test_failed_cli_restores_old_lock_and_no_receipt(self):
        mock = MockNetlify(fails=True)
        with tempfile.TemporaryDirectory() as d, patch.object(release, "request", mock.request):
            out = Path(d) / "netlify-production-deploy.json"
            with self.assertRaisesRegex(RuntimeError, "NETLIFY_CLI_DEPLOY_FAILED"):
                release.release(mock.cli, "secret", out)
            self.assertTrue(mock.locks[mock.prev])
            self.assertEqual(mock.current, mock.prev)
            self.assertFalse(out.exists())

    def test_no_unlock_if_live_deploy_not_locked(self):
        mock = MockNetlify()
        mock.locks[mock.prev] = False
        with tempfile.TemporaryDirectory() as d, patch.object(release, "request", mock.request):
            with self.assertRaisesRegex(RuntimeError, "PREVIOUS_DEPLOY_NOT_LOCKED"):
                release.release(mock.cli, "secret", Path(d) / "out.json")
            self.assertFalse(any(p.endswith("/unlock") for _, p in mock.events))


if __name__ == "__main__":
    unittest.main()
