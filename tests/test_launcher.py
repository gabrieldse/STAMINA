from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import start


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("requirements.txt", "frontend/package.json", "frontend/package-lock.json",
                     "frontend/index.html", "frontend/src/App.tsx"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("initial", encoding="utf-8")
        self.python = self.root / ".venv/python"
        for target, value in (("ROOT", self.root), ("STATE", self.root / ".runtime/launcher.json"),
                              ("PYTHON", self.python)):
            patcher = patch.object(start, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for patcher in (patch.object(start.shutil, "which", return_value="executable"),
                        patch.object(start.subprocess, "check_output", return_value="v22.12.0"),
                        patch("scripts.manage.check_data", return_value=[])):
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_run(self, command, cwd=None):
        if "venv" in command:
            self.python.parent.mkdir(parents=True, exist_ok=True)
            self.python.touch()
        if "ci" in command:
            lock = self.root / "frontend/node_modules/.package-lock.json"
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text("{}", encoding="utf-8")
        if "build" in command:
            index = self.root / "frontend/dist/index.html"
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text("built", encoding="utf-8")

    def test_first_launch_sets_up_once_and_unchanged_launch_reuses_everything(self):
        with patch.object(start, "run", side_effect=self.fake_run) as run:
            start.setup()
            self.assertEqual(run.call_count, 4)
            run.reset_mock()
            start.setup()
            run.assert_not_called()

    def test_source_change_rebuilds_without_reinstalling_dependencies(self):
        with patch.object(start, "run", side_effect=self.fake_run) as run:
            start.setup()
            run.reset_mock()
            (self.root / "frontend/src/App.tsx").write_text("updated application", encoding="utf-8")
            start.setup()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-2:], ["run", "build"])

    def test_failed_build_is_retried_on_next_launch(self):
        with patch.object(start, "run", side_effect=self.fake_run):
            start.setup()
        (self.root / "frontend/src/App.tsx").write_text("new version", encoding="utf-8")
        old_state = start.STATE.read_text(encoding="utf-8")
        with patch.object(start, "run", side_effect=subprocess.CalledProcessError(1, "build")):
            with self.assertRaises(subprocess.CalledProcessError):
                start.setup()
        self.assertEqual(start.STATE.read_text(encoding="utf-8"), old_state)
        with patch.object(start, "run", side_effect=self.fake_run) as run:
            start.setup()
            self.assertEqual(run.call_count, 1)

    def test_missing_kernels_stop_before_data_download_or_build(self):
        with patch.object(start, "run", side_effect=self.fake_run) as run, \
             patch("scripts.manage.check_data", return_value=[self.root / "SMEData/Kernels/de440s.bsp"]):
            with self.assertRaisesRegex(RuntimeError, "SPICE kernels"):
                start.setup()
            self.assertFalse(any("prepare-data" in call.args[0] or "build" in call.args[0]
                                 for call in run.call_args_list))

    def test_missing_map_is_prepared_before_building(self):
        with patch.object(start, "run", side_effect=self.fake_run) as run, \
             patch("scripts.manage.check_data", side_effect=[
                 [self.root / "frontend/public/lunar-map/data/meta.json"], []]):
            start.setup()
            commands = [call.args[0] for call in run.call_args_list]
            preparation = next(i for i, command in enumerate(commands) if "prepare-data" in command)
            build = next(i for i, command in enumerate(commands) if "build" in command)
            self.assertLess(preparation, build)

    def test_occupied_port_is_skipped(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            occupied = listener.getsockname()[1]
            selected = start.available_port(occupied)
            self.assertGreater(selected, occupied)

    def test_server_exit_is_reported_without_opening_browser(self):
        with patch.object(start.subprocess, "Popen") as process:
            process.return_value.poll.return_value = 1
            with self.assertRaisesRegex(RuntimeError, "stopped during startup"):
                start.wait_until_ready(process.return_value, "http://127.0.0.1:8080/")


if __name__ == "__main__":
    unittest.main()
