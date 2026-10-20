import json
import subprocess
import unittest
from unittest.mock import patch

import storage_health
from storage_health import find_smartctl, parse_smartctl_json, scan_storage
from widgets import StorageDriveCard


NVME_FIXTURE = {
    "model_name": "Example NVMe Model",
    "serial_number": "DO-NOT-EXPOSE",
    "device": {"protocol": "NVMe"},
    "user_capacity": {"bytes": 1000204886016},
    "smart_status": {"passed": True},
    "temperature": {"current": 39},
    "nvme_smart_health_information_log": {
        "percentage_used": 4,
        "available_spare": 100,
        "critical_warning": 0,
        "power_on_hours": 812,
        "data_units_written": 123456,
    },
}

SATA_FIXTURE = {
    "model_name": "Example SATA Drive",
    "serial_number": "DO-NOT-EXPOSE",
    "device": {"protocol": "ATA"},
    "rotation_rate": 7200,
    "user_capacity": {"bytes": 500107862016},
    "smart_status": {"passed": False},
    "temperature": {"current": 42},
    "ata_smart_attributes": {
        "table": [
            {"id": 5, "raw": {"value": 0, "string": "0"}},
            {"id": 9, "raw": {"value": 812}},
            {"id": 194, "raw": {"value": 42}},
            {"id": 241, "raw": {"value": 999}},
        ]
    },
}


class ParseSmartctlTests(unittest.TestCase):
    def test_nvme_fields_are_parsed_and_serial_is_not_exposed(self):
        drive = parse_smartctl_json(
            r"\\.\PhysicalDrive0", "nvme", json.dumps(NVME_FIXTURE))
        self.assertEqual(drive.model, "Example NVMe Model")
        self.assertEqual(drive.interface, "NVME")
        self.assertEqual(drive.capacity_bytes, 1000204886016)
        self.assertEqual(drive.health_status, "PASSED")
        self.assertEqual(drive.temperature_c, 39)
        self.assertEqual(drive.percentage_used, 4)
        self.assertEqual(drive.available_spare_percent, 100)
        self.assertEqual(drive.critical_warning, 0)
        self.assertEqual(drive.power_on_hours, 812)
        self.assertIn("63.21 GB", drive.host_writes)
        self.assertNotIn("DO-NOT-EXPOSE", repr(drive))

    def test_sata_omits_vendor_specific_raw_attributes(self):
        drive = parse_smartctl_json(
            r"\\.\PhysicalDrive1", "sat", json.dumps(SATA_FIXTURE))
        self.assertEqual(drive.drive_type, "SATA HDD (7200 RPM)")
        self.assertEqual(drive.health_status, "FAILED")
        self.assertEqual(drive.attributes, ())
        self.assertIn("failing SMART", drive.health_interpretation)

    def test_missing_and_malformed_optional_fields_stay_unavailable(self):
        minimal = {"device": {"protocol": "NVMe"}, "smart_status": {}}
        drive = parse_smartctl_json(
            "/dev/nvme0n1", "nvme", json.dumps(minimal))
        self.assertIsNone(drive.capacity_bytes)
        self.assertIsNone(drive.temperature_c)
        self.assertIsNone(drive.percentage_used)
        self.assertEqual(drive.health_status, "Unavailable")
        self.assertIsNone(drive.host_writes)

    def test_invalid_device_argument_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_smartctl_json("--scan", "nvme", json.dumps(NVME_FIXTURE))

    def test_invalid_device_type_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_smartctl_json("/dev/nvme0n1", "unsafe",
                                json.dumps(NVME_FIXTURE))

    def test_malformed_json_raises_parser_error(self):
        with self.assertRaises(json.JSONDecodeError):
            parse_smartctl_json("/dev/nvme0n1", "nvme", "{")


class ScanSmartctlTests(unittest.TestCase):
    def setUp(self):
        executable_exists = patch(
            "storage_health.Path.is_file", return_value=True)
        executable_exists.start()
        self.addCleanup(executable_exists.stop)

    def test_missing_smartctl_returns_install_guidance(self):
        with (
            patch.dict("storage_health.os.environ", {
                       "PULSE_SMARTCTL_PATH": ""}, clear=False),
            patch("storage_health.shutil.which", return_value=None),
            patch("storage_health.Path.is_file", return_value=False),
        ):
            result = scan_storage()
        self.assertFalse(result.available)
        self.assertIn("smartmontools.org", result.message)
        self.assertIn("PULSE_SMARTCTL_PATH", result.message)

    def test_configured_smartctl_path_is_used(self):
        with patch("storage_health.Path.is_file", return_value=True):
            self.assertEqual(find_smartctl(r"D:\Tools\smartctl.exe"),
                             r"D:\Tools\smartctl.exe")

    def test_environment_path_can_configure_smartctl(self):
        with (
            patch.dict("storage_health.os.environ", {
                "PULSE_SMARTCTL_PATH": r"E:\Apps\smartctl.exe"}),
            patch("storage_health.Path.is_file", return_value=True),
        ):
            self.assertEqual(
                find_smartctl(), r"E:\Apps\smartctl.exe")

    def test_smartctl_is_found_on_path(self):
        with patch("storage_health.shutil.which", side_effect=[None, r"D:\smartctl.exe"]):
            self.assertEqual(find_smartctl(), r"D:\smartctl.exe")

    def test_common_windows_install_path_is_checked(self):
        with (
            patch.dict("storage_health.os.environ", {
                "PULSE_SMARTCTL_PATH": "",
                "ProgramFiles": r"C:\Program Files",
                "ProgramFiles(x86)": r"C:\Program Files (x86)",
            }, clear=False),
            patch("storage_health.shutil.which", return_value=None),
            patch("storage_health.os.name", "nt"),
            patch(
                "storage_health.Path.is_file",
                new=lambda path: str(path).endswith(
                    r"Program Files\smartmontools\bin\smartctl.exe"),
            ),
        ):
            self.assertEqual(
                find_smartctl(),
                str(storage_health.Path(r"C:\Program Files") /
                    "smartmontools" / "bin" / "smartctl.exe"),
            )

    def test_nvme_card_displays_nvme_health_fields_for_nvme_ssd_label(self):
        from PySide6.QtWidgets import QApplication, QLabel

        app = QApplication.instance() or QApplication([])
        drive = parse_smartctl_json(
            r"\\.\PhysicalDrive0", "nvme", json.dumps(NVME_FIXTURE))
        card = StorageDriveCard(drive, 1)
        labels = [label.text() for label in card.findChildren(QLabel)]
        self.assertEqual(drive.drive_type, "NVMe SSD")
        self.assertTrue(any("Percentage used: 4%" in text for text in labels))
        self.assertTrue(
            any("Available spare: 100%" in text for text in labels))
        self.assertTrue(any("Critical warnings: 0" in text for text in labels))
        self.assertTrue(any("Power-on hours: 812" in text for text in labels))
        self.assertTrue(any("Total host writes:" in text for text in labels))
        card.deleteLater()
        app.processEvents()

    def test_scan_command_uses_no_shell_and_parses_multiple_devices(self):
        scan_output = json.dumps({"devices": [
            {"name": r"\\.\PhysicalDrive0", "type": "nvme"},
            {"name": r"\\.\PhysicalDrive1", "type": "sat"},
            {"name": "--dangerous", "type": "nvme"},
        ]})
        drive_output = json.dumps(NVME_FIXTURE)
        calls = [
            subprocess.CompletedProcess([], 0, scan_output, ""),
            subprocess.CompletedProcess([], 0, drive_output, ""),
            subprocess.CompletedProcess([], 0, json.dumps(SATA_FIXTURE), ""),
        ]
        with patch("storage_health.subprocess.run", side_effect=calls) as run:
            result = scan_storage("C:/tools/smartctl.exe")
        self.assertEqual(len(result.drives), 2)
        self.assertFalse(run.call_args_list[0].kwargs["shell"])
        self.assertEqual(
            run.call_args_list[0].kwargs["timeout"], storage_health.COMMAND_TIMEOUT_SECONDS)
        self.assertNotIn("DO-NOT-EXPOSE", repr(result))

    def test_permission_error_is_labeled(self):
        scan_output = json.dumps({"devices": [
            {"name": r"\\.\PhysicalDrive0", "type": "nvme"}
        ]})
        calls = [
            subprocess.CompletedProcess([], 0, scan_output, ""),
            subprocess.CompletedProcess([], 4, "", "Permission denied"),
        ]
        with patch("storage_health.subprocess.run", side_effect=calls):
            result = scan_storage("smartctl.exe")
        self.assertEqual(result.drives[0].message, "Permission required")

    def test_nonzero_smart_health_exit_preserves_json_failure_status(self):
        completed = subprocess.CompletedProcess(
            [], 8, json.dumps(SATA_FIXTURE), "")
        with patch("storage_health.subprocess.run", return_value=completed):
            drive = storage_health._read_one(
                "smartctl.exe", r"\\.\PhysicalDrive1", "sat")
        self.assertEqual(drive.health_status, "FAILED")
        self.assertIn("failing SMART", drive.health_interpretation)

    def test_permission_error_during_empty_discovery_is_labeled(self):
        with patch("storage_health.subprocess.run", return_value=subprocess.CompletedProcess([], 1, json.dumps({"devices": []}), "Access is denied")):
            result = scan_storage("smartctl.exe")
        self.assertIn("Permission required", result.message)

    def test_command_failure_and_timeout_are_reported_without_raising(self):
        scan_output = json.dumps({"devices": [
            {"name": r"\\.\PhysicalDrive0", "type": "nvme"}
        ]})
        with patch("storage_health.subprocess.run", side_effect=[
            subprocess.CompletedProcess([], 0, scan_output, ""),
            subprocess.TimeoutExpired("smartctl", 8),
        ]):
            result = scan_storage("smartctl.exe")
        self.assertEqual(result.drives[0].message, "SMART query timed out")

    def test_malformed_discovery_json_is_handled(self):
        with patch("storage_health.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "not json", "")):
            result = scan_storage("smartctl.exe")
        self.assertIn("malformed", result.message)

    def test_malformed_drive_json_becomes_unavailable_drive(self):
        scan_output = json.dumps({"devices": [
            {"name": r"\\.\PhysicalDrive0", "type": "nvme"}
        ]})
        calls = [
            subprocess.CompletedProcess([], 0, scan_output, ""),
            subprocess.CompletedProcess([], 2, "{malformed", ""),
        ]
        with patch("storage_health.subprocess.run", side_effect=calls):
            result = scan_storage("smartctl.exe")
        self.assertEqual(len(result.drives), 1)
        self.assertEqual(result.drives[0].health_status, "Unavailable")
        self.assertIn("Malformed", result.drives[0].message)


if __name__ == "__main__":
    unittest.main()
