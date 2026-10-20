"""
Pulse metric helpers.

This file talks to the operating system through psutil.
It never guesses or invents numbers. If a reading fails,
it returns an error message instead of a fake value.
"""

from __future__ import annotations

import os
import json
import subprocess
from dataclasses import dataclass

import psutil

try:
    import pynvml
except ImportError:
    pynvml = None


# 1 gigabyte in bytes (1024 * 1024 * 1024). RAM is usually shown this way.
BYTES_PER_GB = 1024 ** 3


@dataclass
class MetricResult:
    """One measurement, or a clear reason it could not be read."""

    ok: bool
    error: str | None = None
    # Optional fields. Only the ones that apply to this metric are filled in.
    percent: float | None = None
    used_gb: float | None = None
    total_gb: float | None = None
    available_gb: float | None = None
    physical_cores: int | None = None
    logical_processors: int | None = None
    drive: str | None = None


@dataclass
class GPUResult:
    """Live GPU metrics, with unsupported or unreadable sensors kept explicit."""

    available: bool
    name: str = "Unavailable"
    utilization_percent: float | None = None
    memory_used_gb: float | None = None
    memory_total_gb: float | None = None
    memory_percent: float | None = None
    temperature_c: int | None = None
    temperature_status: str = "Unavailable"
    power_w: float | None = None
    power_status: str = "Unavailable"
    fan_percent: int | None = None
    fan_status: str = "Unavailable"
    fan_rpm: int | None = None
    fan_rpm_status: str = "Unavailable"
    thermal_throttling: str = "Unavailable"
    error: str | None = None


@dataclass
class HardwareSensorResult:
    """Component identity and sensor readings from one hardware poll."""

    cpu_name: str | None
    cpu_temperature_c: float | None
    cpu_temperature_status: str
    ram_description: str | None
    gpu: GPUResult


def bytes_to_gb(num_bytes: int) -> float:
    """Convert a byte count into gigabytes."""
    return num_bytes / BYTES_PER_GB


def prime_cpu_counter() -> None:
    """
    Teach psutil to start comparing CPU samples.

    cpu_percent(interval=None) is non-blocking. The first call after
    startup has nothing to compare against, so it is not a useful reading.
    We call it once at launch, then use later calls on the 1-second timer.
    """
    try:
        psutil.cpu_percent(interval=None)
    except Exception:
        # The next live read will report the real error to the UI.
        pass


def read_cpu() -> MetricResult:
    """Read live CPU usage and core counts. Does not wait/sleep."""
    try:
        # interval=None is important: it does not freeze the window.
        # Using interval=1 would pause the whole UI for one second.
        percent = psutil.cpu_percent(interval=None)
        physical = psutil.cpu_count(logical=False)
        logical = psutil.cpu_count(logical=True)

        if percent is None:
            return MetricResult(ok=False, error="CPU usage is unavailable.")
        if physical is None:
            return MetricResult(ok=False, error="Physical core count is unavailable.")
        if logical is None:
            return MetricResult(ok=False, error="Logical processor count is unavailable.")

        return MetricResult(
            ok=True,
            percent=float(percent),
            physical_cores=int(physical),
            logical_processors=int(logical),
        )
    except Exception as exc:
        return MetricResult(ok=False, error=f"Could not read CPU: {exc}")


def read_ram() -> MetricResult:
    """Read used RAM, total RAM, and percent used."""
    try:
        memory = psutil.virtual_memory()
        return MetricResult(
            ok=True,
            percent=float(memory.percent),
            used_gb=bytes_to_gb(memory.used),
            total_gb=bytes_to_gb(memory.total),
            available_gb=bytes_to_gb(memory.available),
        )
    except Exception as exc:
        return MetricResult(ok=False, error=f"Could not read RAM: {exc}")


def windows_system_drive() -> str:
    """
    Return the Windows system drive path, such as 'C:\\'.

    SystemDrive is a normal Windows environment variable (usually C:).
    """
    drive = os.environ.get("SystemDrive")
    if not drive:
        raise RuntimeError(
            "Windows SystemDrive environment variable is missing.")
    # disk_usage needs a path like C:\ rather than just C:
    if not drive.endswith("\\"):
        drive = drive + "\\"
    return drive


def read_disk() -> MetricResult:
    """Read used space, total space, and percent used for the system drive."""
    try:
        drive = windows_system_drive()
        usage = psutil.disk_usage(drive)
        return MetricResult(
            ok=True,
            drive=drive,
            percent=float(usage.percent),
            used_gb=bytes_to_gb(usage.used),
            total_gb=bytes_to_gb(usage.total),
        )
    except Exception as exc:
        return MetricResult(ok=False, error=f"Could not read disk: {exc}")


def read_gpu() -> GPUResult:
    """Read GPU 0 through NVML. Sensor failures are reported independently."""
    if pynvml is None:
        return GPUResult(available=False, error="nvidia-ml-py is not installed.")

    initialized = False
    try:
        pynvml.nvmlInit()
        initialized = True
        if pynvml.nvmlDeviceGetCount() < 1:
            return GPUResult(available=False, error="No NVIDIA GPU was detected.")

        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        raw_name = pynvml.nvmlDeviceGetName(handle)
        name = raw_name.decode(
            "utf-8", errors="replace") if isinstance(raw_name, bytes) else str(raw_name)

        utilization = None
        memory_used = None
        memory_total = None
        memory_percent = None
        try:
            utilization = float(
                pynvml.nvmlDeviceGetUtilizationRates(handle).gpu)
        except Exception:
            pass

        try:
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_used = bytes_to_gb(memory.used)
            memory_total = bytes_to_gb(memory.total)
            if memory.total > 0:
                memory_percent = memory.used / memory.total * 100
        except Exception:
            pass

        temperature = None
        temperature_status = "Unavailable"
        try:
            temperature = int(
                pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU)
            )
            temperature_status = ""
        except getattr(pynvml, "NVMLError_NotSupported", Exception):
            temperature_status = "Not supported"
        except Exception:
            pass

        power = None
        power_status = "Unavailable"
        try:
            power = float(pynvml.nvmlDeviceGetPowerUsage(handle)) / 1000
            power_status = ""
        except getattr(pynvml, "NVMLError_NotSupported", Exception):
            power_status = "Not supported"
        except Exception:
            pass

        fan = None
        fan_status = "Unavailable"
        try:
            fan = int(pynvml.nvmlDeviceGetFanSpeed(handle))
            fan_status = ""
        except getattr(pynvml, "NVMLError_NotSupported", Exception):
            fan_status = "Not supported"
        except Exception:
            pass

        fan_rpm = None
        fan_rpm_status = "Unavailable"
        try:
            fan_rpm = int(pynvml.nvmlDeviceGetFanSpeedRPM(handle))
            fan_rpm_status = ""
        except getattr(pynvml, "NVMLError_NotSupported", Exception):
            fan_rpm_status = "Not supported"
        except Exception:
            pass

        thermal_throttling = "Unavailable"
        try:
            thermal_reasons = (
                pynvml.nvmlClocksThrottleReasonHwThermalSlowdown
                | pynvml.nvmlClocksThrottleReasonSwThermalSlowdown
            )
            supported_reasons = pynvml.nvmlDeviceGetSupportedClocksThrottleReasons(
                handle
            )
            if not supported_reasons & thermal_reasons:
                thermal_throttling = "Not supported"
            else:
                current_reasons = pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(
                    handle
                )
                active_reasons = current_reasons & thermal_reasons
                if active_reasons & pynvml.nvmlClocksThrottleReasonHwThermalSlowdown:
                    thermal_throttling = "Active (hardware thermal)"
                elif active_reasons & pynvml.nvmlClocksThrottleReasonSwThermalSlowdown:
                    thermal_throttling = "Active (software thermal)"
                else:
                    thermal_throttling = "Not active"
        except getattr(pynvml, "NVMLError_NotSupported", Exception):
            thermal_throttling = "Not supported"
        except Exception:
            pass

        return GPUResult(
            available=True,
            name=name,
            utilization_percent=utilization,
            memory_used_gb=memory_used,
            memory_total_gb=memory_total,
            memory_percent=memory_percent,
            temperature_c=temperature,
            temperature_status=temperature_status,
            power_w=power,
            power_status=power_status,
            fan_percent=fan,
            fan_status=fan_status,
            fan_rpm=fan_rpm,
            fan_rpm_status=fan_rpm_status,
            thermal_throttling=thermal_throttling,
        )
    except Exception as exc:
        return GPUResult(available=False, error=f"Could not read NVIDIA GPU: {exc}")
    finally:
        if initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass


def read_platform_hardware() -> tuple[str | None, str | None, float | None, str]:
    """Read CPU/RAM identity and CPU temperature from Windows hardware sources."""
    if os.name != "nt":
        return None, None, None, "Windows hardware providers are unavailable"

    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name
$memoryModules = @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
    [pscustomobject]@{ manufacturer = [string]$_.Manufacturer; part_number = [string]$_.PartNumber }
})
$matches = @()
foreach ($namespace in @('root/LibreHardwareMonitor', 'root/OpenHardwareMonitor')) {
    try {
        $sensors = Get-CimInstance -Namespace $namespace -ClassName Sensor -ErrorAction Stop |
            Where-Object { $_.SensorType -eq 'Temperature' -and $_.Name -match '(?i)CPU.*(Package|Die|CCD|Core)|(Package|Die|CCD|Core).*CPU' }
        foreach ($sensor in $sensors) {
            $matches += [pscustomobject]@{ name = [string]$sensor.Name; value = [double]$sensor.Value }
        }
    } catch {}
}
[pscustomobject]@{ cpu_name = [string]$processor; memory_modules = @($memoryModules); sensors = @($matches) } | ConvertTo-Json -Compress -Depth 3
"""
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        payload = json.loads(completed.stdout)
        cpu_name = str(payload.get("cpu_name") or "").strip() or None
        module_names = []
        for module in payload.get("memory_modules", []):
            manufacturer = str(module.get("manufacturer", "")).strip()
            part_number = str(module.get("part_number", "")).strip()
            useful_values = [
                value for value in (manufacturer, part_number)
                if value and value.lower() not in {"unknown", "not specified", "to be filled by o.e.m.", "0"}
            ]
            if useful_values:
                module_name = " ".join(useful_values)
                if module_name not in module_names:
                    module_names.append(module_name)
        if not module_names:
            ram_description = None
        elif len(module_names) <= 2:
            ram_description = "; ".join(module_names)
        else:
            ram_description = f"{'; '.join(module_names[:2])} + {len(module_names) - 2} more"

        sensors = payload.get("sensors", [])
        if isinstance(sensors, dict):
            sensors = [sensors]
        if not sensors:
            return cpu_name, ram_description, None, "no supported CPU sensor provider is running"

        def sensor_priority(sensor: dict[str, object]) -> int:
            name = str(sensor.get("name", "")).lower()
            if "package" in name:
                return 0
            if "die" in name or "ccd" in name:
                return 1
            return 2

        selected = min(sensors, key=sensor_priority)
        return cpu_name, ram_description, float(selected["value"]), ""
    except subprocess.TimeoutExpired:
        return None, None, None, "CPU sensor query timed out"
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        return None, None, None, "CPU sensor query failed"


def read_hardware_sensors() -> HardwareSensorResult:
    """Collect CPU/RAM identity and CPU/GPU sensor data in one worker."""
    cpu_name, ram_description, cpu_temperature_c, cpu_temperature_status = (
        read_platform_hardware()
    )
    return HardwareSensorResult(
        cpu_name=cpu_name,
        cpu_temperature_c=cpu_temperature_c,
        cpu_temperature_status=cpu_temperature_status,
        ram_description=ram_description,
        gpu=read_gpu(),
    )
