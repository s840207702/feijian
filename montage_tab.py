import math
import os
import sys
import ctypes
import tempfile
import random
import time
import subprocess
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QMessageBox, QFileDialog, \
    QRadioButton, QButtonGroup
from PyQt5.QtCore import QRunnable, pyqtSlot, QObject, pyqtSignal, QThreadPool
from PyQt5.QtGui import QFont
from ui_components import MaterialButton, MaterialLineEdit


if sys.platform == 'win32':
    no_window = subprocess.CREATE_NO_WINDOW
else:
    no_window = 0

class MontageSignals(QObject):
    completed = pyqtSignal(str)
    error = pyqtSignal(str)
    duration_calculated = pyqtSignal(float)
    progress = pyqtSignal(int)

class MontageTask(QRunnable):
    def __init__(self, folder_path, export_path, order, target_duration, mute=False):
        super().__init__()
        self.folder_path = folder_path
        self.export_path = export_path
        self.order = order
        self.target_duration = target_duration
        self.mute = mute
        self.signals = MontageSignals()

    def get_short_path_name(self, long_name):
        buffer = ctypes.create_unicode_buffer(512)
        ctypes.windll.kernel32.GetShortPathNameW(long_name, buffer, len(buffer))
        return buffer.value

    def process_with_ffmpeg(self, video_files, output_video_path):
        try:
            video_files = [os.path.abspath(video_file) for video_file in video_files]

            with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as f:
                for video_file in video_files:
                    f.write(f"file '{video_file}'\n")
                f.flush()

            command = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'concat', '-safe', '0', '-i', f.name,
                '-c:v', 'copy',
            ]

            if self.mute:
                command.extend(['-an'])
            else:
                command.extend(['-c:a', 'copy'])

            command.append(output_video_path)

            result = subprocess.run(command, check=True, creationflags=no_window)

            if result.returncode != 0:
                self.signals.error.emit(f"FFmpeg 返回非零退出状态：{result.returncode}")

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"FFmpeg 错误：{str(e)}")
        except Exception as e:
            self.signals.error.emit(f"发生错误：{str(e)}")

    @pyqtSlot()
    def run(self):
        try:
            video_files = []
            video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.3gp', '.flv', '.wmv', '.mpeg', '.mpg')
            for video_file in os.listdir(self.folder_path):
                if video_file.lower().endswith(video_extensions):
                    video_path = os.path.join(self.folder_path, video_file)
                    video_files.append(video_path)

            if self.order == "乱序合成":
                random.shuffle(video_files)

            # 获取所有视频的时长
            video_durations = []
            for video_file in video_files:
                duration = self.get_video_duration(video_file)
                video_durations.append((video_file, duration))

            # 根据目标时长分组
            groups = []
            current_group = []
            current_duration = 0.0
            for video_file, duration in video_durations:
                current_group.append(video_file)
                current_duration += duration
                if current_duration >= self.target_duration - 2:
                    groups.append(current_group)
                    current_group = []
                    current_duration = 0.0

            # 只有当current_duration达到目标时长时，才添加最后一组
            if current_group and current_duration >= self.target_duration - 2:
                groups.append(current_group)

            total_groups = len(groups)

            timestamp = time.strftime("%Y%m%d%H%M%S")
            output_folder = os.path.join(self.export_path, f"合成结果_{timestamp}")
            os.makedirs(output_folder, exist_ok=True)

            for idx, group in enumerate(groups):
                progress_percent = int((idx + 1) / total_groups * 100)
                self.signals.progress.emit(progress_percent)

                output_video_path = os.path.join(output_folder, f"montage_part_{idx + 1}_{timestamp}.mp4")
                self.process_with_ffmpeg(group, output_video_path)

            self.signals.completed.emit(output_folder)
        except Exception as e:
            self.signals.error.emit(str(e))

    def get_video_duration(self, video_path):
        command = ['ffprobe', '-v', 'error', '-show_entries',
                   'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=no_window)
        return float(process.stdout.decode().strip())


class DurationCalculationTask(QRunnable):
    def __init__(self, folder_path, signals):
        super().__init__()
        self.folder_path = folder_path
        self.signals = signals

    @pyqtSlot()
    def run(self):
        try:
            total_duration = self.calculate_total_duration()
            self.signals.duration_calculated.emit(total_duration)
        except Exception as e:
            self.signals.error.emit(str(e))

    def calculate_total_duration(self):
        total_duration = 0
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.3gp', '.flv', '.wmv', '.mpeg', '.mpg')
        for video_file in os.listdir(self.folder_path):
            if video_file.lower().endswith(video_extensions):
                video_path = os.path.join(self.folder_path, video_file)
                total_duration += self.get_video_duration(video_path)
        return total_duration

    def get_video_duration(self, video_path):
        command = ['ffprobe', '-v', 'error', '-show_entries',
                   'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=no_window)
        return float(process.stdout.decode().strip())


class MaterialLineEdit(QLineEdit):
    pathDropped = pyqtSignal(str)

    def __init__(self, parent=None, app_reference=None, target="input"):
        super().__init__(parent)
        self.app_reference = app_reference
        self.target = target
        self.setAcceptDrops(True)
        self.setFont(QFont('微软雅黑', 9))
        self.setStyleSheet("""
            MaterialLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #F5F5F5;
                font-family: '微软雅黑';
                font-size: 9pt;
            }
            MaterialLineEdit:focus {
                border-color: #6200EE;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                folder_path = urls[0].toLocalFile()
                if os.path.isdir(folder_path):
                    self.setText(folder_path)
                    self.pathDropped.emit(folder_path)
                    event.acceptProposedAction()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理文件夹时出错：{e}")

def create_montage_tab(parent):
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setSpacing(15)

    folder_label_layout = QHBoxLayout()
    folder_label = QLabel("导入文件夹：")
    folder_label_layout.addWidget(folder_label)
    parent.total_duration_label = QLabel("总时长：0秒")
    folder_label_layout.addWidget(parent.total_duration_label)
    layout.addLayout(folder_label_layout)

    folder_input_layout = QHBoxLayout()
    parent.folder_input_montage = MaterialLineEdit(parent=tab, app_reference=parent, target="input")
    parent.folder_input_montage.pathDropped.connect(parent.handle_input_dropped)
    folder_input_layout.addWidget(parent.folder_input_montage)

    browse_button = MaterialButton("选择")
    browse_button.clicked.connect(parent.browse_folder_montage)
    folder_input_layout.addWidget(browse_button)
    layout.addLayout(folder_input_layout)

    export_label = QLabel("导出目录：")
    layout.addWidget(export_label)

    export_input_layout = QHBoxLayout()
    parent.export_input_montage = MaterialLineEdit(parent=tab, app_reference=parent, target="output")
    parent.export_input_montage.pathDropped.connect(parent.handle_output_dropped)
    export_input_layout.addWidget(parent.export_input_montage)

    export_button = MaterialButton("选择")
    export_button.clicked.connect(parent.browse_export_folder_montage)
    export_input_layout.addWidget(export_button)
    layout.addLayout(export_input_layout)

    duration_layout = QHBoxLayout()
    duration_label = QLabel("单个合成视频时长（秒）：")
    duration_layout.addWidget(duration_label)

    parent.duration_input_montage = MaterialLineEdit()
    parent.duration_input_montage.setPlaceholderText("输入时长")
    parent.duration_input_montage.textChanged.connect(parent.calculate_video_count)
    duration_layout.addWidget(parent.duration_input_montage)

    parent.video_count_label = QLabel("可合成视频数量：0")
    duration_layout.addWidget(parent.video_count_label)
    layout.addLayout(duration_layout)

    order_layout = QHBoxLayout()
    order_label = QLabel("选择合成顺序：")
    order_layout.addWidget(order_label)

    parent.sequential_radio = QRadioButton("顺序合成")
    parent.random_radio = QRadioButton("乱序合成")
    parent.random_radio.setChecked(True)  # 默认选中“乱序合成”

    parent.order_group = QButtonGroup()
    parent.order_group.addButton(parent.sequential_radio)
    parent.order_group.addButton(parent.random_radio)

    order_layout.addWidget(parent.sequential_radio)
    order_layout.addWidget(parent.random_radio)
    layout.addLayout(order_layout)

    mute_layout = QHBoxLayout()
    parent.mute_checkbox = QCheckBox("静音导出")
    mute_layout.addWidget(parent.mute_checkbox)
    layout.addLayout(mute_layout)

    montage_button = MaterialButton("开始混剪")
    montage_button.clicked.connect(parent.start_montage)
    layout.addWidget(montage_button)

    return tab


def handle_input_dropped(self, folder_path):
    self.folder_input_montage.setText(folder_path)
    self.calculate_total_duration()

def handle_output_dropped(self, folder_path):
    self.export_input_montage.setText(folder_path)

def browse_folder_montage(self):
    folder_path = QFileDialog.getExistingDirectory(self, "选择导入文件夹")
    if folder_path:
        self.folder_input_montage.setText(folder_path)
        self.calculate_total_duration()

def browse_export_folder_montage(self):
    folder_path = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
    if folder_path:
        self.export_input_montage.setText(folder_path)

def calculate_total_duration(self):
    folder_path = self.folder_input_montage.text()
    if os.path.isdir(folder_path):
        self.total_duration_label.setText("计算中...")
        self.signals = MontageSignals()
        self.signals.duration_calculated.connect(self.update_total_duration)
        self.signals.error.connect(self.show_error_message)
        self.duration_task = DurationCalculationTask(folder_path, self.signals)
        QThreadPool.globalInstance().start(self.duration_task)

def update_total_duration(self, total_duration):
    self.total_duration = total_duration
    self.total_duration_label.setText(f"总时长：{int(total_duration)}秒")
    self.calculate_video_count()

def calculate_video_count(self):
    try:
        target_duration = float(self.duration_input_montage.text())
        if self.total_duration:
            video_count = math.ceil(self.total_duration / self.target_duration)
            self.video_count_label.setText(f"可合成的视频数量：{video_count}")
        else:
            self.video_count_label.setText("可合成的视频数量：0")
    except ValueError:
        self.video_count_label.setText("可合成的视频数量：0")


def update_progress(self, value):
    # 更新进度条逻辑，例如更新一个进度条组件
    pass

def montage_completed(self, output_folder):
    QMessageBox.information(self, "完成", f"混剪完成，文件保存在：{output_folder}")

def show_error_message(self, message):
    QMessageBox.critical(self, "错误", message)
