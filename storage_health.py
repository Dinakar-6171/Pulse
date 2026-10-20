"""Read-only smartctl discovery and JSON parsing for storage health."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WINDOWS_DEVICE_RE = re.compile(
    r"^" + re.escape(r"\\.\PhysicalDrive") + r"\d+$", re.IGNORECASE)
UNIX_DEVICE_RE = re.compile(
    r"^/dev/(?:sd[a-z]+|nvme\d+n\d+|vd[a-z]+|xvd[a-z]+)$")
ALLOWED_DEVICE_TYPES = {"ata", "sat", "scsi", "nvme",
                        "usbjmicron", "usbprolific", "usbsunplus"}
COMMAND_TIMEOUT_SECONDS = 8
SMARTCTL_PATH_ENV = "PULSE_SMARTCTL_PATH"


@dataclass(frozen=True)
class StorageDrive:
    """Sanitized drive facts from smartctl; serials are intentionally omitted."""

    device: str
    model: str
    interface: str
    capacity_bytes: int | None
    health_status: str
    health_interpretation: str
    temperature_c: int | None
    drive_type: str
    percentage_used: int | None = None
    available_spare_percent: int | None = None
    critical_warning: int | None = None
    power_on_hours: int | None = None
    host_writes: str | None = None
    attributes: tuple[tuple[str, str], ...] = ()
    message: str | None = None


@dataclass(frozen=True)
class StorageScan:
    available: bool
    drives: tuple[StorageDrive, ...] = ()
    message: str | None = None


def _valid_device(device: str) -> bool:
    return bool(WINDOWS_DEVICE_RE.fullmatch(device) or UNIX_DEVICE_RE.fullmatch(device))


def _number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result >= 0 else None


def _capacity_bytes(payload: dict[str, Any]) -> int | None:
    user_capacity = payload.get("user_capacity")
    if isinstance(user_capacity, dict):
        capacity = _number(user_capacity.get("bytes"))
        if capacity is not None:
            return capacity
    return _number(payload.get("capacity_bytes"))


def _health(payload: dict[str, Any]) -> tuple[str, str]:
    smart_status = payload.get("smart_status")
    if not isinstance(smart_status, dict) or not isinstance(smart_status.get("passed"), bool):
        return "Unavailable", "Pulse interpretation unavailable: SMART health status was not reported."
    if smart_status["passed"]:
        return "PASSED", "No failure indicated by the reported SMART overall-health check."
    return "FAILED", "Warning: the drive reports a failing SMART overall-health check. Back up important data and seek drive support."


def _temperature(payload: dict[str, Any]) -> int | None:
    temperature = payload.get("temperature")
    if not isinstance(temperature, dict):
        return None
    return _number(temperature.get("current"))


def _media_type(payload: dict[str, Any], protocol: str, device_type: str) -> str:
    protocol_name = str(protocol or device_type).lower()
    if protocol_name == "nvme":
        return "NVMe SSD"
    if protocol_name in {"ata", "sat"}:
        rotation_rate = payload.get("rotation_rate")
        if isinstance(rotation_rate, str) and "solid state" in rotation_rate.lower():
            return "SATA SSD"
        rpm = _number(rotation_rate)
        if rpm:
            return f"SATA HDD ({rpm} RPM)"
        return "SATA (media type unavailable)"
    return "Storage drive"


def _nvme_fields(payload: dict[str, Any]) -> dict[str, Any]:
    nvme = payload.get("nvme_smart_health_information_log")
    if not isinstance(nvme, dict):
        nvme = {}
    data_units = _number(nvme.get("data_units_written"))
    return {
        "percentage_used": _number(nvme.get("percentage_used")),
        "available_spare_percent": _number(nvme.get("available_spare")),
        "critical_warning": _number(nvme.get("critical_warning")),
        "power_on_hours": _number(nvme.get("power_on_hours")),
        "host_writes": (
            f"{data_units * 512_000 / 1_000_000_000:.2f} GB "
            "(NVMe data units)" if data_units is not None else None
        ),
    }


def parse_smartctl_json(device: str, device_type: str, output: str) -> StorageDrive:
    """Parse one smartctl JSON document, excluding unnecessary drive identifiers."""
    if not _valid_device(device):
        raise ValueError("Unrecognized storage device identifier")
    if device_type and device_type not in ALLOWED_DEVICE_TYPES:
        raise ValueError("Unsupported smartctl device type")

    payload = json.loads(output)
    if not isinstance(payload, dict):
        raise ValueError("smartctl JSON root must be an object")

    model = payload.get("model_name") or payload.get("model_family")
    if not isinstance(model, str) or not model.strip():
        model = "Model unavailable"
    device_info = payload.get("device")
    protocol = device_info.get("protocol") if isinstance(
        device_info, dict) else None
    interface = str(protocol or device_type or "Interface unavailable").upper()
    is_nvme = str(protocol or device_type).lower() == "nvme"
    health_status, health_interpretation = _health(payload)
    common = {
        "device": device,
        "model": model.strip(),
        "interface": interface,
        "capacity_bytes": _capacity_bytes(payload),
        "health_status": health_status,
        "health_interpretation": health_interpretation,
        "temperature_c": _temperature(payload),
        "drive_type": _media_type(payload, str(protocol or ""), device_type),
    }
    if is_nvme:
        common.update(_nvme_fields(payload))
    return StorageDrive(**common)


def _scan_entries(output: str) -> list[tuple[str, str]]:
    payload = json.loads(output)
    if not isinstance(payload, dict) or not isinstance(payload.get("devices"), list):
        raise ValueError("smartctl scan JSON does not contain a devices list")
    entries = []
    for item in payload["devices"]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        device_type = item.get("type", "")
        if not isinstance(name, str) or not _valid_device(name):
            continue
        if device_type and device_type not in ALLOWED_DEVICE_TYPES:
            continue
        entries.append((name, device_type))
    return entries


def _permission_message(returncode: int, output: str) -> bool:
    text = output.lower()
    return any(
        phrase in text for phrase in (
            "permission denied", "access denied", "administrator privileges",
            "access is denied", "requires administrator", "run as administrator",
            "not permitted", "operation not permitted", "insufficient privileges",
        )
    )


def _read_one(smartctl: str, device: str, device_type: str) -> StorageDrive:
    if not _valid_device(device):
        raise ValueError("Unrecognized storage device identifier")
    args = [smartctl, "-a", "-j"]
    if device_type:
        if device_type not in ALLOWED_DEVICE_TYPES:
            raise ValueError("Unsupported smartctl device type")
        args.extend(("-d", device_type))
    args.append(device)
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout or ""
    if not output.strip():
        detail = completed.stderr.strip()
        if _permission_message(completed.returncode, detail):
            return _unavailable_drive(device, device_type, "Permission required")
        return _unavailable_drive(device, device_type, "SMART data unavailable")
    try:
        drive = parse_smartctl_json(device, device_type, output)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _unavailable_drive(device, device_type, "Malformed or unsupported smartctl output")

    if _permission_message(completed.returncode, completed.stderr):
        return StorageDrive(**{**drive.__dict__, "message": "Permission required for complete SMART data"})
    if completed.returncode & 4 and drive.health_status == "Unavailable":
        return StorageDrive(**{**drive.__dict__, "message": "Drive access unavailable; check controller support and permissions"})
    return drive


def _unavailable_drive(device: str, device_type: str, message: str) -> StorageDrive:
    return StorageDrive(
        device=device,
        model="Model unavailable",
        interface=(device_type or "Interface unavailable").upper(),
        capacity_bytes=None,
        health_status="Unavailable",
        health_interpretation="Pulse interpretation unavailable without SMART data.",
        temperature_c=None,
        drive_type="Storage drive",
        message=message,
    )


def find_smartctl(smartctl_path: str | None = None) -> str | None:
    """Find smartctl using explicit config, PATH, and common Windows locations."""
    configured = smartctl_path or os.environ.get(SMARTCTL_PATH_ENV)
    if configured:
        path = Path(configured).expanduser()
        return str(path) if path.is_file() else None

    executable = shutil.which("smartctl") or shutil.which("smartctl.exe")
    if executable:
        return executable

    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        roots = (Path(program_files), Path(os.environ.get(
            "ProgramFiles(x86)", r"C:\Program Files (x86)")))
        for root in roots:
            candidate = root / "smartmontools" / "bin" / "smartctl.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def scan_storage(smartctl_path: str | None = None) -> StorageScan:
    """Discover physical drives and read SMART data; all subprocesses are bounded."""
    executable = find_smartctl(smartctl_path)
    if not executable:
        return StorageScan(
            available=False,
            message=(
                f"smartctl was not found. Install smartmontools from "
                "https://www.smartmontools.org/wiki/Download, add its bin folder "
                f"to PATH, or set {SMARTCTL_PATH_ENV} to the full smartctl.exe path."
            ),
        )
    try:
        scan = subprocess.run(
            [executable, "--scan", "-j"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return StorageScan(available=True, message="Drive discovery timed out.")
    except OSError:
        return StorageScan(available=False, message="smartctl could not be started.")

    try:
        devices = _scan_entries(scan.stdout or "")
    except (json.JSONDecodeError, TypeError, ValueError):
        detail = scan.stderr.strip()
        if _permission_message(scan.returncode, detail):
            return StorageScan(available=True, message="Permission required to discover drives.")
        return StorageScan(available=True, message="smartctl returned malformed discovery data.")

    if not devices:
        if _permission_message(scan.returncode, scan.stderr):
            return StorageScan(
                available=True,
                message="Permission required to discover physical drives.",
            )
        return StorageScan(
            available=True,
            message="No compatible physical drives were discovered. Controller or RAID support may be limited.",
        )

    drives = []
    for device, device_type in devices:
        try:
            drives.append(_read_one(executable, device, device_type))
        except subprocess.TimeoutExpired:
            drives.append(_unavailable_drive(
                device, device_type, "SMART query timed out"))
        except OSError:
            drives.append(_unavailable_drive(device, device_type,
                          "smartctl could not read this drive"))
        except (TypeError, ValueError):
            drives.append(_unavailable_drive(
                device, device_type, "SMART query failed"))
    return StorageScan(available=True, drives=tuple(drives))
