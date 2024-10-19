import os
import sys
import platform
import random
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtCore import QRunnable, pyqtSlot, QObject, pyqtSignal, Qt, QThreadPool
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFileDialog, QDialog, QPushButton, QSpacerItem, QSizePolicy, QMessageBox
from PyQt5.QtGui import QFont, QDesktopServices
from PyQt5.QtCore import QUrl
from ui_components import MaterialButton

# 定义 no_window 变量
if sys.platform == 'win32':
    no_window = subprocess.CREATE_NO_WINDOW
else:
    no_window = 0

class MaterialLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFont(QFont('微软雅黑', 9))  # 设置字体为微软雅黑
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

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            if os.path.isdir(file_path) or file_path.endswith(('.mp4', '.mov', '.3gp')):
                self.setText(file_path)
                event.acceptProposedAction()

class SplitSignals(QObject):
    completed = pyqtSignal(str)
    progress = pyqtSignal(int)

class SplitTask(QRunnable):
    def __init__(self, path, export_path, min_duration, max_duration):
        super(SplitTask, self).__init__()
        self.path = path
        self.export_path = export_path
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.signals = SplitSignals()

    def get_video_duration(self, video_path):
        """获取视频的持续时间"""
        command = ['ffprobe', '-v', 'error', '-show_entries',
                   'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=no_window)
        return float(process.stdout.decode().strip())

    @pyqtSlot()
    def run(self):
        try:
            # 如果是文件夹，遍历文件夹中的视频文件
            if os.path.isdir(self.path):
                output_folder = self.split_videos_in_folder()
            # 如果是单个文件，直接处理该文件
            else:
                output_folder = self.split_single_video(self.path)

            self.signals.completed.emit(output_folder)
        except Exception as e:
            print(f"Error occurred: {e}")

    def split_videos_in_folder(self):
        output_folder = self.export_path

        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.3gp', '.flv', '.wmv', '.mpeg', '.mpg')
        video_files = [f for f in os.listdir(self.path) if f.lower().endswith(video_extensions)]

        total_videos = len(video_files)
        processed_videos = 0

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for video_file in video_files:
                video_path = os.path.join(self.path, video_file)
                futures.append(executor.submit(self.split_single_video, video_path, output_folder))

            for future in futures:
                future.result()

                processed_videos += 1
                progress = int((processed_videos / total_videos) * 100)
                self.signals.progress.emit(progress)  # 这里更新总进度

        return output_folder

    def split_single_video(self, video_path, output_folder=None):
        if output_folder is None:
            output_folder = self.export_path

        video_clip_duration = self.get_video_duration(video_path)
        start_time = 0
        total_segments = 0  # 记录总片段数

        # 先计算片段数
        while start_time < video_clip_duration:
            duration = random.randint(self.min_duration, self.max_duration)
            start_time += duration
            total_segments += 1

        start_time = 0  # 重置开始时间
        progress_increment = 100 / total_segments if total_segments > 0 else 0

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for part in range(1, total_segments + 1):
                duration = random.randint(self.min_duration, self.max_duration)
                end_time = min(start_time + duration, video_clip_duration)

                output_video_path = os.path.join(output_folder,
                                                 f"{os.path.splitext(os.path.basename(video_path))[0]}_part{part}.mp4")
                futures.append(executor.submit(self.process_clip, video_path, start_time, end_time, output_video_path))

                # 记录处理开始时间
                start_time = end_time  # Move to the next segment

            # 遍历所有的 future，确保捕获任何异常
            for i, future in enumerate(futures):
                try:
                    future.result()  # 获取结果，捕获异常
                    self.signals.progress.emit(min(int((i + 1) * progress_increment), 100))  # 避免超出100%
                except Exception as e:
                    print(f"Error processing segment {i + 1}: {e}")
                    self.signals.progress.emit(min(int((i + 1) * progress_increment), 100))  # 强制更新进度

        # 确保最后一次更新进度条为100%
        self.signals.progress.emit(100)

        return output_folder

    def process_clip(self, video_path, start_time, end_time, output_video_path):
        self.extract_subclip(video_path, start_time, end_time, output_video_path)

    # # 这个方案打包出来之后，运行分割，会快速闪烁命令行
    # def extract_subclip(self, video_path, start_time, end_time, output_path):
    #     """提取子剪辑"""
    #     video_codec = 'libx264'
    #     preset = 'ultrafast'
    #
    #     command = [
    #         'ffmpeg', '-y', '-loglevel', 'error', '-i', video_path,
    #         '-ss', str(start_time), '-to', str(end_time),
    #         '-c:v', video_codec, '-preset', preset, '-crf', '23',
    #         '-c:a', 'aac', '-b:a', '128k',
    #         output_path
    #     ]
    #
    #     # 在 Windows 系统中隐藏窗口
    #     if platform.system() == "Windows":
    #         startupinfo = subprocess.STARTUPINFO()
    #         startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    #         startupinfo.wShowWindow = subprocess.SW_HIDE  # 隐藏命令行窗口
    #
    #         process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    #                                    startupinfo=startupinfo)
    #     else:
    #         process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #
    #     stdout, stderr = process.communicate()
    #
    #     if process.returncode != 0:
    #         error_message = stderr.decode('utf-8').strip()
    #         print(f"Failed to extract subclip: {error_message}")
    #         raise Exception(f"FFmpeg 错误: {error_message}")

    def extract_subclip(self, video_path, start_time, end_time, output_path):
        """提取子剪辑"""
        video_codec = 'libx264'
        preset = 'ultrafast'

        command = [
            'ffmpeg', '-y', '-loglevel', 'error', '-i', video_path,
            '-ss', str(start_time), '-to', str(end_time),
            '-c:v', video_codec, '-preset', preset, '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            output_path
        ]

        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                                    creationflags=no_window)
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode('utf-8').strip()
            print(f"Failed to extract subclip: {error_message}")
            raise Exception(f"FFmpeg 错误: {error_message}")


class SplitTab(QWidget):
    def __init__(self, parent=None):
        super(SplitTab, self).__init__(parent)
        self.dialog_shown = False  # 添加对话框已弹出标志
        self.main_window = parent  # 保存主窗口的引用
        self.scroll_index = 0
        self.scroll_text = "正在分割，请耐心等待..."
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        folder_layout = QHBoxLayout()
        folder_label = QLabel("导入文件夹/视频文件：")
        layout.addWidget(folder_label)

        self.folder_input = MaterialLineEdit()  # 确保 MaterialLineEdit 类已经正确定义或导入
        folder_layout.addWidget(self.folder_input)

        browse_button = MaterialButton("选择")
        browse_button.clicked.connect(self.browse_folder)
        folder_layout.addWidget(browse_button)
        layout.addLayout(folder_layout)

        export_layout = QHBoxLayout()
        export_label = QLabel("导出目录：")
        layout.addWidget(export_label)

        self.export_input = MaterialLineEdit()  # 确保 MaterialLineEdit 类已经正确定义或导入
        export_layout.addWidget(self.export_input)

        export_button = MaterialButton("选择")
        export_button.clicked.connect(self.browse_export_folder)
        export_layout.addWidget(export_button)
        layout.addLayout(export_layout)

        duration_label = QLabel("设置分割时长区间（秒）：")
        layout.addWidget(duration_label)

        duration_layout = QHBoxLayout()
        self.duration_min = MaterialLineEdit()
        self.duration_min.setPlaceholderText("最小时长")
        self.duration_max = MaterialLineEdit()
        self.duration_max.setPlaceholderText("最大时长")
        duration_layout.addWidget(self.duration_min)
        duration_layout.addWidget(self.duration_max)

        layout.addLayout(duration_layout)

        self.split_button = MaterialButton("开始分割")
        self.split_button.clicked.connect(self.on_split_button_clicked)
        layout.addWidget(self.split_button)

    def on_split_button_clicked(self):
        """当用户点击‘开始分割’按钮后执行"""
        # 重置进度条
        self.main_window.progress_bar.setValue(0)
        self.dialog_shown = False  # 重置对话框状态
        self.split_button.setEnabled(True)  # 确保按钮可用

        # 检查是否输入完整参数
        if not self.duration_min.text() or not self.duration_max.text():
            QMessageBox.warning(self, "输入错误", "请完整填写最小和最大时长。")
            return

        # 获取用户输入的参数
        folder_path = self.folder_input.text()
        export_path = self.export_input.text()

        # **新增：检查导入和导出目录是否已指定**
        if not folder_path:
            QMessageBox.warning(self, "输入错误", "请指定导入文件夹或视频文件。")
            return
        if not export_path:
            QMessageBox.warning(self, "输入错误", "请指定导出目录。")
            return

        # **检查导入路径是否存在并且有效**
        if not os.path.exists(folder_path):
            QMessageBox.warning(self, "输入错误", "指定的导入文件夹或视频文件不存在。")
            return

        # **检查导入路径是否为目录或支持的视频文件**
        valid_video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.3gp', '.flv', '.wmv', '.mpeg', '.mpg')
        if not (os.path.isdir(folder_path) or folder_path.lower().endswith(valid_video_extensions)):
            QMessageBox.warning(self, "输入错误", "指定的导入路径不是有效的文件夹或支持的视频文件。")
            return

        # **检查导出路径是否存在**
        if not os.path.exists(export_path):
            # 如果导出路径不存在，提示用户是否创建
            reply = QMessageBox.question(self, '导出目录不存在',
                                         f"导出目录 {export_path} 不存在，是否创建？",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                try:
                    os.makedirs(export_path)
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"创建导出目录失败：{e}")
                    return
            else:
                return
        else:
            # 检查导出路径是否为目录
            if not os.path.isdir(export_path):
                QMessageBox.warning(self, "输入错误", "指定的导出路径不是一个有效的目录。")
                return

        # 尝试将输入转换为整数，并添加异常处理
        try:
            min_duration = int(self.duration_min.text())
            max_duration = int(self.duration_max.text())
        except ValueError:
            QMessageBox.warning(self, "输入错误", "最小和最大时长必须为整数！")
            return

        # 添加最小时长不大于最大时长的验证
        if min_duration > max_duration:
            QMessageBox.warning(self, "输入错误", "最小时长不能大于最大时长。")
            return

        # 创建带时间戳的导出目录
        timestamp = time.strftime("%Y%m%d%H%M%S")
        export_folder = os.path.join(export_path, f"非丨本次分割结果_{timestamp}")
        os.makedirs(export_folder, exist_ok=True)

        # 自动打开新建的导出文件夹
        if os.name == 'nt':  # Windows 系统
            os.startfile(export_folder)
        else:
            subprocess.run(['xdg-open', export_folder])

        # 创建分割任务，使用新建的导出文件夹
        split_task = SplitTask(folder_path, export_folder, min_duration, max_duration)

        # 将 SplitTask 的 progress 信号连接到主窗口的 progress_update 信号
        split_task.signals.progress.connect(self.main_window.progress_update, Qt.QueuedConnection)

        split_task.signals.completed.connect(self.on_split_completed)
        QThreadPool.globalInstance().start(split_task)

    def on_split_completed(self, output_folder):
        """当分割完成时执行"""
        # 手动将进度条设置为 100%
        self.main_window.progress_bar.setValue(100)

        # 取消任何定时器的引用
        if hasattr(self, 'timer') and self.timer is not None:
            self.timer.stop()  # 确保不再使用定时器
            self.timer = None  # 清除引用

        # 重新启用分割按钮
        self.split_button.setEnabled(True)
        self.split_button.setText("开始分割")  # 确保按钮文字恢复为初始状态
        print(f"分割完成，输出文件夹为：{output_folder}")

        if not self.dialog_shown:
            self.dialog_shown = True
            self.show_completion_dialog()

    def show_completion_dialog(self):
        """分割完成后的高逼格对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("视频分割已完成")
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # 去除问号
        dialog.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border-radius: 15px;
                color: #333333;
                font-family: '微软雅黑';
            }
            QPushButton {
                border: 2px solid #CCCCCC;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                font-family: '微软雅黑';
            }
            QPushButton#contact {
                background-color: #FF6F61;
                color: white;
            }
            QPushButton#ok {
                background-color: #68B684;
                color: white;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
            }
        """)

        layout = QVBoxLayout(dialog)

        # 标题
        title_label = QLabel("视频分割已完成")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #333333; margin-bottom: 20px; font-family: '微软雅黑';")
        layout.addWidget(title_label)

        button_layout = QHBoxLayout()

        # 联系非哥按钮
        contact_button = QPushButton("联系非哥")
        contact_button.setObjectName("contact")
        contact_button.clicked.connect(self.open_contact_link)

        # OK按钮
        ok_button = QPushButton("OK")
        ok_button.setObjectName("ok")
        ok_button.clicked.connect(dialog.accept)

        button_layout.addWidget(contact_button)
        button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec_()

    def open_contact_link(self):
        """打开联系非哥的链接"""
        QDesktopServices.openUrl(QUrl("https://a.eturl.cn/JJqTZV"))

    def browse_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder_path:
            self.folder_input.setText(folder_path)

    def browse_export_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if folder_path:
            self.export_input.setText(folder_path)

def create_split_tab(parent):
    """创建并返回 SplitTab 实例"""
    return SplitTab(parent)