"""
PULSE — local PC monitor (sci-fi Phase 1 UI)

Start it with:  python main.py

Beginner notes:
- metrics.py still reads the real PC values through psutil.
- theme.py and widgets.py only change how the window looks.
- This file builds the window and updates labels in place every second.
- Future sidebar pages are placeholders. They do not invent extra data.
"""

from __future__ import annotations

import sys
import time
from collections import deque

from PySide6.QtCore import QDateTime, QObject, QRunnable, QRectF, QThreadPool, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from metrics import (
    HardwareSensorResult,
    prime_cpu_counter,
    read_cpu,
    read_disk,
    read_hardware_sensors,
    read_ram,
)
from diagnostics import DiagnosticSample, analyze_samples
from storage_health import StorageScan, scan_storage
from theme import STYLESHEET
from widgets import (
    CYAN,
    LogoMark,
    BottleneckDetectivePanel,
    MetricCard,
    NavButton,
    SystemOverviewPanel,
    StorageHealthPanel,
    angular_path,
    draw_glow_path,
    logo_icon,
)


# Sidebar destinations. Only "overview" has a real page today.
NAV_ITEMS = [
    ("overview", "Overview", "home", True),
    ("bottleneck", "Bottleneck Detective", "chart", True),
    ("storage_health", "Storage Health", "disk", True),
    ("performance", "Performance", "chart", False),
    ("gaming", "Gaming Sessions", "game", False),
    ("incidents", "Incident History", "clock", False),
    ("reports", "Reports", "file", False),
]


class PulseWorkerSignals(QObject):
    gpu_finished = Signal(object)
    gpu_failed = Signal(str)
    storage_finished = Signal(object)


class GPUReader(QRunnable):
    """Run NVML queries away from the GUI thread."""

    def __init__(self, signals: PulseWorkerSignals) -> None:
        super().__init__()
        self.signals = signals

    def run(self) -> None:
        try:
            self.signals.gpu_finished.emit(read_hardware_sensors())
        except Exception as exc:
            self.signals.gpu_failed.emit(str(exc))


class StorageReader(QRunnable):
    """Run bounded read-only SMART discovery away from the GUI thread."""

    def __init__(self, signals: PulseWorkerSignals) -> None:
        super().__init__()
        self.signals = signals

    def run(self) -> None:
        try:
            result = scan_storage()
        except Exception:
            result = StorageScan(
                available=True, message="Storage health scan failed unexpectedly.")
        self.signals.storage_finished.emit(result)


def format_gb(value: float) -> str:
    """Show gigabytes with two decimal places, for example 7.25 GB."""
    return f"{value:.2f} GB"


def local_os_label() -> str:
    """
    Describe this operating system from real Windows version info.

    Windows 11 still reports NT 10.0. Microsoft's documented cutoff
    for Windows 11 is build 22000, so that is what we use.
    """
    if sys.platform != "win32":
        return sys.platform
    version = sys.getwindowsversion()
    if version.major == 10 and version.build >= 22000:
        return "Windows 11"
    if version.major == 10:
        return "Windows 10"
    return f"Windows {version.major}.{version.minor}"


class AmbientBackground(QWidget):
    """Deep navy canvas with a restrained cyan bloom. No fake data."""

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor("#050910"))
        base.setColorAt(0.55, QColor("#071322"))
        base.setColorAt(1.0, QColor("#04070D"))
        painter.fillRect(rect, base)

        glow = QRadialGradient(rect.width() * 0.78,
                               rect.height() * 0.08, rect.width() * 0.45)
        glow.setColorAt(0.0, QColor(34, 180, 255, 55))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, glow)


class CardStrip(QWidget):
    """Holds the three metric cards and stacks them if the window gets narrow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cards_layout = QHBoxLayout(self)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setSpacing(14)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def add_card(self, card: QWidget) -> None:
        self.cards_layout.addWidget(card, stretch=1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        narrow = self.width() < 860
        if narrow:
            self.cards_layout.setDirection(QBoxLayout.Direction.TopToBottom)
        else:
            self.cards_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        stretch = 0 if narrow else 1
        for index in range(self.cards_layout.count()):
            self.cards_layout.setStretch(index, stretch)


class ComingPanel(QFrame):
    """Placeholder plate with the same cut-corner chrome as the live cards."""

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = angular_path(rect, cut=16)
        painter.fillPath(path, QColor(10, 24, 42, 230))
        draw_glow_path(painter, path, CYAN, width=1.2)


class ComingSoonPage(QWidget):
    """Honest placeholder so unused sidebar items are not fake finished pages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 16, 0, 0)

        panel = ComingPanel()
        panel.setObjectName("comingPanel")
        panel.setMaximumWidth(560)

        inner = QVBoxLayout(panel)
        inner.setContentsMargins(28, 28, 28, 28)
        inner.setSpacing(10)

        self.title_label = QLabel("Coming in a future update")
        self.title_label.setObjectName("comingTitle")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel()
        self.body_label.setObjectName("comingBody")
        self.body_label.setWordWrap(True)

        inner.addWidget(self.title_label)
        inner.addWidget(self.body_label)

        outer.addWidget(panel, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addStretch(1)

    def set_section(self, name: str) -> None:
        """Name the unfinished section without inventing features inside it."""
        self.body_label.setText(
            f"{name} is not part of this version. "
            "PULSE currently monitors local CPU, RAM, storage, NVIDIA GPU, and "
            "evidence-based bottleneck signals."
        )


class PulseWindow(QMainWindow):
    """Main PULSE window: sidebar, header, Overview cards, and placeholders."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PULSE - PC Health Monitor")
        self.setWindowIcon(logo_icon())
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)

        shell = AmbientBackground()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)

        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_content(), stretch=1)

        prime_cpu_counter()
        self._gpu_reading = False
        self._storage_reading = False
        self._storage_scan_started = False
        self._latest_gpu_result = None
        self._latest_hardware_sensors = None
        self._latest_gpu_timestamp = None
        self._last_diagnostic_gpu_timestamp = None
        self._latest_ram_available_gb = None
        self._diagnostic_samples: deque[DiagnosticSample] = deque(maxlen=60)
        self._closing = False
        self._worker_pool = QThreadPool(self)
        self._worker_pool.setMaxThreadCount(2)
        self._worker_signals = PulseWorkerSignals(self)
        self._worker_signals.gpu_finished.connect(self._update_gpu_card)
        self._worker_signals.gpu_failed.connect(self._gpu_read_failed)
        self._worker_signals.storage_finished.connect(
            self._update_storage_panel)

        # Refresh labels in place. Never rebuild the window on the timer.
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_metrics)
        self.timer.start()

        self.refresh_metrics(include_cpu=False)
        self.show_page("overview")

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(6)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo_row.addWidget(LogoMark(46))

        word_block = QVBoxLayout()
        word_block.setSpacing(0)
        word = QLabel("PULSE")
        word.setObjectName("logoWord")
        tag = QLabel("PC HEALTH MONITOR")
        tag.setObjectName("logoTag")
        word_block.addWidget(word)
        word_block.addWidget(tag)

        logo_row.addLayout(word_block)
        logo_row.addStretch(1)
        layout.addLayout(logo_row)
        layout.addSpacing(22)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, NavButton] = {}

        for page_id, label, icon_kind, implemented in NAV_ITEMS:
            button = NavButton(label, icon_kind, coming_soon=not implemented)
            button.clicked.connect(lambda _checked=False,
                                   pid=page_id: self.show_page(pid))
            self.nav_group.addButton(button)
            self.nav_buttons[page_id] = button
            layout.addWidget(button)

        self.nav_buttons["overview"].setChecked(True)
        layout.addStretch(1)

        tagline = QLabel("BETTER INSIGHTS\nFOR A HEALTHIER PC")
        tagline.setObjectName("sideTagline")
        tagline.setWordWrap(True)
        layout.addWidget(tagline)
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("content")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(26, 18, 26, 12)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(16)

        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.page_title = QLabel("Overview")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel(
            "Live CPU, RAM, and system-drive storage on this PC.")
        self.page_subtitle.setObjectName("pageSubtitle")
        self.page_subtitle.setWordWrap(True)
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)

        status_chip = QFrame()
        status_chip.setObjectName("statusChip")
        status_chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        status_layout = QVBoxLayout(status_chip)
        status_layout.setContentsMargins(12, 8, 14, 8)
        status_layout.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_title = QLabel("System Status")
        self.status_title.setObjectName("statusTitle")
        row.addWidget(self.status_dot)
        row.addWidget(self.status_title)
        row.addStretch(1)
        self.status_text = QLabel("Waiting for readings")
        self.status_text.setObjectName("statusText")
        status_layout.addLayout(row)
        status_layout.addWidget(self.status_text)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        self.clock_time = QLabel("")
        self.clock_time.setObjectName("clockTime")
        self.clock_time.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.clock_date = QLabel("")
        self.clock_date.setObjectName("clockDate")
        self.clock_date.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.clock_time)
        clock_box.addWidget(self.clock_date)

        header.addLayout(titles, stretch=1)
        header.addWidget(status_chip, alignment=Qt.AlignmentFlag.AlignTop)
        header.addLayout(clock_box)

        self.stack = QStackedWidget()
        self.overview_page = self._build_overview()
        self.detective_page = self._build_detective_page()
        self.storage_health_page = self._build_storage_health_page()
        self.coming_page = ComingSoonPage()
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.detective_page)
        self.stack.addWidget(self.storage_health_page)
        self.stack.addWidget(self.coming_page)

        footer = QLabel("PULSE  /  LOCAL SYSTEM MONITOR")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(header)
        layout.addWidget(self.stack, stretch=1)
        layout.addWidget(footer)
        self._update_clock()
        return content

    def _build_overview(self) -> QWidget:
        """Overview holds the three live cards plus the cosmic system panel."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.viewport().setAutoFillBackground(False)

        inner = QWidget()
        inner.setObjectName("overviewInner")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 8, 0)
        inner_layout.setSpacing(14)

        strip = CardStrip()
        strip.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Minimum)
        self.cpu_card = MetricCard(
            "CPU", "Processor Usage", "cpu", accent="cyan")
        self.ram_card = MetricCard(
            "RAM", "Memory Usage", "ram", accent="violet")
        self.disk_card = MetricCard(
            "Disk", "Storage Usage", "disk", accent="cyan")
        self.gpu_card = MetricCard("GPU", "NVIDIA GPU", "cpu", accent="violet")
        strip.add_card(self.cpu_card)
        strip.add_card(self.ram_card)
        strip.add_card(self.disk_card)
        strip.add_card(self.gpu_card)

        self.overview_panel = SystemOverviewPanel()
        self.overview_panel.os_chip.value.setText(local_os_label())

        inner_layout.addWidget(strip)
        inner_layout.addWidget(self.overview_panel, stretch=1)

        scroll.setWidget(inner)
        page_layout.addWidget(scroll)
        return page

    def _build_detective_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.viewport().setAutoFillBackground(False)
        self.detective_panel = BottleneckDetectivePanel()
        scroll.setWidget(self.detective_panel)
        layout.addWidget(scroll)
        return page

    def _build_storage_health_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self.storage_refresh_button = QPushButton("Refresh Storage Health")
        self.storage_refresh_button.setObjectName("storageRefreshButton")
        self.storage_refresh_button.setCursor(
            Qt.CursorShape.PointingHandCursor)
        self.storage_refresh_button.clicked.connect(self._start_storage_scan)
        header.addStretch(1)
        header.addWidget(self.storage_refresh_button)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.viewport().setAutoFillBackground(False)
        self.storage_health_panel = StorageHealthPanel()
        scroll.setWidget(self.storage_health_panel)
        layout.addWidget(scroll, stretch=1)
        return page

    def show_page(self, page_id: str) -> None:
        """Switch the stacked view. Future pages stay honest placeholders."""
        names = {item[0]: item[1] for item in NAV_ITEMS}
        implemented = {item[0]: item[3] for item in NAV_ITEMS}
        title = names.get(page_id, page_id)
        self.page_title.setText(title)
        self.nav_buttons[page_id].setChecked(True)

        if page_id == "overview":
            self.page_subtitle.setText(
                "Live CPU, RAM, and system-drive storage on this PC."
            )
            self.stack.setCurrentWidget(self.overview_page)
            return

        if page_id == "bottleneck":
            self.page_subtitle.setText(
                "Evidence-based performance signals from rolling hardware readings."
            )
            self.stack.setCurrentWidget(self.detective_page)
            return

        if page_id == "storage_health":
            self.page_subtitle.setText(
                "Read-only SMART health and supported drive sensor information."
            )
            self.stack.setCurrentWidget(self.storage_health_page)
            if not self._storage_scan_started:
                self._start_storage_scan()
            return

        self.page_subtitle.setText("This section is not implemented yet.")
        self.coming_page.set_section(title)
        self.stack.setCurrentWidget(self.coming_page)

    def refresh_metrics(self, include_cpu: bool = True) -> None:
        """Ask psutil for new readings and update existing widgets only."""
        self._start_gpu_read()
        cpu_ok = None
        ram_ok = None
        disk_ok = None
        cpu_percent = None
        ram_percent = None
        disk_percent = None

        if include_cpu:
            cpu_ok, cpu_percent = self._update_cpu_card()
        ram_ok, ram_percent = self._update_ram_card()
        disk_ok, disk_percent = self._update_disk_card()
        self._record_diagnostic_sample(
            cpu_percent if include_cpu else None, ram_percent)
        self._update_status(cpu_ok, ram_ok, disk_ok,
                            cpu_percent, ram_percent, disk_percent)
        self._update_clock()

    def _start_gpu_read(self) -> None:
        if self._closing or self._gpu_reading:
            return
        self._gpu_reading = True
        self._worker_pool.start(GPUReader(self._worker_signals))

    def _start_storage_scan(self) -> None:
        if self._closing or self._storage_reading:
            return
        self._storage_reading = True
        self._storage_scan_started = True
        self.storage_refresh_button.setEnabled(False)
        self.storage_health_panel.status.setText(
            "Scanning drives with read-only SMART queries…")
        self._worker_pool.start(StorageReader(self._worker_signals))

    def _update_storage_panel(self, result: StorageScan) -> None:
        if self._closing:
            return
        self._storage_reading = False
        self.storage_refresh_button.setEnabled(True)
        self.storage_health_panel.set_scan(result)

    def _update_gpu_card(self, sensors: HardwareSensorResult) -> None:
        if self._closing:
            return
        self._gpu_reading = False
        self._latest_hardware_sensors = sensors
        self._latest_gpu_result = sensors.gpu
        self._latest_gpu_timestamp = time.monotonic()
        if sensors.cpu_temperature_c is not None:
            cpu_temperature = f"{sensors.cpu_temperature_c:.1f} °C"
        else:
            cpu_temperature = "Temperature unavailable"
            if sensors.cpu_temperature_status:
                cpu_temperature += f" ({sensors.cpu_temperature_status})"
        self.cpu_card.set_extra_details(
            f"{sensors.cpu_name or 'CPU name unavailable'}  ·  {cpu_temperature}  ·  "
            "CPU thermal throttling: Unavailable (no reliable documented sensor source)"
        )
        self.cpu_card.set_title("CPU", sensors.cpu_name or "Processor Usage")
        self.ram_card.set_title(
            "RAM", sensors.ram_description or "Memory Usage")

        result = sensors.gpu
        if not result.available:
            self.gpu_card.set_title("GPU", "NVIDIA GPU")
            self.gpu_card.show_unavailable(
                result.error or "GPU is unavailable.")
            return

        self.gpu_card.set_title("GPU", result.name)
        utilization = result.utilization_percent
        self.gpu_card.gauge.set_value(utilization)
        self.gpu_card.bar.set_value(utilization)
        self.gpu_card.stat_primary_name.setText("Dedicated Memory")
        if result.memory_used_gb is not None and result.memory_total_gb is not None:
            self.gpu_card.stat_primary_value.setText(
                f"{format_gb(result.memory_used_gb)} / {format_gb(result.memory_total_gb)}"
            )
        else:
            self.gpu_card.stat_primary_value.setText("Unavailable")

        self.gpu_card.stat_secondary_name.setText("Memory Usage")
        self.gpu_card.stat_secondary_value.setText(
            f"{result.memory_percent:.1f}%" if result.memory_percent is not None else "Unavailable"
        )
        self.gpu_card.message_label.hide()
        self.gpu_card.bar.setVisible(utilization is not None)
        details = [
            f"GPU utilization: {utilization:.1f}%" if utilization is not None else "GPU utilization: Unavailable",
            f"Temperature: {result.temperature_c} °C" if result.temperature_c is not None else "Temperature unavailable",
            f"Power: {result.power_w:.1f} W" if result.power_w is not None else f"Power: {result.power_status}",
            f"Fan: {result.fan_percent}%" if result.fan_percent is not None else f"Fan: {result.fan_status}",
            f"Fan speed: {result.fan_rpm} RPM" if result.fan_rpm is not None else f"Fan speed: {result.fan_rpm_status}",
            f"Thermal throttling: {result.thermal_throttling}",
        ]
        self.gpu_card.set_extra_details("  ·  ".join(details))

    def _gpu_read_failed(self, message: str) -> None:
        if self._closing:
            return
        self._gpu_reading = False
        self.gpu_card.show_unavailable(
            f"GPU sensor query failed: {message or 'unknown error'}")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop periodic work and drain this window's workers before Qt deletes widgets."""
        self._closing = True
        self.timer.stop()
        self.storage_refresh_button.setEnabled(False)
        self._worker_signals.gpu_finished.disconnect(self._update_gpu_card)
        self._worker_signals.gpu_failed.disconnect(self._gpu_read_failed)
        self._worker_signals.storage_finished.disconnect(
            self._update_storage_panel)
        self._worker_pool.waitForDone()
        event.accept()

    def _record_diagnostic_sample(
        self, cpu_percent: float | None, ram_percent: float | None
    ) -> None:
        """Append real readings once per timer tick, without duplicating GPU polls."""
        gpu = self._latest_gpu_result
        gpu_timestamp = self._latest_gpu_timestamp
        has_new_gpu_sample = (
            gpu is not None
            and gpu_timestamp is not None
            and gpu_timestamp != self._last_diagnostic_gpu_timestamp
            and time.monotonic() - gpu_timestamp <= 3.0
        )
        self._diagnostic_samples.append(DiagnosticSample(
            timestamp=time.monotonic(),
            cpu_percent=cpu_percent,
            gpu_percent=(
                gpu.utilization_percent if has_new_gpu_sample and gpu.available else None),
            ram_percent=ram_percent,
            ram_available_gb=self._latest_ram_available_gb,
            gpu_memory_percent=(
                gpu.memory_percent if has_new_gpu_sample and gpu.available else None),
            gpu_thermal_throttling=(
                gpu.thermal_throttling if has_new_gpu_sample and gpu.available else None),
        ))
        if has_new_gpu_sample:
            self._last_diagnostic_gpu_timestamp = gpu_timestamp
        self.detective_panel.set_report(
            analyze_samples(tuple(self._diagnostic_samples)))

    def _update_clock(self) -> None:
        now = QDateTime.currentDateTime()
        self.clock_time.setText(now.toString("h:mm AP"))
        self.clock_date.setText(now.toString("MMM d, yyyy"))

    def _update_cpu_card(self) -> tuple[bool, float | None]:
        result = read_cpu()
        if not result.ok:
            self.cpu_card.show_unavailable(
                result.error or "CPU is unavailable.")
            self.overview_panel.core_chip.value.setText("—")
            self.overview_panel.logical_chip.value.setText("—")
            return False, None

        self.cpu_card.show_ok(
            percent=result.percent or 0.0,
            primary_name="Cores",
            primary_value=str(result.physical_cores),
            secondary_name="Logical Processors",
            secondary_value=str(result.logical_processors),
        )
        self.cpu_card.sparkline.add_sample(result.percent or 0.0)
        if self.cpu_card.sparkline.has_trend():
            self.cpu_card.sparkline.show()
            self.cpu_card.bar.hide()
        else:
            self.cpu_card.sparkline.hide()
            self.cpu_card.bar.show()
        self.overview_panel.core_chip.value.setText(str(result.physical_cores))
        self.overview_panel.logical_chip.value.setText(
            str(result.logical_processors))
        return True, result.percent

    def _update_ram_card(self) -> tuple[bool, float | None]:
        result = read_ram()
        if not result.ok:
            self._latest_ram_available_gb = None
            self.ram_card.show_unavailable(
                result.error or "RAM is unavailable.")
            return False, None

        self.ram_card.show_ok(
            percent=result.percent or 0.0,
            primary_name="Used",
            primary_value=format_gb(result.used_gb),
            secondary_name="Total",
            secondary_value=format_gb(result.total_gb),
        )
        if self._latest_hardware_sensors and self._latest_hardware_sensors.ram_description:
            self.ram_card.set_title(
                "RAM", self._latest_hardware_sensors.ram_description)
        else:
            self.ram_card.set_title("RAM", "Memory Usage")
        self._latest_ram_available_gb = result.available_gb
        return True, result.percent

    def _update_disk_card(self) -> tuple[bool, float | None]:
        result = read_disk()
        if not result.ok:
            self.disk_card.show_unavailable(
                result.error or "Disk is unavailable.")
            return False, None

        drive = (result.drive or "").rstrip("\\")
        self.disk_card.set_title(f"Disk ({drive})", "Storage Usage")
        self.disk_card.show_ok(
            percent=result.percent or 0.0,
            primary_name="Used",
            primary_value=format_gb(result.used_gb),
            secondary_name="Total",
            secondary_value=format_gb(result.total_gb),
        )
        return True, result.percent

    def _update_status(
        self,
        cpu_ok: bool | None,
        ram_ok: bool | None,
        disk_ok: bool | None,
        cpu_percent: float | None,
        ram_percent: float | None,
        disk_percent: float | None,
    ) -> None:
        """
        Status is only about readings this app can take.
        It never says the whole PC is healthy.
        """
        parts = []
        if cpu_ok is True:
            parts.append("CPU")
        elif cpu_ok is False:
            parts.append("CPU unavailable")
        else:
            parts.append("CPU measuring")

        if ram_ok is True:
            parts.append("RAM")
        elif ram_ok is False:
            parts.append("RAM unavailable")

        if disk_ok is True:
            parts.append("Disk")
        elif disk_ok is False:
            parts.append("Disk unavailable")

        failed = [flag for flag in (cpu_ok, ram_ok, disk_ok) if flag is False]
        if failed:
            state = "error" if len(failed) >= 2 else "warn"
        else:
            state = "ok"

        if failed:
            self.status_text.setText("Readings: " + " · ".join(parts))
        elif cpu_ok is None:
            self.status_text.setText("Readings: " + " · ".join(parts))
        else:
            self.status_text.setText("Monitoring")

        self.status_dot.setProperty("state", state)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)

        self._update_overview_copy(
            cpu_ok, ram_ok, disk_ok, cpu_percent, ram_percent, disk_percent)

    def _update_overview_copy(
        self,
        cpu_ok: bool | None,
        ram_ok: bool | None,
        disk_ok: bool | None,
        cpu_percent: float | None,
        ram_percent: float | None,
        disk_percent: float | None,
    ) -> None:
        """Write a status sentence that is justified by the live numbers we have."""
        missing = []
        if cpu_ok is False:
            missing.append("CPU")
        if ram_ok is False:
            missing.append("RAM")
        if disk_ok is False:
            missing.append("disk")

        if missing:
            self.overview_panel.status_title.setText(
                "Some readings are unavailable")
            self.overview_panel.status_body.setText(
                "Could not read " + ", ".join(missing) + " on this PC."
            )
            return

        if cpu_ok is None:
            self.overview_panel.status_title.setText("Waiting for CPU sample")
            self.overview_panel.status_body.setText(
                "RAM and disk are live. CPU usage needs a second sample before it can be shown."
            )
            return

        high = []
        if cpu_percent is not None and cpu_percent >= 90:
            high.append(f"CPU {cpu_percent:.1f}%")
        if ram_percent is not None and ram_percent >= 90:
            high.append(f"RAM {ram_percent:.1f}%")
        if disk_percent is not None and disk_percent >= 90:
            high.append(f"disk {disk_percent:.1f}%")

        if high:
            self.overview_panel.status_title.setText(
                "High usage on live readings")
            self.overview_panel.status_body.setText(
                "Current measurements: " + ", ".join(high) + "."
            )
            return

        self.overview_panel.status_title.setText("Live readings are available")
        self.overview_panel.status_body.setText(
            "CPU, RAM, and system-drive storage are being measured on this PC."
        )


def main() -> int:
    """Create the Qt application, show PULSE, and start the event loop."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("PULSE")
    app.setWindowIcon(logo_icon())
    app.setStyleSheet(STYLESHEET)

    window = PulseWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
