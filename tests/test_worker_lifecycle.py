from storage_health import StorageScan
import main
from PySide6.QtWidgets import QApplication
import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class WorkerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_close_stops_timer_and_drains_active_hardware_workers(self):
        def delayed_gpu_read():
            time.sleep(0.1)
            return object()

        def delayed_storage_scan():
            time.sleep(0.1)
            return StorageScan(available=True)

        with (
            patch.object(main, "read_hardware_sensors",
                         side_effect=delayed_gpu_read),
            patch.object(main, "scan_storage",
                         side_effect=delayed_storage_scan),
        ):
            window = main.PulseWindow()
            window._start_storage_scan()
            self.assertTrue(window._gpu_reading)
            self.assertTrue(window._storage_reading)
            window.close()

        self.assertFalse(window.timer.isActive())
        self.assertEqual(window._worker_pool.activeThreadCount(), 0)
        self.assertTrue(window._closing)

    def test_repeated_close_does_not_start_more_work(self):
        window = main.PulseWindow()
        window.close()
        self.assertFalse(window.timer.isActive())
        self.assertEqual(window._worker_pool.activeThreadCount(), 0)
        self.assertFalse(window._start_gpu_read())


if __name__ == "__main__":
    unittest.main()
