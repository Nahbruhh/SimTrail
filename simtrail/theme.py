APP_STYLE = """
* { font-family: "Segoe UI"; font-size: 13px; color: #17243A; }
QMainWindow, QWidget#root { background: #F4F7FA; }
QFrame#sidebar { background: #142239; border: none; }
QLabel#brand { color: white; font-size: 21px; font-weight: 700; }
QLabel#brandDot { color: #29C7B5; font-size: 24px; font-weight: 800; }
QLabel#caption { color: #8290A5; font-size: 11px; letter-spacing: 1px; }
QPushButton#nav { text-align: left; padding: 11px 14px; border-radius: 7px; color: #AAB7CA; background: transparent; border: none; font-weight: 600; }
QPushButton#nav:hover { background: #1D304D; color: white; }
QPushButton#nav[active="true"] { background: #203853; color: white; border-left: 3px solid #29C7B5; }
QPushButton#nav:disabled { color: #53647D; background: transparent; border: none; }
QLabel#sideFoot { color: #8290A5; font-size: 11px; }
QFrame#topbar { background: white; border-bottom: 1px solid #E3E9EF; }
QLabel#title { font-size: 23px; font-weight: 700; color: #17243A; }
QLabel#subtitle { color: #708096; }
QPushButton { padding: 8px 14px; border-radius: 7px; border: 1px solid #D7E0E8; background: white; font-weight: 600; }
QPushButton:hover { border-color: #20B8A6; color: #168C81; }
QPushButton#primary { background: #20B8A6; color: white; border: none; }
QPushButton#primary:hover { background: #169F91; }
QPushButton#primary:disabled { background: #C9D4DC; color: white; border: none; }
QPushButton#secondary { background: #E8F8F5; color: #168C81; border: none; }
QPushButton#secondary:disabled { background: #EDF1F4; color: #A4AFBC; border: none; }
QPushButton#danger { background: #FDEFF1; color: #A43C4C; border: none; }
QPushButton#danger:hover { background: #F9DCE1; color: #8F293A; }
QPushButton:disabled { background: #EDF1F4; color: #A4AFBC; border-color: #E1E6EB; }
QMenu { background: #17243A; color: white; border: 1px solid #2A3B54; padding: 5px; }
QMenu::item { color: white; background: transparent; padding: 8px 24px; border-radius: 4px; }
QMenu::item:selected { color: white; background: #20B8A6; }
QMenu::separator { height: 1px; background: #3A4960; margin: 5px 8px; }
QFrame#card { background: white; border: 1px solid #E2E8EE; border-radius: 10px; }
QLabel#metric { font-size: 25px; font-weight: 700; }
QLabel#metricLabel { color: #718095; font-size: 12px; }
QLabel#metricHint { color: #19A291; font-size: 11px; }
QLineEdit, QComboBox, QTextEdit { min-height: 34px; padding: 0 10px; border: 1px solid #DCE3E9; border-radius: 7px; background: white; }
QTextEdit { padding: 7px; }
QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border: 1px solid #20B8A6; }
QTableWidget { background: white; border: none; gridline-color: #EDF1F4; selection-background-color: #E6F7F4; selection-color: #17243A; }
QTableWidget::item { padding: 9px 7px; border-bottom: 1px solid #EDF1F4; }
QHeaderView::section { background: #F7F9FB; color: #65758A; padding: 10px 7px; border: none; border-bottom: 1px solid #E2E8EE; font-size: 11px; font-weight: 700; }
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: #C7D1DB; border-radius: 4px; min-height: 28px; }
QDialog { background: #F4F7FA; }
QLabel#dialogTitle { font-size: 20px; font-weight: 700; }
QLabel#sectionTitle { font-size: 12px; font-weight: 700; color: #718095; }
QFrame#diffRow { background: white; border-bottom: 1px solid #E7ECF0; }
QLabel#before { color: #B04B5A; background: #FDEFF1; padding: 6px; border-radius: 4px; }
QLabel#after { color: #087E72; background: #E8F8F5; padding: 6px; border-radius: 4px; }
QStatusBar { background: white; color: #718095; border-top: 1px solid #E3E9EF; }
"""
