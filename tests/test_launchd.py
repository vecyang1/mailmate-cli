import plistlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mailmate_cli.launchd import build_launch_agent_plist, install_launch_agent


class LaunchdTests(unittest.TestCase):
    def test_build_launch_agent_plist_runs_quiet_mailmate_on_interval(self):
        plist = build_launch_agent_plist(
            label="com.vec.mailmate-cli.run",
            program="/opt/mailmate",
            interval_minutes=120,
            stdout_log="/tmp/mailmate.out.log",
            stderr_log="/tmp/mailmate.err.log",
        )

        self.assertEqual(plist["Label"], "com.vec.mailmate-cli.run")
        self.assertEqual(plist["ProgramArguments"], ["/opt/mailmate", "--quiet", "run"])
        self.assertEqual(plist["StartInterval"], 7200)
        self.assertFalse(plist["RunAtLoad"])
        self.assertEqual(plist["StandardOutPath"], "/tmp/mailmate.out.log")
        self.assertEqual(plist["StandardErrorPath"], "/tmp/mailmate.err.log")
        self.assertIn("/opt/homebrew/bin", plist["EnvironmentVariables"]["PATH"])
        self.assertIn("/usr/bin", plist["EnvironmentVariables"]["PATH"])

    def test_build_launch_agent_plist_can_include_run_confirmation(self):
        plist = build_launch_agent_plist(
            label="com.vec.mailmate-cli.run",
            program="/opt/mailmate",
            interval_minutes=120,
            stdout_log="/tmp/mailmate.out.log",
            stderr_log="/tmp/mailmate.err.log",
            run_yes=True,
        )

        self.assertEqual(plist["ProgramArguments"], ["/opt/mailmate", "--quiet", "run", "--yes"])

    def test_install_launch_agent_writes_valid_plist(self):
        with TemporaryDirectory() as tmp:
            plist_path = Path(tmp) / "com.vec.mailmate-cli.run.plist"
            plist = build_launch_agent_plist(
                label="com.vec.mailmate-cli.run",
                program="/opt/mailmate",
                interval_minutes=60,
                stdout_log="/tmp/mailmate.out.log",
                stderr_log="/tmp/mailmate.err.log",
            )

            result = install_launch_agent(plist_path, plist)
            parsed = plistlib.loads(plist_path.read_bytes())
            mode = oct(plist_path.stat().st_mode & 0o777)

        self.assertTrue(result["installed"])
        self.assertEqual(parsed["StartInterval"], 3600)
        self.assertEqual(mode, "0o644")


if __name__ == "__main__":
    unittest.main()
