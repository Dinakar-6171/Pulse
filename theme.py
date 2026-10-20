"""
PULSE visual theme.

This file only describes colors and widget styling.
It does not read CPU, RAM, or disk values.
Custom gauges and panel outlines are drawn in widgets.py.
"""

STYLESHEET = """
QMainWindow, QWidget#shell {
    background-color: #050910;
    color: #E8F4FF;
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
}

QWidget#ambient {
    background-color: #050910;
}

QWidget#sidebar {
    background-color: #061018;
    border-right: 1px solid #16324A;
}

QLabel#logoWord {
    color: #F4FBFF;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 4px;
}

QLabel#logoTag {
    color: #67E8F9;
    font-size: 9px;
    letter-spacing: 1.6px;
    font-weight: 700;
}

QLabel#sideTagline {
    color: #22E0FF;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.1px;
}

QWidget#content {
    background-color: transparent;
}

QWidget#headerBar {
    background-color: transparent;
}

QLabel#pageTitle {
    color: #F4FBFF;
    font-size: 26px;
    font-weight: 700;
}

QLabel#pageSubtitle {
    color: #8BA3C1;
    font-size: 12px;
}

QFrame#statusChip {
    background-color: rgba(10, 28, 48, 180);
    border: 1px solid #1D4E6E;
    border-radius: 4px;
}

QLabel#statusDot {
    color: #22E0FF;
    font-size: 12px;
}

QLabel#statusDot[state="warn"] {
    color: #FBBF24;
}

QLabel#statusDot[state="error"] {
    color: #F87171;
}

QLabel#statusTitle {
    color: #67E8F9;
    font-size: 11px;
    font-weight: 700;
}

QLabel#statusText {
    color: #C5D0E0;
    font-size: 10px;
}

QLabel#clockTime {
    color: #E8F4FF;
    font-size: 12px;
    font-weight: 700;
}

QLabel#clockDate {
    color: #8BA3C1;
    font-size: 10px;
}

QLabel#cardTitle, QLabel#cardSubtitle, QLabel#statName, QLabel#statValue,
QLabel#overviewTitle, QLabel#overviewStatus, QLabel#overviewBody,
QLabel#chipCaption, QLabel#chipValue, QLabel#cardError {
    background: transparent;
}

QLabel#findingTitle {
    color: #F4FBFF;
    font-size: 15px;
    font-weight: 700;
}

QLabel#findingPriority {
    color: #67E8F9;
    font-size: 10px;
    font-weight: 700;
}

QLabel#findingMeta {
    color: #A78BFA;
    font-size: 10px;
    font-weight: 700;
}

QLabel#findingBody, QLabel#diagnosticEvidence, QLabel#diagnosticNote,
QLabel#diagnosticLimitations {
    color: #C5D0E0;
    font-size: 11px;
}

QLabel#diagnosticAssessment {
    color: #67E8F9;
    font-size: 22px;
    font-weight: 700;
}

QPushButton#storageRefreshButton {
    color: #E8F4FF;
    background-color: rgba(10, 28, 48, 210);
    border: 1px solid #22E0FF;
    padding: 8px 14px;
    font-size: 11px;
    font-weight: 700;
}

QPushButton#storageRefreshButton:hover:enabled {
    background-color: rgba(20, 70, 110, 220);
}

QPushButton#storageRefreshButton:disabled {
    color: #8BA3C1;
    border-color: #1D4E6E;
}

QLabel#storageTitle {
    color: #F4FBFF;
    font-size: 14px;
    font-weight: 700;
}

QLabel#storageHealth {
    color: #67E8F9;
    font-size: 10px;
    font-weight: 700;
}

QLabel#storageFact {
    color: #C5D0E0;
    font-size: 11px;
}

QLabel#storageMessage {
    color: #FBBF24;
    font-size: 11px;
}

QLabel#cardTitle {
    color: #F4FBFF;
    font-size: 15px;
    font-weight: 700;
}

QLabel#cardSubtitle {
    color: #8BA3C1;
    font-size: 11px;
}

QLabel#statName {
    color: #8BA3C1;
    font-size: 11px;
}

QLabel#statValue {
    color: #F4FBFF;
    font-size: 20px;
    font-weight: 700;
}

QLabel#cardError {
    color: #F87171;
    font-size: 12px;
}

QLabel#overviewTitle {
    color: #F4FBFF;
    font-size: 16px;
    font-weight: 700;
}

QLabel#overviewStatus {
    color: #F4FBFF;
    font-size: 22px;
    font-weight: 700;
}

QLabel#overviewBody {
    color: #C5D0E0;
    font-size: 13px;
}

QFrame#infoChip {
    background-color: rgba(8, 20, 36, 190);
    border: 1px solid #1D4E6E;
}

QLabel#chipCaption {
    color: #8BA3C1;
    font-size: 10px;
}

QLabel#chipValue {
    color: #F4FBFF;
    font-size: 15px;
    font-weight: 700;
}

QFrame#comingPanel {
    background-color: rgba(10, 24, 42, 230);
    border: 1px solid #1D4E6E;
}

QLabel#comingTitle {
    color: #F4FBFF;
    font-size: 20px;
    font-weight: 700;
}

QLabel#comingBody {
    color: #8BA3C1;
    font-size: 13px;
}

QLabel#footer {
    color: #6E7D94;
    font-size: 10px;
    letter-spacing: 1.6px;
}

QScrollArea {
    border: none;
    background: transparent;
}

QWidget#overviewInner {
    background-color: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #16324A;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 0;
}
"""
