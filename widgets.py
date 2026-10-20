"""
PULSE custom-drawn widgets.

These classes only handle appearance: gauges, icons, panels, and the logo.
They never call psutil. Live numbers are passed in from main.py.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from diagnostics import DiagnosticReport, Finding
from storage_health import StorageDrive, StorageScan


ASSETS_DIR = Path(__file__).resolve().parent / "assets"

CYAN = QColor("#22E0FF")
CYAN_SOFT = QColor("#67E8F9")
BLUE = QColor("#3B82F6")
VIOLET = QColor("#A78BFA")
VIOLET_DEEP = QColor("#7C3AED")
NAVY = QColor("#07111F")
PANEL = QColor(10, 22, 40, 210)
TEXT = QColor("#E8F4FF")
MUTED = QColor("#8BA3C1")
DANGER = QColor("#F87171")


def angular_path(rect: QRectF, cut: float = 14.0) -> QPainterPath:
    """
    Build a sci-fi panel outline with clipped corners.

    cut controls how sharp the corners look. A larger cut makes a more
    angular, armor-like plate.
    """
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    cut = min(cut, w * 0.18, h * 0.18)
    path = QPainterPath()
    path.moveTo(x + cut, y)
    path.lineTo(x + w - cut, y)
    path.lineTo(x + w, y + cut)
    path.lineTo(x + w, y + h - cut)
    path.lineTo(x + w - cut, y + h)
    path.lineTo(x + cut, y + h)
    path.lineTo(x, y + h - cut)
    path.lineTo(x, y + cut)
    path.closeSubpath()
    return path


def draw_glow_path(painter: QPainter, path: QPainterPath, color: QColor, width: float = 1.6) -> None:
    """Draw a thin border, then two wider, faint copies to fake a glow."""
    for extra, alpha in ((width + 7, 28), (width + 3, 70), (width, 230)):
        glow = QColor(color)
        glow.setAlpha(alpha)
        pen = QPen(glow, extra)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


def paint_pulse_mark(painter: QPainter, rect: QRectF) -> None:
    """
    Draw the PULSE mark: an angular plate plus a pulse-shaped P.

    Coordinates are written for a 128x128 square, then scaled into rect
    so the same art stays sharp at sidebar and window-icon sizes.
    """
    painter.save()
    painter.translate(rect.topLeft())
    painter.scale(rect.width() / 128.0, rect.height() / 128.0)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    plate = QPainterPath()
    plate.moveTo(18, 28)
    plate.lineTo(46, 8)
    plate.lineTo(86, 8)
    plate.lineTo(114, 36)
    plate.lineTo(114, 78)
    plate.lineTo(78, 120)
    plate.lineTo(40, 120)
    plate.lineTo(14, 90)
    plate.closeSubpath()

    fill = QLinearGradient(8, 4, 120, 124)
    fill.setColorAt(0.0, QColor("#7DF9FF"))
    fill.setColorAt(0.45, QColor("#22D3EE"))
    fill.setColorAt(1.0, QColor("#2563EB"))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill)
    painter.drawPath(plate)

    inner = QPainterPath()
    inner.moveTo(28, 36)
    inner.lineTo(48, 20)
    inner.lineTo(80, 20)
    inner.lineTo(100, 40)
    inner.lineTo(100, 72)
    inner.lineTo(72, 108)
    inner.lineTo(46, 108)
    inner.lineTo(28, 86)
    inner.closeSubpath()
    painter.setBrush(QColor("#07111F"))
    painter.drawPath(inner)

    # Stem plus a pulse wave that reads as a stylized P / heartbeat.
    pulse = QPainterPath()
    pulse.moveTo(44, 32)
    pulse.lineTo(58, 32)
    pulse.lineTo(58, 54)
    pulse.lineTo(70, 42)
    pulse.lineTo(80, 56)
    pulse.lineTo(90, 40)
    pulse.lineTo(104, 58)
    pulse.lineTo(90, 58)
    pulse.lineTo(80, 72)
    pulse.lineTo(70, 58)
    pulse.lineTo(58, 72)
    pulse.lineTo(58, 96)
    pulse.lineTo(44, 96)
    pulse.closeSubpath()

    core = QLinearGradient(24, 20, 96, 108)
    core.setColorAt(0.0, QColor("#E8FBFF"))
    core.setColorAt(1.0, QColor("#38BDF8"))
    painter.setBrush(core)
    painter.drawPath(pulse)
    painter.restore()


def render_logo_pixmap(size: int = 256) -> QPixmap:
    """Rasterize the vector mark for the window icon and PNG asset."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    paint_pulse_mark(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def save_logo_png(path: Path | None = None) -> Path:
    """Write assets/logo.png next to the SVG so the app never fetches art online."""
    target = path or (ASSETS_DIR / "logo.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    render_logo_pixmap(256).save(str(target), "PNG")
    return target


def logo_icon() -> QIcon:
    return QIcon(render_logo_pixmap(128))


def draw_line_icon(painter: QPainter, kind: str, rect: QRectF, color: QColor) -> None:
    """Simple geometric icons. kind is a short name such as 'home' or 'cpu'."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    if kind == "home":
        painter.drawLine(QPointF(x + w * 0.15, y + h * 0.5),
                         QPointF(x + w * 0.5, y + h * 0.18))
        painter.drawLine(QPointF(x + w * 0.5, y + h * 0.18),
                         QPointF(x + w * 0.85, y + h * 0.5))
        painter.drawRect(
            QRectF(x + w * 0.28, y + h * 0.48, w * 0.44, h * 0.36))
    elif kind == "chart":
        painter.drawLine(QPointF(x + w * 0.15, y + h * 0.8),
                         QPointF(x + w * 0.85, y + h * 0.8))
        path = QPainterPath()
        path.moveTo(x + w * 0.2, y + h * 0.62)
        path.lineTo(x + w * 0.38, y + h * 0.4)
        path.lineTo(x + w * 0.55, y + h * 0.52)
        path.lineTo(x + w * 0.8, y + h * 0.22)
        painter.drawPath(path)
    elif kind == "cpu":
        painter.drawRoundedRect(
            QRectF(x + w * 0.28, y + h * 0.28, w * 0.44, h * 0.44), 2, 2)
        for t in (0.38, 0.5, 0.62):
            painter.drawLine(QPointF(x + w * t, y + h * 0.16),
                             QPointF(x + w * t, y + h * 0.28))
            painter.drawLine(QPointF(x + w * t, y + h * 0.72),
                             QPointF(x + w * t, y + h * 0.84))
            painter.drawLine(QPointF(x + w * 0.16, y + h * t),
                             QPointF(x + w * 0.28, y + h * t))
            painter.drawLine(QPointF(x + w * 0.72, y + h * t),
                             QPointF(x + w * 0.84, y + h * t))
    elif kind == "game":
        painter.drawRoundedRect(
            QRectF(x + w * 0.12, y + h * 0.32, w * 0.76, h * 0.4), 8, 8)
        painter.drawLine(QPointF(x + w * 0.32, y + h * 0.44),
                         QPointF(x + w * 0.32, y + h * 0.6))
        painter.drawLine(QPointF(x + w * 0.24, y + h * 0.52),
                         QPointF(x + w * 0.4, y + h * 0.52))
        painter.drawEllipse(
            QRectF(x + w * 0.62, y + h * 0.42, w * 0.1, h * 0.1))
        painter.drawEllipse(
            QRectF(x + w * 0.72, y + h * 0.52, w * 0.1, h * 0.1))
    elif kind == "clock":
        painter.drawEllipse(rect.adjusted(2, 2, -2, -2))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(
            rect.center().x(), y + h * 0.32))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(
            x + w * 0.7, y + h * 0.55))
    elif kind == "file":
        path = QPainterPath()
        path.moveTo(x + w * 0.3, y + h * 0.16)
        path.lineTo(x + w * 0.58, y + h * 0.16)
        path.lineTo(x + w * 0.74, y + h * 0.34)
        path.lineTo(x + w * 0.74, y + h * 0.84)
        path.lineTo(x + w * 0.3, y + h * 0.84)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.58, y + h * 0.16),
                         QPointF(x + w * 0.58, y + h * 0.34))
        painter.drawLine(QPointF(x + w * 0.58, y + h * 0.34),
                         QPointF(x + w * 0.74, y + h * 0.34))
    elif kind == "ram":
        painter.drawRoundedRect(
            QRectF(x + w * 0.16, y + h * 0.3, w * 0.68, h * 0.4), 3, 3)
        painter.drawRect(
            QRectF(x + w * 0.28, y + h * 0.38, w * 0.12, h * 0.24))
        painter.drawRect(
            QRectF(x + w * 0.46, y + h * 0.38, w * 0.12, h * 0.24))
        painter.drawRect(
            QRectF(x + w * 0.64, y + h * 0.38, w * 0.08, h * 0.24))
    elif kind == "disk":
        painter.drawRoundedRect(
            QRectF(x + w * 0.18, y + h * 0.28, w * 0.64, h * 0.46), 4, 4)
        painter.drawLine(QPointF(x + w * 0.18, y + h * 0.42),
                         QPointF(x + w * 0.82, y + h * 0.42))
        painter.drawEllipse(
            QRectF(x + w * 0.28, y + h * 0.5, w * 0.1, h * 0.1))
    elif kind == "monitor":
        painter.drawRoundedRect(
            QRectF(x + w * 0.14, y + h * 0.2, w * 0.72, h * 0.48), 2, 2)
        painter.drawLine(QPointF(x + w * 0.5, y + h * 0.68),
                         QPointF(x + w * 0.5, y + h * 0.78))
        painter.drawLine(QPointF(x + w * 0.32, y + h * 0.8),
                         QPointF(x + w * 0.68, y + h * 0.8))
    else:
        painter.drawEllipse(rect.adjusted(3, 3, -3, -3))

    painter.restore()


class LogoMark(QWidget):
    """Sidebar / header mark painted from the same vector path as the SVG."""

    def __init__(self, size: int = 44, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        glow = QRadialGradient(
            self.width() / 2, self.height() / 2, self.width() / 2)
        glow.setColorAt(0.0, QColor(34, 224, 255, 70))
        glow.setColorAt(1.0, QColor(34, 224, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(self.rect())
        paint_pulse_mark(painter, QRectF(
            2, 2, self.width() - 4, self.height() - 4))


class CircularGauge(QWidget):
    """
    Arc gauge for a 0-100 percentage.

    Qt drawArc uses 1/16th of a degree. 0 is 3 o'clock, and positive
    values travel counter-clockwise. We start at 240 degrees and sweep
    300 degrees so the opening sits at the bottom, like a speedometer.
    """

    def __init__(self, accent: str = "cyan", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._percent: float | None = None
        self._accent = accent
        self._caption = "Usage"
        self.setMinimumSize(118, 118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(150, 150)

    def set_value(self, percent: float | None) -> None:
        self._percent = percent
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        side = min(self.width(), self.height())
        pad = 10
        rect = QRectF((self.width() - side) / 2 + pad, (self.height() -
                      side) / 2 + pad, side - pad * 2, side - pad * 2)

        if self._accent == "violet":
            start_color, end_color = VIOLET, VIOLET_DEEP
        else:
            start_color, end_color = CYAN, BLUE

        track = QColor(255, 255, 255, 22)
        pen = QPen(track, 10)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # Background track: almost a full ring with a gap at the bottom.
        painter.drawArc(rect, 240 * 16, -300 * 16)

        if self._percent is None:
            value_text = "—"
        else:
            bounded = max(0.0, min(100.0, self._percent))
            span = -300 * 16 * (bounded / 100.0)
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, start_color)
            gradient.setColorAt(1.0, end_color)
            value_pen = QPen(QColor(start_color))
            value_pen.setWidth(10)
            value_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            # Soft outer glow, then the solid value arc.
            glow = QPen(QColor(start_color.red(),
                        start_color.green(), start_color.blue(), 70), 16)
            glow.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(glow)
            painter.drawArc(rect, 240 * 16, int(span))
            painter.setPen(value_pen)
            painter.drawArc(rect, 240 * 16, int(span))
            value_text = f"{self._percent:.1f}%"

        painter.setPen(TEXT)
        font = QFont(self.font())
        font.setPixelSize(max(16, int(side * 0.16)))
        font.setBold(True)
        painter.setFont(font)
        text_rect = rect.adjusted(8, 8, -8, -8)
        painter.drawText(
            text_rect.adjusted(0, -int(side * 0.06), 0, -int(side * 0.06)),
            Qt.AlignmentFlag.AlignCenter,
            value_text,
        )

        caption_font = QFont(self.font())
        caption_font.setPixelSize(max(9, int(side * 0.075)))
        caption_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(caption_font)
        painter.setPen(MUTED)
        painter.drawText(
            QRectF(rect.x(), rect.center().y() +
                   side * 0.08, rect.width(), 18),
            Qt.AlignmentFlag.AlignHCenter,
            self._caption if self._percent is not None else "",
        )


class Sparkline(QWidget):
    """Tiny CPU trend chart drawn only from real samples collected by the timer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._samples: deque[float] = deque(maxlen=36)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def add_sample(self, value: float) -> None:
        self._samples.append(max(0.0, min(100.0, value)))
        self.update()

    def clear_samples(self) -> None:
        self._samples.clear()
        self.update()

    def has_trend(self) -> bool:
        return len(self._samples) >= 2

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if len(self._samples) < 2:
            return

        rect = QRectF(self.rect()).adjusted(4, 6, -4, -6)
        values = list(self._samples)
        step = rect.width() / (len(values) - 1)
        path = QPainterPath()
        points: list[QPointF] = []
        for index, value in enumerate(values):
            x = rect.x() + step * index
            y = rect.bottom() - (value / 100.0) * rect.height()
            point = QPointF(x, y)
            points.append(point)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)

        fill = QPainterPath(path)
        fill.lineTo(points[-1].x(), rect.bottom())
        fill.lineTo(points[0].x(), rect.bottom())
        fill.closeSubpath()
        shade = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        shade.setColorAt(0.0, QColor(34, 224, 255, 70))
        shade.setColorAt(1.0, QColor(34, 224, 255, 0))
        painter.fillPath(fill, shade)

        glow = QPen(QColor(34, 224, 255, 70), 5)
        glow.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(glow)
        painter.drawPath(path)
        pen = QPen(CYAN, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)


class GradientBar(QWidget):
    """Horizontal usage bar. percent is None when the reading failed."""

    def __init__(self, accent: str = "cyan", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._percent: float | None = None
        self._accent = accent
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def set_value(self, percent: float | None) -> None:
        self._percent = percent
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 4, 4)
        painter.fillPath(path, QColor(8, 16, 30))

        if self._percent is None:
            return

        width = rect.width() * max(0.0, min(100.0, self._percent)) / 100.0
        fill_rect = QRectF(rect.x(), rect.y(), max(width, 0.0), rect.height())
        gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
        if self._accent == "violet":
            gradient.setColorAt(0.0, VIOLET_DEEP)
            gradient.setColorAt(1.0, VIOLET)
        else:
            gradient.setColorAt(0.0, BLUE)
            gradient.setColorAt(1.0, CYAN)
        fill_path = QPainterPath()
        fill_path.addRoundedRect(fill_rect, 4, 4)
        painter.fillPath(fill_path, gradient)


class NavButton(QPushButton):
    """Sidebar destination with a drawn icon and an optional Coming soon mark."""

    def __init__(self, label: str, icon_kind: str, coming_soon: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._icon_kind = icon_kind
        self._coming_soon = coming_soon
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = angular_path(rect, cut=8)

        if self.isChecked():
            painter.fillPath(path, QColor(20, 70, 110, 160))
            draw_glow_path(painter, path, CYAN, width=1.2)
        elif self.underMouse():
            painter.fillPath(path, QColor(16, 36, 58, 160))
            painter.setPen(QPen(QColor(34, 224, 255, 90), 1))
            painter.drawPath(path)

        color = TEXT if self.isChecked() or self.underMouse() else MUTED
        icon_rect = QRectF(12, (self.height() - 18) / 2, 18, 18)
        draw_line_icon(painter, self._icon_kind, icon_rect, color)

        painter.setPen(color)
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setBold(self.isChecked())
        painter.setFont(font)
        painter.drawText(QRect(36, 0, self.width() - 78, self.height()),
                         Qt.AlignmentFlag.AlignVCenter, self._label)

        if self._coming_soon:
            painter.setPen(QColor(139, 163, 193, 180))
            small = QFont(self.font())
            small.setPixelSize(8)
            small.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
            painter.setFont(small)
            painter.drawText(
                QRect(self.width() - 46, 0, 40, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                "SOON",
            )


class MetricCard(QFrame):
    """One live measurement card: icon, circular gauge, facts, and optional trend."""

    def __init__(self, title: str, subtitle: str, icon_kind: str, accent: str = "cyan", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._accent = accent
        self._hover = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(250)
        self.setMinimumHeight(250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.icon_kind = icon_kind
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("cardSubtitle")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        header.addSpacing(26)
        header.addLayout(titles)
        header.addStretch(1)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(8)
        self.gauge = CircularGauge(accent=accent)
        self.stat_primary_name = QLabel("")
        self.stat_primary_name.setObjectName("statName")
        self.stat_primary_value = QLabel("—")
        self.stat_primary_value.setObjectName("statValue")
        self.stat_secondary_name = QLabel("")
        self.stat_secondary_name.setObjectName("statName")
        self.stat_secondary_value = QLabel("—")
        self.stat_secondary_value.setObjectName("statValue")
        stats = QVBoxLayout()
        stats.setSpacing(4)
        stats.addStretch(1)
        stats.addWidget(self.stat_primary_name)
        stats.addWidget(self.stat_primary_value)
        stats.addSpacing(10)
        stats.addWidget(self.stat_secondary_name)
        stats.addWidget(self.stat_secondary_value)
        stats.addStretch(1)
        body.addWidget(self.gauge, stretch=3)
        body.addLayout(stats, stretch=2)
        layout.addLayout(body, stretch=1)

        self.message_label = QLabel("")
        self.message_label.setObjectName("cardError")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        self.extra_details = QLabel("")
        self.extra_details.setObjectName("statName")
        self.extra_details.setWordWrap(True)
        self.extra_details.hide()
        layout.addWidget(self.extra_details)

        self.sparkline = Sparkline()
        self.bar = GradientBar(accent=accent)
        layout.addWidget(self.sparkline)
        layout.addWidget(self.bar)
        self.sparkline.hide()

    def event(self, event):
        if event.type() == QEvent.Type.HoverEnter:
            self._hover = True
            self.update()
        elif event.type() == QEvent.Type.HoverLeave:
            self._hover = False
            self.update()
        return super().event(event)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        path = angular_path(rect, cut=16)
        fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
        fill.setColorAt(0.0, QColor(10, 24, 42, 230))
        fill.setColorAt(1.0, QColor(7, 16, 32, 230))
        painter.fillPath(path, fill)
        accent = VIOLET if self._accent == "violet" else CYAN
        draw_glow_path(painter, path, accent if self._hover else QColor(
            accent.red(), accent.green(), accent.blue(), 170), width=1.3)

        # Tiny header icon in the card's own paint so it stays aligned with the glow.
        draw_line_icon(painter, self.icon_kind, QRectF(18, 20, 18, 18), accent)

    def show_ok(self, percent: float, primary_name: str, primary_value: str, secondary_name: str, secondary_value: str) -> None:
        self.gauge.set_value(percent)
        self.bar.set_value(percent)
        self.stat_primary_name.setText(primary_name)
        self.stat_primary_value.setText(primary_value)
        self.stat_secondary_name.setText(secondary_name)
        self.stat_secondary_value.setText(secondary_value)
        self.message_label.hide()
        self.bar.show()

    def set_extra_details(self, details: str) -> None:
        self.extra_details.setText(details)
        self.extra_details.setVisible(bool(details))

    def show_unavailable(self, message: str) -> None:
        self.gauge.set_value(None)
        self.bar.set_value(None)
        self.stat_primary_name.setText("")
        self.stat_primary_value.setText("—")
        self.stat_secondary_name.setText("")
        self.stat_secondary_value.setText("—")
        self.message_label.setText(message)
        self.message_label.show()
        self.extra_details.hide()
        self.sparkline.hide()
        self.sparkline.clear_samples()

    def set_title(self, title: str, subtitle: str) -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)


class DiagnosticFindingCard(QFrame):
    """Evidence-first finding styled to match Pulse's angular metric panels."""

    def __init__(self, finding: Finding, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel(finding.title)
        title.setObjectName("findingTitle")
        title.setWordWrap(True)
        priority = QLabel(f"PRIORITY {finding.priority}")
        priority.setObjectName("findingPriority")
        header.addWidget(title, stretch=1)
        header.addWidget(priority, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        metadata = QLabel(
            f"{finding.component.upper()}  /  CONFIDENCE {finding.confidence.upper()}"
        )
        metadata.setObjectName("findingMeta")
        layout.addWidget(metadata)
        self._add_detail(layout, "OBSERVED FACT", finding.observed)
        self._add_detail(layout, "WHY IT MAY MATTER", finding.why_it_matters)
        self._add_detail(layout, "SAFE NEXT ACTION", finding.next_action)
        self._add_detail(layout, "VERIFY", finding.verification)

    @staticmethod
    def _add_detail(layout: QVBoxLayout, heading: str, text: str) -> None:
        label = QLabel(f"{heading}  {text}")
        label.setObjectName("findingBody")
        label.setWordWrap(True)
        layout.addWidget(label)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = angular_path(rect, cut=12)
        painter.fillPath(path, QColor(8, 20, 36, 235))
        draw_glow_path(painter, path, QColor(34, 224, 255, 150), width=1.0)


class BottleneckDetectivePanel(QWidget):
    """Live diagnostic report view; findings remain separate from raw metrics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 8, 8)
        layout.setSpacing(12)

        self.assessment = QLabel("Insufficient data")
        self.assessment.setObjectName("diagnosticAssessment")
        self.assessment.setWordWrap(True)
        self.evidence_window = QLabel("Waiting for live measurements.")
        self.evidence_window.setObjectName("diagnosticEvidence")
        self.evidence_window.setWordWrap(True)
        self.rule_note = QLabel(
            "Rules use rolling observations, not a score. System-wide utilization "
            "does not prove which application or component limits a task."
        )
        self.rule_note.setObjectName("diagnosticNote")
        self.rule_note.setWordWrap(True)

        layout.addWidget(self.assessment)
        layout.addWidget(self.evidence_window)
        layout.addWidget(self.rule_note)

        self.findings_layout = QVBoxLayout()
        self.findings_layout.setSpacing(10)
        layout.addLayout(self.findings_layout)

        self.limitations = QLabel("")
        self.limitations.setObjectName("diagnosticLimitations")
        self.limitations.setWordWrap(True)
        layout.addWidget(self.limitations)
        layout.addStretch(1)

    def set_report(self, report: DiagnosticReport) -> None:
        self.assessment.setText(report.assessment)
        self.evidence_window.setText(report.evidence_window)
        while self.findings_layout.count():
            item = self.findings_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if report.findings:
            for finding in report.findings:
                self.findings_layout.addWidget(DiagnosticFindingCard(finding))
        else:
            empty = QLabel(
                "No sustained findings from the measurements available so far. "
                "Continue monitoring during the workload that feels slow."
            )
            empty.setObjectName("diagnosticEvidence")
            empty.setWordWrap(True)
            self.findings_layout.addWidget(empty)

        self.limitations.setText(
            "DATA LIMITS  " + "  ·  ".join(report.limitations))


class StorageDriveCard(QFrame):
    """Drive health facts from smartctl, with reported and Pulse text separated."""

    def __init__(self, drive: StorageDrive, number: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel(f"DRIVE {number}  /  {drive.model}")
        title.setObjectName("storageTitle")
        title.setWordWrap(True)
        health = QLabel(f"SMART {drive.health_status.upper()}")
        health.setObjectName("storageHealth")
        header.addWidget(title, stretch=1)
        header.addWidget(health, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        facts = [
            f"Type / interface: {drive.drive_type} / {drive.interface}",
            f"Capacity: {_format_storage_capacity(drive.capacity_bytes)}",
            f"Temperature: {drive.temperature_c} °C" if drive.temperature_c is not None else "Temperature: Unavailable",
            f"Pulse interpretation: {drive.health_interpretation}",
        ]
        if drive.drive_type.startswith("NVMe"):
            facts.extend((
                f"Percentage used: {drive.percentage_used}%" if drive.percentage_used is not None else "Percentage used: Unsupported",
                f"Available spare: {drive.available_spare_percent}%" if drive.available_spare_percent is not None else "Available spare: Unsupported",
                f"Critical warnings: {drive.critical_warning}" if drive.critical_warning is not None else "Critical warnings: Unsupported",
                f"Power-on hours: {drive.power_on_hours}" if drive.power_on_hours is not None else "Power-on hours: Unsupported",
                f"Total host writes: {drive.host_writes}" if drive.host_writes is not None else "Total host writes: Unsupported",
            ))
        if drive.attributes:
            facts.extend(
                f"SMART attribute: {name}: {value}" for name, value in drive.attributes)
        elif drive.drive_type.startswith("SATA"):
            facts.append(
                "SMART attributes: Unsupported (drive-specific raw values are not safely interpreted)"
            )
        for fact in facts:
            label = QLabel(fact)
            label.setObjectName("storageFact")
            label.setWordWrap(True)
            layout.addWidget(label)
        if drive.message:
            message = QLabel(drive.message)
            message.setObjectName("storageMessage")
            message.setWordWrap(True)
            layout.addWidget(message)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = angular_path(rect, cut=12)
        painter.fillPath(path, QColor(8, 20, 36, 235))
        draw_glow_path(painter, path, QColor(34, 224, 255, 150), width=1.0)


def _format_storage_capacity(capacity_bytes: int | None) -> str:
    if capacity_bytes is None:
        return "Unavailable"
    return f"{capacity_bytes / 1_000_000_000:.1f} GB"


class StorageHealthPanel(QWidget):
    """Manually refreshed SMART drive report shown in the Storage Health page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 8, 8)
        layout.setSpacing(12)

        self.status = QLabel("Storage health has not been checked yet.")
        self.status.setObjectName("diagnosticEvidence")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.drive_layout = QVBoxLayout()
        self.drive_layout.setSpacing(10)
        layout.addLayout(self.drive_layout)
        layout.addStretch(1)

    def set_scan(self, scan: StorageScan) -> None:
        while self.drive_layout.count():
            item = self.drive_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not scan.available:
            self.status.setText(scan.message or "smartctl is unavailable.")
        elif scan.drives:
            self.status.setText(
                f"Read-only SMART report for {len(scan.drives)} detected drive(s). "
                "SMART status below is reported by each drive; Pulse interpretation is separate."
            )
            for index, drive in enumerate(scan.drives, start=1):
                self.drive_layout.addWidget(StorageDriveCard(drive, index))
            if scan.message:
                self.status.setText(f"{self.status.text()} {scan.message}")
        else:
            self.status.setText(
                scan.message or "No storage drives were reported by smartctl.")


class InfoChip(QFrame):
    """Small fact chip used in the System Overview panel."""

    def __init__(self, icon_kind: str, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.icon_kind = icon_kind
        self.setObjectName("infoChip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(58)
        self.setMinimumWidth(118)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 8, 12, 8)
        layout.setSpacing(0)
        self.caption = QLabel(caption)
        self.caption.setObjectName("chipCaption")
        self.value = QLabel("—")
        self.value.setObjectName("chipValue")
        layout.addWidget(self.caption)
        layout.addWidget(self.value)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        draw_line_icon(painter, self.icon_kind, QRectF(12, 20, 16, 16), CYAN)


class SystemOverviewPanel(QFrame):
    """
    Wide lower panel with an original painted cosmic landscape.

    Overlay labels always show facts from live readings. The artwork is
    decoration only and never pretends to be a sensor value.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("systemOverview")
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 22, 16)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        self.title_label = QLabel("  System Overview")
        self.title_label.setObjectName("overviewTitle")
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        layout.addLayout(title_row)
        layout.addStretch(1)

        self.status_title = QLabel("Waiting for readings")
        self.status_title.setObjectName("overviewStatus")
        self.status_title.setWordWrap(True)
        self.status_body = QLabel(
            "CPU, RAM, and disk values appear here after the first successful measurement.")
        self.status_body.setObjectName("overviewBody")
        self.status_body.setWordWrap(True)
        layout.addWidget(self.status_title)
        layout.addWidget(self.status_body)
        layout.addStretch(1)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        chips.addStretch(1)
        self.core_chip = InfoChip("cpu", "CPU Cores")
        self.logical_chip = InfoChip("cpu", "Logical Processors")
        self.os_chip = InfoChip("monitor", "System")
        chips.addWidget(self.core_chip)
        chips.addWidget(self.logical_chip)
        chips.addWidget(self.os_chip)
        layout.addLayout(chips)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        clip = angular_path(rect, cut=18)
        painter.setClipPath(clip)

        sky = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        sky.setColorAt(0.0, QColor(6, 16, 36))
        sky.setColorAt(0.45, QColor(8, 28, 58))
        sky.setColorAt(1.0, QColor(4, 10, 22))
        painter.fillPath(clip, sky)

        # Planet glow, upper right. Purely decorative.
        planet_center = QPointF(
            rect.right() - rect.width() * 0.16, rect.top() + rect.height() * 0.22)
        planet = QRadialGradient(planet_center, rect.height() * 0.55)
        planet.setColorAt(0.0, QColor(90, 170, 255, 90))
        planet.setColorAt(0.35, QColor(40, 90, 170, 50))
        planet.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(planet)
        painter.drawEllipse(planet_center, rect.height()
                            * 0.42, rect.height() * 0.42)
        painter.setBrush(QColor(70, 130, 190, 80))
        painter.drawEllipse(planet_center, rect.height()
                            * 0.18, rect.height() * 0.18)

        # Fixed star positions so they do not jump when the window resizes.
        painter.setBrush(QColor(200, 230, 255, 180))
        for fx, fy, size in (
            (0.08, 0.14, 2),
            (0.18, 0.08, 1.4),
            (0.27, 0.2, 1.6),
            (0.41, 0.11, 1.2),
            (0.55, 0.16, 1.8),
            (0.63, 0.07, 1.3),
            (0.72, 0.22, 1.5),
            (0.88, 0.12, 2.2),
            (0.93, 0.3, 1.4),
        ):
            painter.drawEllipse(QPointF(
                rect.x() + rect.width() * fx, rect.y() + rect.height() * fy), size, size)

        def mountain(points: list[tuple[float, float]], color: QColor) -> None:
            path = QPainterPath()
            path.moveTo(rect.x() + rect.width() *
                        points[0][0], rect.y() + rect.height() * points[0][1])
            for px, py in points[1:]:
                path.lineTo(rect.x() + rect.width() * px,
                            rect.y() + rect.height() * py)
            path.closeSubpath()
            painter.fillPath(path, color)

        mountain(
            [(0.0, 1.0), (0.0, 0.72), (0.12, 0.5), (0.22, 0.62), (0.34, 0.4),
             (0.48, 0.58), (0.62, 0.36), (0.78, 0.55), (1.0, 0.42), (1.0, 1.0)],
            QColor(12, 28, 52, 220),
        )
        mountain(
            [(0.0, 1.0), (0.0, 0.82), (0.16, 0.64), (0.3, 0.78),
             (0.46, 0.58), (0.6, 0.74), (0.76, 0.56), (1.0, 0.7), (1.0, 1.0)],
            QColor(8, 20, 38, 230),
        )

        ridge = QPainterPath()
        ridge.moveTo(rect.x(), rect.y() + rect.height() * 0.72)
        ridge.lineTo(rect.x() + rect.width() * 0.12,
                     rect.y() + rect.height() * 0.5)
        ridge.lineTo(rect.x() + rect.width() * 0.34,
                     rect.y() + rect.height() * 0.4)
        ridge.lineTo(rect.x() + rect.width() * 0.62,
                     rect.y() + rect.height() * 0.36)
        painter.setPen(QPen(QColor(34, 224, 255, 90), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(ridge)

        painter.setClipping(False)
        draw_glow_path(painter, clip, CYAN, width=1.2)
        draw_line_icon(painter, "chart", QRectF(
            rect.x() + 22, rect.y() + 20, 16, 16), CYAN)
