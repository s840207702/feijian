import sys
import os
import webbrowser
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QTabBar, QFileDialog, QProgressBar, QMessageBox
from PyQt5.QtGui import QFont, QIcon, QCursor
from PyQt5.QtCore import Qt, pyqtSignal, QThreadPool
from image_base64 import get_icon_pixmap
from split_tab import create_split_tab, SplitTask
from montage_tab import create_montage_tab, MontageSignals, DurationCalculationTask, MontageTask


class CustomTabBar(QTabBar):
    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        size.setWidth(self.parent().width() // self.count())
        return size

class VideoEditorApp(QMainWindow):
    process_completed = pyqtSignal(str)
    progress_update = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setFixedSize(500, 500)
        self.setWindowTitle('非丨剪1.0')
        self.setWindowIcon(QIcon(get_icon_pixmap()))

        self.setFont(QFont('微软雅黑', 10))
        self.threadpool = QThreadPool()
        self.signals = MontageSignals()
        self.signals.duration_calculated.connect(self.update_duration_label)
        self.process_completed.connect(self.show_completion_message)
        self.progress_update.connect(self.update_progress)

        cursor_pos = QCursor.pos()
        self.move(cursor_pos.x() - self.width() // 2, cursor_pos.y() - self.height() // 2)

        self.initUI()

    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")
        self.progress_bar.setAlignment(Qt.AlignRight)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                font: bold 14px '微软雅黑';
                color: black;
            }
            QProgressBar::chunk {
                background-color: #6200EE;
                width: 20px;
                margin: 0.5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        tabs = QTabWidget(self)
        custom_tab_bar = CustomTabBar(tabs)
        tabs.setTabBar(custom_tab_bar)
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border-top: 2px solid #6200EE;
                background: #FFFFFF;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #F5F5F5;
                padding: 16px 12px;  /* 增加上下内边距为16px，左右为12px */
                min-height: 18px;    /* 设置最小高度为20px，根据需要调整 */
                font: bold 18px '微软雅黑';  /* Tab上的字号显示大小 */
                margin-right: 2px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                font-family: '微软雅黑';
            }
            QTabBar::tab:selected {
                background: #6200EE;
                color: white;
                border: 1px solid #6200EE;
            }
        """)

        tabs.addTab(create_split_tab(self), "分割")
        tabs.addTab(create_montage_tab(self), "混剪")
        layout.addWidget(tabs)

    def browse_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        if folder_path:
            self.folder_input.setText(folder_path)

    def browse_export_folder(self):
        export_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if export_path:
            self.export_input.setText(export_path)

    def start_splitting(self):
        self.reset_progress_bar()
        folder_path = self.folder_input.text()
        export_path = self.export_input.text()
        min_duration = self.duration_min.text()
        max_duration = self.duration_max.text()

        if not folder_path or not export_path or not min_duration or not max_duration:
            QMessageBox.warning(self, "警告", "请填写所有必要的参数！")
            return

        try:
            min_duration = int(min_duration)
            max_duration = int(max_duration)
        except ValueError:
            QMessageBox.warning(self, "警告", "时长区间必须为整数！")
            return

        task = SplitTask(folder_path, export_path, min_duration, max_duration)
        task.signals.completed.connect(self.show_completion_message)
        task.signals.progress.connect(self.update_progress)  # 确保连接了进度信号
        self.threadpool.start(task)

    def browse_folder_montage(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        if folder_path:
            self.folder_input_montage.setText(folder_path)
            self.start_duration_calculation_task(folder_path)

    def browse_export_folder_montage(self):
        export_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if export_path:
            self.export_input_montage.setText(export_path)

    def handle_input_dropped(self, folder_path):
        self.folder_input_deduplication.setText(folder_path)

    def handle_output_dropped(self, folder_path):
        self.export_input_deduplication.setText(folder_path)

    def start_montage(self):
        try:
            self.reset_progress_bar()
            folder_path = self.folder_input_montage.text()
            export_path = self.export_input_montage.text()
            duration = self.duration_input_montage.text()

            if not folder_path or not export_path or not duration:
                QMessageBox.warning(self, "警告", "请填写所有的合成参数！")
                return

            try:
                target_duration = float(duration)
            except ValueError:
                QMessageBox.warning(self, "警告", "合成时长必须为数字！")
                return

            # 使用最新的控件名称和逻辑
            order = "顺序合成" if self.sequential_radio.isChecked() else "乱序合成"
            mute = self.mute_checkbox.isChecked()

            task = MontageTask(folder_path, export_path, order, target_duration, mute)
            task.signals.completed.connect(self.show_completion_message)
            task.signals.progress.connect(self.update_progress)
            task.signals.error.connect(self.show_error_message)
            self.threadpool.start(task)
        except Exception as e:
            print(f"An error occurred in start_montage: {e}")
            self.show_error_message(f"发生错误：{e}")

    def show_error_message(self, message):
        QMessageBox.critical(self, "错误", message)

    def show_completion_message(self, output_folder):
        webbrowser.open(output_folder)

    def reset_progress_bar(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")

    def update_progress(self, value):
        # 在主线程中更新进度条
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{value}%")

    def show_completion_message(self, output_folder):
        webbrowser.open(output_folder)

    def load_folder_details(self, folder_path):
        if not os.path.isdir(folder_path):
            return
        total_duration = 0
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.3gp', '.flv', '.wmv', '.mpeg', '.mpg')
        for video_file in os.listdir(folder_path):
            if video_file.lower().endswith(video_extensions):
                video_path = os.path.join(folder_path, video_file)
                total_duration += self.get_video_duration(video_path)
        self.total_duration_label.setText(f"总时长：{int(total_duration)}秒")
        self.total_duration = total_duration

    def handle_input_dropped(self, folder_path):
        self.folder_input_montage.setText(folder_path)
        self.start_duration_calculation_task(folder_path)

    def handle_output_dropped(self, folder_path):
        self.export_input_montage.setText(folder_path)

    def start_duration_calculation_task(self, folder_path):
        duration_task = DurationCalculationTask(folder_path, self.signals)
        self.threadpool.start(duration_task)

    def update_duration_label(self, duration):
        self.total_duration_label.setText(f"总时长：{int(duration)}秒")
        self.total_duration = duration

    def calculate_video_count(self):
        if hasattr(self, 'total_duration') and self.total_duration > 0:
            try:
                desired_duration = float(self.duration_input_montage.text())
                if desired_duration > 0:
                    video_count = self.total_duration / desired_duration
                    self.video_count_label.setText(f"可合成的视频数量：{int(video_count)}")
                else:
                    self.video_count_label.setText("可合成的视频数量：0")
            except ValueError:
                self.video_count_label.setText("可合成的视频数量：0")
        else:
            self.video_count_label.setText("总时长无效")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = None
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWin = VideoEditorApp()
    mainWin.show()
    sys.exit(app.exec_())
