from __future__ import annotations


APP_STYLE = """
QWidget {{
    color: {text_color};
    font-family: "Segoe UI", "Microsoft YaHei UI", "Yu Gothic UI", sans-serif;
    font-size: 14px;
}}

#NavigationRail {{
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 10px;
}}

#ContentPanel {{
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-radius: 10px;
}}

#SeparatePage,
#SeparateContent,
#SlicerPage,
#SlicerContent,
QScrollArea#TransparentScrollArea,
QScrollArea#TransparentScrollArea > QWidget {{
    background: transparent;
}}

QScrollArea#TransparentScrollArea {{
    border: 0;
}}

#AppTitle {{
    font-size: 20px;
    font-weight: 700;
}}

#AppSubtitle,
#MutedText {{
    color: rgba(247, 249, 252, 0.72);
}}

#PageTitle {{
    font-size: 30px;
    font-weight: 700;
}}

#PageBody {{
    color: rgba(247, 249, 252, 0.78);
    font-size: 15px;
}}

#SectionTitle {{
    color: rgba(247, 249, 252, 0.82);
    font-size: 18px;
    font-weight: 700;
}}

#CardTitle {{
    font-size: 16px;
    font-weight: 700;
}}

#GlassCard {{
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
}}

QPushButton {{
    background: transparent;
    border: 0;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
}}

QPushButton:hover {{
    background: rgba(255, 255, 255, 0.10);
}}

QPushButton:checked {{
    background: rgba(255, 255, 255, 0.16);
}}

QPushButton#GlassButton,
QPushButton#PrimaryButton,
QPushButton#DangerButton,
QPushButton#IconTextButton,
QToolButton#IconButton,
QComboBox#LanguageCombo {{
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 6px;
    min-height: 34px;
    padding: 8px 12px;
}}

QPushButton#GlassButton:hover,
QToolButton#IconButton:hover,
QComboBox#LanguageCombo:hover {{
    background: rgba(255, 255, 255, 0.095);
}}

QComboBox#LanguageCombo::drop-down {{
    border: 0;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background: rgba(8, 12, 18, 0.84);
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 6px;
    padding: 4px;
    outline: 0;
    selection-background-color: rgba(255, 255, 255, 0.18);
    selection-color: {text_color};
}}

QComboBox QAbstractItemView::item {{
    min-height: 30px;
    padding: 6px 10px;
    border-radius: 5px;
}}

QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {{
    background: rgba(255, 255, 255, 0.16);
}}

QLineEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox {{
    background: rgba(255, 255, 255, 0.055);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 6px;
    min-height: 34px;
    padding: 8px 12px;
}}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus {{
    border: 1px solid rgba(255, 255, 255, 0.34);
}}

QPushButton#PrimaryButton {{
    background: rgba(74, 132, 255, 0.34);
}}

QPushButton#PrimaryButton:hover {{
    background: rgba(74, 132, 255, 0.62);
}}

QPushButton#DangerButton {{
    background: rgba(210, 65, 82, 0.30);
}}

QPushButton#DangerButton:hover {{
    background: rgba(210, 65, 82, 0.62);
}}

QPushButton#IconTextButton {{
    min-width: 28px;
    max-width: 28px;
    padding: 7px 4px;
    text-align: center;
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: rgba(255, 255, 255, 0.16);
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    width: 18px;
    margin: -6px 0;
    background: rgba(247, 249, 252, 0.92);
    border-radius: 9px;
}}

QCheckBox {{
    min-height: 34px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px 2px 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.22);
    border-radius: 5px;
    min-height: 36px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.34);
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
    border: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px 4px 2px 4px;
}}

QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.22);
    border-radius: 5px;
    min-width: 36px;
}}

QScrollBar::handle:horizontal:hover {{
    background: rgba(255, 255, 255, 0.34);
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: transparent;
    border: 0;
}}

QStatusBar {{
    color: rgba(247, 249, 252, 0.70);
}}
"""


def build_style(text_color: str = "#f7f9fc") -> str:
    return APP_STYLE.format(text_color=text_color)
