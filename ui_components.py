from PyQt5.QtWidgets import QPushButton, QLineEdit

class MaterialButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            MaterialButton {
                background-color: #6200EE;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-family: '微软雅黑';
                font-size: 14px;  /* 确保字体大小适中 */
                font-weight: normal;  /* 不加粗字体 */
            }
            MaterialButton:hover {
                background-color: #3700B3;
            }
            MaterialButton:pressed {
                background-color: #03DAC5;
            }
            MaterialButton:focus {
                outline: none;  /* 去除焦点虚线 */
            }
        """)
class MaterialLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            MaterialLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #F5F5F5;
                font-family: '微软雅黑';
            }
            MaterialLineEdit:focus {
                border-color: #6200EE;
            }
        """)
