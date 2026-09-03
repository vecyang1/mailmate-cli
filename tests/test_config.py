import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mailmate_cli.config import ProfilePaths, RunConfig, load_run_config, resolve_profile_paths


class ConfigTests(unittest.TestCase):
    def test_missing_config_uses_safe_defaults(self):
        with TemporaryDirectory() as tmp:
            config = load_run_config(Path(tmp) / "missing.json")

        self.assertEqual(config, RunConfig())
        self.assertFalse(config.apply)

    def test_load_run_config_normalizes_sender_and_mail_ids(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "inboxId": 82433,
                        "limit": 5,
                        "senderContains": "全国健康保険協会",
                        "mailIds": [198843, "199671"],
                    }
                ),
                encoding="utf-8",
            )

            config = load_run_config(path)

        self.assertEqual(config.inbox_id, "82433")
        self.assertEqual(config.limit, 5)
        self.assertEqual(config.sender_contains, ["全国健康保険協会"])
        self.assertEqual(config.mail_ids, ["198843", "199671"])

    def test_apply_config_requires_explicit_paper_discard_confirmation(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"apply": True}), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                load_run_config(path)

        self.assertIn("confirmedPaperDiscard", str(ctx.exception))

    def test_resolve_profile_paths_default(self):
        with TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / ".config" / "mailmate-cli"
            state_dir = Path(tmp) / ".local" / "state" / "mailmate-cli"
            paths = resolve_profile_paths("default", base_config_dir=cfg_dir, base_state_dir=state_dir)
            self.assertEqual(paths.profile, "default")
            self.assertEqual(paths.config_file, cfg_dir / "config.json")
            self.assertEqual(paths.env_file, cfg_dir / "env")
            self.assertEqual(paths.cookie_jar, state_dir / "cookies.txt")
            self.assertEqual(paths.audit_log, state_dir / "audit.jsonl")
            self.assertEqual(paths.lock_file, state_dir / "run.lock")

    def test_resolve_profile_paths_custom_profile(self):
        with TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / ".config" / "mailmate-cli"
            state_dir = Path(tmp) / ".local" / "state" / "mailmate-cli"
            paths = resolve_profile_paths("profile2", base_config_dir=cfg_dir, base_state_dir=state_dir)
            self.assertEqual(paths.profile, "profile2")
            self.assertEqual(paths.config_file, cfg_dir / "profiles" / "profile2" / "config.json")
            self.assertEqual(paths.env_file, cfg_dir / "profiles" / "profile2" / "env")
            self.assertEqual(paths.cookie_jar, state_dir / "profiles" / "profile2" / "cookies.txt")
            self.assertEqual(paths.audit_log, state_dir / "profiles" / "profile2" / "audit.jsonl")
            self.assertEqual(paths.lock_file, state_dir / "profiles" / "profile2" / "run.lock")


if __name__ == "__main__":
    unittest.main()
