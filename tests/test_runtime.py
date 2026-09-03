import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mailmate_cli.runtime import FileLock, append_audit_log, build_status_report, scaffold_local_setup


class RuntimeTests(unittest.TestCase):
    def test_append_audit_log_writes_jsonl_with_private_permissions(self):
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "state" / "audit.jsonl"

            append_audit_log(log_path, {"command": "run", "rows": [{"mailId": "198843"}]})

            self.assertEqual(oct(log_path.stat().st_mode & 0o777), "0o600")
            records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(records[0]["command"], "run")
        self.assertEqual(records[0]["rows"][0]["mailId"], "198843")
        self.assertIn("timestamp", records[0])

    def test_file_lock_blocks_second_runner_and_releases(self):
        with TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "run.lock"
            first = FileLock(lock_path)
            second = FileLock(lock_path)

            with first:
                with self.assertRaises(RuntimeError):
                    with second:
                        pass
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())

    def test_build_status_report_summarizes_latest_audit_record(self):
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            append_audit_log(log_path, {"command": "run", "rows": [{"decision": "dry_run"}, {"decision": "skipped"}]})
            append_audit_log(log_path, {"command": "run", "rows": [{"decision": "discarded"}]})

            report = build_status_report(log_path)

        self.assertTrue(report["ok"])
        self.assertEqual(report["runs"], 2)
        self.assertEqual(report["latest"]["counts"]["discarded"], 1)
        self.assertEqual(report["latest"]["counts"]["dry_run"], 0)

    def test_build_status_report_handles_missing_audit_log(self):
        with TemporaryDirectory() as tmp:
            report = build_status_report(Path(tmp) / "missing.jsonl")

        self.assertFalse(report["ok"])
        self.assertEqual(report["runs"], 0)
        self.assertEqual(report["latest"], None)

    def test_scaffold_local_setup_writes_config_and_env_sample_without_credentials(self):
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            env_sample_path = Path(tmp) / "env.sample"
            state_dir = Path(tmp) / "state"

            result = scaffold_local_setup(config_path, env_sample_path, state_dir)

            config = json.loads(config_path.read_text(encoding="utf-8"))
            env_sample = env_sample_path.read_text(encoding="utf-8")
            config_mode = oct(config_path.stat().st_mode & 0o777)
            env_sample_mode = oct(env_sample_path.stat().st_mode & 0o777)

        self.assertTrue(result["createdConfig"])
        self.assertTrue(result["createdEnvSample"])
        self.assertEqual(config["inboxId"], "82433")
        self.assertFalse(config["apply"])
        self.assertIn("MAILMATE_EMAIL=", env_sample)
        self.assertIn("MAILMATE_PASSWORD=", env_sample)
        self.assertNotIn("dummy-password", env_sample)
        self.assertEqual(config_mode, "0o600")
        self.assertEqual(env_sample_mode, "0o600")


if __name__ == "__main__":
    unittest.main()
