import os
import sys
import json
import keyboard
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel, QFileDialog,
                           QListWidget, QStyle, QStyleFactory, QLineEdit, QComboBox, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QPalette, QColor, QIcon
from midi_player import MidiPlayer
from keyboard_mapping import CONTROL_KEYS
import mido
import time

# 忽略废弃警告
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

CONFIG_FILE = "config.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 设置Windows 10风格
        QApplication.setStyle(QStyleFactory.create('Windows'))
        
        self.setWindowTitle("燕云-自动演奏")
        self.setMinimumSize(800, 600)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 加载配置
        self.config = self.load_config()
        self.last_directory = self.config.get('last_directory', '')
        
        # 添加键盘事件防抖动
        self.last_key_time = 0
        self.key_cooldown = 0.2  # 200ms冷却时间
        
        # 设置基础样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
                color: #333333;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
                border-color: #adadad;
            }
            QPushButton:pressed {
                background-color: #d4d4d4;
                border-color: #8c8c8c;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                font-size: 14px;
            }
            QLabel {
                color: #333333;
                font-size: 14px;
            }
            QLineEdit {
                font-size: 14px;
                padding: 5px;
            }
            QCheckBox {
                font-size: 14px;
            }
        """)
        
        self.midi_player = MidiPlayer()
        self.midi_files = []
        self.current_index = -1
        
        # 用于更新进度条的计时器
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.setInterval(100)  # 每100ms更新一次
        
        self.setup_ui()
        self.setup_keyboard_hooks()
        
        # 应用保存的置顶状态
        stay_on_top = self.config.get('stay_on_top', True)  # 默认为True
        self.stay_on_top.setChecked(stay_on_top)  # 设置复选框状态
        if stay_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        
        # 如果有上次的目录，自动加载
        if self.last_directory and os.path.exists(self.last_directory):
            self.load_directory(self.last_directory)

    def closeEvent(self, event):
        """重写关闭事件，直接退出程序"""
        self.quit_application()
        event.accept()

    def quit_application(self):
        """退出应用程序"""
        # 停止播放
        if self.midi_player.playing:
            self.midi_player.stop()
        
        # 停止所有计时器
        self.stop_timers()
        
        # 保存配置
        self.save_config()
        
        # 移除所有键盘钩子
        keyboard.unhook_all()
        
        # 退出应用程序
        QApplication.quit()

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 如果配置文件不存在，创建默认配置
                default_config = {
                    'last_directory': '',
                    'stay_on_top': False
                }
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                return default_config
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return {'last_directory': '', 'stay_on_top': False}

    def save_config(self):
        """保存配置文件"""
        try:
            config = {
                'last_directory': self.last_directory,
                'stay_on_top': self.stay_on_top.isChecked()
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")

    def setup_ui(self):
        """设置UI界面"""
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧布局
        left_widget = QWidget()
        left_widget.setFixedWidth(300)
        left_layout = QVBoxLayout(left_widget)
        
        # 添加置顶复选框
        top_layout = QHBoxLayout()
        self.stay_on_top = QCheckBox("窗口置顶")
        self.stay_on_top.stateChanged.connect(self.toggle_stay_on_top)
        top_layout.addWidget(self.stay_on_top)
        top_layout.addStretch()
        left_layout.addLayout(top_layout)
        
        # 文件选择按钮
        self.file_button = QPushButton("选择MIDI文件夹")
        self.file_button.clicked.connect(self.select_directory)
        left_layout.addWidget(self.file_button)
        
        # 搜索框
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索歌曲...")
        self.search_input.textChanged.connect(self.filter_songs)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)
        
        # 歌曲列表
        self.song_list = QListWidget()
        self.song_list.itemSelectionChanged.connect(self.song_selected)
        left_layout.addWidget(self.song_list)
        
        main_layout.addWidget(left_widget)
        
        # 右侧布局
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 音轨选择标题
        track_label = QLabel("选择音轨:")
        track_label.setStyleSheet("QLabel { padding: 5px; }")
        right_layout.addWidget(track_label)
        
        # 音轨列表
        self.tracks_list = QListWidget()
        self.tracks_list.itemSelectionChanged.connect(self.track_selected)
        right_layout.addWidget(self.tracks_list)
        
        # 添加时间显示
        self.time_label = QLabel("剩余时间: 00:00")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("QLabel { padding: 5px; }")
        right_layout.addWidget(self.time_label)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        # 播放按钮
        self.play_button = QPushButton("播放")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.toggle_play)
        control_layout.addWidget(self.play_button)
        
        # 暂停按钮
        self.pause_button = QPushButton("暂停")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.pause_playback)
        control_layout.addWidget(self.pause_button)
        
        # 停止按钮
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_playback)
        control_layout.addWidget(self.stop_button)
        
        right_layout.addLayout(control_layout)
        
        # 添加说明文字（移到底部）
        right_layout.addStretch()  # 添加弹性空间
        
        # 添加使用说明
        usage_label = QLabel("使用说明：\n1. 使用管理员权限启动\n2. 选择MIDI文件\n3. 选择要播放的音轨\n4. 点击播放按钮开始演奏")
        usage_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        right_layout.addWidget(usage_label)
        
        # 添加快捷键说明
        shortcut_label = QLabel("快捷键说明：\n减号键(-) - 播放/暂停\n等号键(=) - 停止播放\n方向键上 - 上一首\n方向键下 - 下一首")
        shortcut_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        right_layout.addWidget(shortcut_label)
        
        main_layout.addWidget(right_widget)

    def setup_keyboard_hooks(self):
        """设置全局键盘钩子"""
        try:
            keyboard.on_press_key(CONTROL_KEYS['START_PAUSE'], 
                                lambda e: self.safe_key_handler(self.pause_playback), 
                                suppress=True)
            keyboard.on_press_key(CONTROL_KEYS['STOP'], 
                                lambda e: self.safe_key_handler(self.stop_playback), 
                                suppress=True)
            keyboard.on_press_key(CONTROL_KEYS['PREV_SONG'], 
                                lambda e: self.safe_key_handler(lambda: self.change_song(-1)), 
                                suppress=True)
            keyboard.on_press_key(CONTROL_KEYS['NEXT_SONG'], 
                                lambda e: self.safe_key_handler(lambda: self.change_song(1)), 
                                suppress=True)
        except Exception as e:
            print(f"设置键盘钩子时出错: {str(e)}")

    def safe_key_handler(self, func):
        """安全地处理键盘事件，添加防抖动和状态检查"""
        try:
            current_time = time.time()
            if current_time - self.last_key_time < self.key_cooldown:
                return
            
            self.last_key_time = current_time
            
            if self.isVisible():
                func()
                
        except Exception as e:
            print(f"处理键盘事件时出错: {str(e)}")

    def load_directory(self, dir_path):
        """加载指定目录的MIDI文件"""
        self.midi_files = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(('.mid', '.midi')):
                    self.midi_files.append(os.path.join(root, file))
        
        # 清除搜索框
        self.search_input.clear()
        
        # 显示所有歌曲
        self.song_list.clear()
        for file in self.midi_files:
            self.song_list.addItem(os.path.basename(file))

    def select_directory(self):
        """选择MIDI文件夹"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "选择MIDI文件夹",
                self.last_directory
            )
            
            if dir_path:
                # 更新最后访问的目录
                self.last_directory = dir_path
                self.save_config()
                
                # 加载目录中的所有MIDI文件（包括子目录）
                self.midi_files = []
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        if file.lower().endswith(('.mid', '.midi')):
                            self.midi_files.append(os.path.join(root, file))
                
                # 清空并更新歌曲列表
                self.song_list.clear()
                for file in self.midi_files:
                    self.song_list.addItem(os.path.basename(file))
                
                # 如果有文件，选中第一个
                if self.midi_files:
                    self.song_list.setCurrentRow(0)
                    self.current_index = 0
                    self.play_button.setEnabled(True)
                    self.stop_button.setEnabled(True)
                    self.pause_button.setEnabled(True)
                
        except Exception as e:
            print(f"选择文件夹时出错: {str(e)}")

    def song_selected(self):
        """处理歌曲选择"""
        try:
            current_item = self.song_list.currentItem()
            if not current_item:
                return
                
            # 获取当前选中项的索引
            index = self.song_list.row(current_item)
            
            if 0 <= index < len(self.midi_files):
                self.current_index = index
                
                try:
                    # 加载MIDI文件并分析音轨
                    mid = mido.MidiFile(self.midi_files[index])
                    self.midi_player.analyze_tracks(mid)
                    self.update_tracks_list()
                except (EOFError, OSError, ValueError) as e:
                    print(f"MIDI文件损坏或格式不正确: {str(e)}")
                    # 从列表中移除损坏的文件
                    self.song_list.takeItem(index)
                    self.midi_files.pop(index)
                    # 重置当前索引
                    self.current_index = -1
                    # 清空音轨列表
                    self.tracks_list.clear()
                    self.tracks_list.addItem("◆ 全部音轨")
                except Exception as e:
                    print(f"加载MIDI文件时出错: {str(e)}")
                    # 清空音轨列表
                    self.tracks_list.clear()
                    self.tracks_list.addItem("◆ 全部音轨")
                    
                # 启用播放和停止按钮
                self.play_button.setEnabled(True)
                self.stop_button.setEnabled(True)
                self.pause_button.setEnabled(True)
                
        except Exception as e:
            print(f"选择歌曲时出错: {str(e)}")
            self.current_index = -1

    def format_time(self, seconds):
        """将秒数格式化为 mm:ss 格式"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def update_progress(self):
        """更新倒计时显示"""
        if self.midi_player.playing and not self.midi_player.paused:
            current_time = self.midi_player.get_current_time()
            total_time = self.midi_player.get_total_time()
            
            if total_time > 0:
                remaining_time = max(0, total_time - current_time)
                self.time_label.setText(f"剩余时间: {self.format_time(remaining_time)}")
                
                # 如果播放结束，自动停止
                if remaining_time == 0:
                    self.stop_playback()

    def update_button_states(self):
        """更新按钮状态"""
        # 重置所有按钮样式
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
                color: #333333;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
                border-color: #adadad;
            }
        """)
        self.pause_button.setStyleSheet(self.play_button.styleSheet())
        self.stop_button.setStyleSheet(self.play_button.styleSheet())

        # 根据播放状态设置高亮
        if self.midi_player.playing:
            if self.midi_player.paused:
                # 暂停状态：暂停按钮高亮
                self.pause_button.setStyleSheet("""
                    QPushButton {
                        background-color: #5cb85c;
                        border: 1px solid #4cae4c;
                        border-radius: 4px;
                        padding: 5px 15px;
                        min-width: 80px;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #449d44;
                        border-color: #398439;
                    }
                """)
            else:
                # 播放状态：播放按钮高亮
                self.play_button.setStyleSheet("""
                    QPushButton {
                        background-color: #5cb85c;
                        border: 1px solid #4cae4c;
                        border-radius: 4px;
                        padding: 5px 15px;
                        min-width: 80px;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #449d44;
                        border-color: #398439;
                    }
                """)

    def start_playback(self):
        if self.current_index >= 0:
            self.midi_player.play_file(self.midi_files[self.current_index])
            # 使用 QMetaObject.invokeMethod 在主线程中更新 UI
            QMetaObject.invokeMethod(self, "update_ui_after_playback",
                                   Qt.QueuedConnection)

    @pyqtSlot()
    def update_ui_after_playback(self):
        """在主线程中更新UI"""
        # 更新按钮状态
        self.update_button_states()
        # 启动计时器
        if not self.progress_timer.isActive():
            self.progress_timer.start()

    def stop_playback(self):
        self.midi_player.stop()
        # 使用 QMetaObject.invokeMethod 在主线程中更新 UI
        QMetaObject.invokeMethod(self, "update_ui_after_stop",
                               Qt.QueuedConnection)

    @pyqtSlot()
    def update_ui_after_stop(self):
        """在主线程中更新UI"""
        # 更新按钮状态
        self.update_button_states()
        # 停止计时器
        if self.progress_timer.isActive():
            self.progress_timer.stop()
        self.time_label.setText("剩余时间: 00:00")

    def pause_playback(self):
        """处理播放/暂停"""
        try:
            if self.midi_player.playing:
                self.midi_player.pause()
                # 使用 QMetaObject.invokeMethod 在主线程中更新 UI
                QMetaObject.invokeMethod(self, "update_ui_after_pause",
                                       Qt.QueuedConnection)
            else:
                # 只有在有选中的歌曲时才开始播放
                if self.current_index >= 0:
                    self.start_playback()
        except Exception as e:
            print(f"播放/暂停操作时出错: {str(e)}")

    @pyqtSlot()
    def update_ui_after_pause(self):
        """在主线程中更新UI"""
        # 更新按钮状态
        self.update_button_states()
        if self.midi_player.paused:
            if self.progress_timer.isActive():
                self.progress_timer.stop()
        else:
            if not self.progress_timer.isActive():
                self.progress_timer.start()

    def change_song(self, delta):
        """切换歌曲"""
        try:
            if not self.midi_files:
                return
                
            # 计算新的索引
            new_index = (self.current_index + delta) % len(self.midi_files)
            if new_index < 0:  # 处理负数索引
                new_index = len(self.midi_files) - 1
                
            print(f"切换歌曲: 当前索引 {self.current_index}, 新索引 {new_index}")
            
            # 使用 QMetaObject.invokeMethod 在主线程中更新 UI
            QMetaObject.invokeMethod(self, "update_ui_after_song_change",
                                   Qt.QueuedConnection,
                                   Q_ARG(int, new_index))
                
        except Exception as e:
            print(f"切换歌曲时出错: {str(e)}")

    @pyqtSlot(int)
    def update_ui_after_song_change(self, new_index):
        """在主线程中更新UI"""
        # 更新列表选择
        self.song_list.setCurrentRow(new_index)
        
        # 如果正在播放，停止当前播放并开始新歌曲
        was_playing = self.midi_player.playing
        if was_playing:
            self.stop_playback()
            # 确保当前索引已更新（通过song_selected）
            self.start_playback()

    def stop_timers(self):
        """停止所有计时器"""
        if self.progress_timer.isActive():
            self.progress_timer.stop()

    def update_tracks_list(self):
        """更新音轨列表"""
        try:
            self.tracks_list.clear()
            
            # 添加"全部音轨"选项
            self.tracks_list.addItem("◆ 全部音轨")
            
            # 检查是否有可用的音轨信息
            if hasattr(self.midi_player, 'tracks_info') and self.midi_player.tracks_info:
                # 添加各个音轨信息
                for track in self.midi_player.tracks_info:
                    if 'name' in track and 'notes_count' in track:
                        track_info = f"◇ {track['name']} [音符: {track['notes_count']}]"
                        self.tracks_list.addItem(track_info)
            
            # 默认选择全部音轨
            self.tracks_list.setCurrentRow(0)
            self.midi_player.set_track(None)
            
        except Exception as e:
            print(f"更新音轨列表时出错: {str(e)}")
            # 出错时重置列表
            self.tracks_list.clear()
            self.tracks_list.addItem("◆ 全部音轨")
            self.tracks_list.setCurrentRow(0)
            self.midi_player.set_track(None)

    def track_selected(self):
        """处理音轨选择变化"""
        try:
            current_row = self.tracks_list.currentRow()
            
            # 检查是否有有效选择
            if current_row < 0:
                return
                
            # 检查是否选择了"全部音轨"
            if current_row == 0:
                self.midi_player.set_track(None)
            else:
                # 检查索引是否有效
                if current_row - 1 < len(self.midi_player.tracks_info):
                    channel = self.midi_player.tracks_info[current_row - 1]['channel']
                    self.midi_player.set_track(channel)
                else:
                    print(f"无效的音轨索引: {current_row - 1}, 可用音轨数: {len(self.midi_player.tracks_info)}")
                    # 重置为全部音轨
                    self.tracks_list.setCurrentRow(0)
                    self.midi_player.set_track(None)
                    return
            
            # 如果正在播放，重新开始播放选中的音轨
            if self.midi_player.playing:
                self.stop_playback()
                self.start_playback()
                
        except Exception as e:
            print(f"选择音轨时出错: {str(e)}")
            # 发生错误时重置为全部音轨
            self.tracks_list.setCurrentRow(0)
            self.midi_player.set_track(None)

    def filter_songs(self, text):
        """根据搜索文本过滤歌曲列表"""
        try:
            search_text = text.lower()
            self.song_list.clear()
            
            if not search_text:
                # 如果搜索框为空，显示所有歌曲
                for file in self.midi_files:
                    self.song_list.addItem(os.path.basename(file))
            else:
                # 否则显示匹配的歌曲
                for file in self.midi_files:
                    filename = os.path.basename(file).lower()
                    if search_text in filename:
                        self.song_list.addItem(os.path.basename(file))
            
            # 如果之前有选中的歌曲，尝试重新选中
            if self.current_index >= 0 and self.current_index < len(self.midi_files):
                current_file = os.path.basename(self.midi_files[self.current_index])
                # 查找当前歌曲在过滤后列表中的位置
                for i in range(self.song_list.count()):
                    if self.song_list.item(i).text() == current_file:
                        self.song_list.setCurrentRow(i)
                        break
                        
        except Exception as e:
            print(f"过滤歌曲时出错: {str(e)}")

    def clear_search(self):
        """清除搜索框并显示所有歌曲"""
        self.search_input.clear()
        self.filter_songs("")

    def toggle_stay_on_top(self, state):
        """切换窗口置顶状态"""
        if state == Qt.Checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()  # 需要重新显示窗口以应用更改

    def select_file(self):
        """保留此方法以保持兼容性，但改为调用select_directory"""
        self.select_directory()

    def toggle_play(self):
        """切换播放/暂停状态"""
        if not self.midi_player.playing:
            self.start_playback()
        else:
            self.pause_playback()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 