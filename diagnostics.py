"""Conservative, explainable performance-pressure rules for Pulse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DiagnosticSample:
    """One real monitoring tick; unavailable measurements stay as None."""

    timestamp: float
    cpu_percent: float | None = None
    gpu_percent: float | None = None
    ram_percent: float | None = None
    ram_available_gb: float | None = None
    gpu_memory_percent: float | None = None
    gpu_thermal_throttling: str | None = None


@dataclass(frozen=True)
class DiagnosticThresholds:
    """Configurable conservative thresholds for sustained observations."""

    window_samples: int = 8
    minimum_samples: int = 5
    sustained_fraction: float = 0.75
    cpu_percent: float = 85.0
    gpu_percent: float = 90.0
    ram_percent: float = 88.0
    ram_available_gb: float = 1.5
    gpu_memory_percent: float = 92.0


@dataclass(frozen=True)
class Finding:
    component: str
    title: str
    priority: int
    confidence: str
    observed: str
    why_it_matters: str
    next_action: str
    verification: str


@dataclass(frozen=True)
class DiagnosticReport:
    assessment: str
    evidence_window: str
    findings: tuple[Finding, ...]
    limitations: tuple[str, ...]


def _sustained(
    samples: Sequence[DiagnosticSample],
    value_getter,
    condition,
    thresholds: DiagnosticThresholds,
) -> tuple[bool, list[float]]:
    window = samples[-thresholds.window_samples:]
    values = [value for sample in window if (
        value := value_getter(sample)) is not None]
    if len(values) < thresholds.minimum_samples:
        return False, values
    matches = sum(condition(value) for value in values)
    return matches / len(values) >= thresholds.sustained_fraction, values


def analyze_samples(
    samples: Sequence[DiagnosticSample],
    thresholds: DiagnosticThresholds = DiagnosticThresholds(),
) -> DiagnosticReport:
    """Create prioritized findings from real samples without assigning a score."""
    findings: list[Finding] = []
    recent = samples[-thresholds.window_samples:]

    cpu_high, cpu_values = _sustained(
        samples, lambda sample: sample.cpu_percent,
        lambda value: value >= thresholds.cpu_percent, thresholds,
    )
    gpu_high, gpu_values = _sustained(
        samples, lambda sample: sample.gpu_percent,
        lambda value: value >= thresholds.gpu_percent, thresholds,
    )
    ram_high, ram_values = _sustained(
        samples,
        lambda sample: (
            (sample.ram_percent, sample.ram_available_gb)
            if sample.ram_percent is not None and sample.ram_available_gb is not None
            else None
        ),
        lambda values: (
            values[0] >= thresholds.ram_percent
            and values[1] <= thresholds.ram_available_gb
        ),
        thresholds,
    )
    gpu_memory_high, gpu_memory_values = _sustained(
        samples, lambda sample: sample.gpu_memory_percent,
        lambda value: value >= thresholds.gpu_memory_percent, thresholds,
    )

    if cpu_high:
        average = sum(cpu_values) / len(cpu_values)
        both_busy = gpu_high
        findings.append(Finding(
            component="CPU",
            title="Sustained high CPU utilization",
            priority=2,
            confidence="Medium",
            observed=(f"CPU averaged {average:.1f}% over {len(cpu_values)} readings; "
                      f"at least {thresholds.sustained_fraction:.0%} met the "
                      f"{thresholds.cpu_percent:.0f}% threshold."),
            why_it_matters=(
                "High system-wide CPU load can leave less processing time for "
                "the foreground task, but it does not identify which process is responsible."
            ),
            next_action=(
                "During the slowdown, inspect Task Manager's Processes tab for "
                "sustained CPU use. Close only applications you recognize and do not need."
            ),
            verification=(
                "Repeat the same workload and compare CPU utilization and responsiveness."
            ),
        ))

    if gpu_high:
        average = sum(gpu_values) / len(gpu_values)
        findings.append(Finding(
            component="GPU",
            title="Sustained high GPU utilization",
            priority=2 if both_busy else 3,
            confidence="Medium",
            observed=(f"GPU averaged {average:.1f}% over {len(gpu_values)} readings; "
                      f"at least {thresholds.sustained_fraction:.0%} met the "
                      f"{thresholds.gpu_percent:.0f}% threshold."),
            why_it_matters=(
                "The GPU is consistently busy. This may limit graphics-heavy work, "
                "but high use can also be expected for the chosen task."
            ),
            next_action=(
                "If the task feels slow, try a lower render resolution or graphics "
                "quality setting for that task. Do not change clocks or voltage."
            ),
            verification=(
                "Compare frame rate or task completion time and GPU utilization "
                "before and after the setting change."
            ),
        ))

    if ram_high:
        paired = [
            sample for sample in recent
            if sample.ram_percent is not None and sample.ram_available_gb is not None
        ]
        average_percent = sum(
            sample.ram_percent for sample in paired) / len(paired)
        minimum_available = min(sample.ram_available_gb for sample in paired)
        findings.append(Finding(
            component="RAM",
            title="Sustained system memory pressure",
            priority=1,
            confidence="High",
            observed=(f"RAM averaged {average_percent:.1f}% used and available memory "
                      f"fell to {minimum_available:.2f} GB across {len(paired)} paired readings."),
            why_it_matters=(
                "High use together with very little available memory can cause "
                "Windows to reclaim or page memory, which may reduce responsiveness."
            ),
            next_action=(
                "Check Task Manager for applications using the most memory; save your "
                "work, then close only applications you recognize and do not need."
            ),
            verification=(
                "Repeat the same workload and check whether available memory and "
                "responsiveness improve."
            ),
        ))

    if gpu_memory_high:
        average = sum(gpu_memory_values) / len(gpu_memory_values)
        findings.append(Finding(
            component="GPU",
            title="High dedicated GPU-memory occupancy",
            priority=3,
            confidence="Medium",
            observed=(f"Dedicated GPU memory averaged {average:.1f}% used over "
                      f"{len(gpu_memory_values)} readings."),
            why_it_matters=(
                "Near-full dedicated memory can constrain some graphics workloads; "
                "occupancy alone does not prove that memory is limiting performance."
            ),
            next_action=(
                "For a graphics-heavy task, try lower texture quality or close an "
                "unneeded graphics application."
            ),
            verification=(
                "Compare dedicated memory use and the task's responsiveness after the change."
            ),
        ))

    active_thermal = next((
        sample.gpu_thermal_throttling
        for sample in reversed(recent)
        if sample.gpu_thermal_throttling
        and sample.gpu_thermal_throttling.startswith("Active")
    ), None)
    if active_thermal:
        findings.append(Finding(
            component="GPU",
            title="GPU thermal throttling reported by NVML",
            priority=1,
            confidence="High",
            observed=f"NVML reported {active_thermal} during a recent reading.",
            why_it_matters=(
                "The GPU driver reports a thermal throttle reason; this is direct "
                "sensor evidence, not an inference from temperature alone."
            ),
            next_action=(
                "Check that the PC's vents are unobstructed and fans can move air. "
                "Avoid overclocking; seek hardware support if this persists."
            ),
            verification=(
                "After airflow is checked, repeat the workload and see whether NVML "
                "continues to report thermal throttling."
            ),
        ))

    sample_counts = {
        "CPU": sum(sample.cpu_percent is not None for sample in recent),
        "GPU": sum(sample.gpu_percent is not None for sample in recent),
        "RAM": sum(
            sample.ram_percent is not None and sample.ram_available_gb is not None
            for sample in recent
        ),
    }
    eligible = sum(
        count >= thresholds.minimum_samples for count in sample_counts.values())
    eligible += int(len(gpu_memory_values) >= thresholds.minimum_samples)
    if eligible == 0 and not active_thermal:
        assessment = "Insufficient data"
    elif findings and cpu_high and gpu_high:
        assessment = "Multiple pressure signals; the limiting component is unclear"
    elif findings:
        assessment = "Potential performance pressure detected"
    else:
        assessment = "No sustained pressure signals detected"

    count = len(recent)
    evidence_window = (
        f"{count} of {thresholds.window_samples} recent samples; "
        f"CPU {sample_counts['CPU']}, GPU {sample_counts['GPU']}, "
        f"RAM with available-memory data {sample_counts['RAM']} "
        f"(minimum {thresholds.minimum_samples} per rule)."
    )
    limitations = (
        "Storage pressure is not assessed: Pulse has no reliable per-drive activity "
        "and response-latency measurements.",
        "CPU and GPU utilization are system-wide signals; Pulse cannot attribute "
        "them to a specific application or prove a task-specific bottleneck.",
    )
    if sample_counts["GPU"] < thresholds.minimum_samples:
        limitations += ("GPU utilization history is insufficient or unavailable.",)
    if sample_counts["RAM"] < thresholds.minimum_samples:
        limitations += ("Paired RAM-use and available-memory history is insufficient or unavailable.",)

    findings.sort(key=lambda finding: (finding.priority, finding.component))
    return DiagnosticReport(
        assessment=assessment,
        evidence_window=evidence_window,
        findings=tuple(findings),
        limitations=limitations,
    )
