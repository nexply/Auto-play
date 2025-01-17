"""
MIDI自动演奏程序 - 一个基于PyQt5的MIDI文件播放器，支持选择音轨和键盘控制。
提供直观的界面来加载、选择和播放MIDI文件，并支持全局快捷键控制。
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
import keyboard
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel, QFileDialog,
                           QListWidget, QStyleFactory, QLineEdit, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QMetaObject, Q_ARG, pyqtSlot, QThread
from PyQt5.QtGui import QIcon
from midi_player import MidiPlayer
from keyboard_mapping import CONTROL_KEYS
import mido
import time
import pygame.mixer
import threading

# 忽略废弃警告
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 在主程序中添加或更新版本号
VERSION = "1.0.3"

class Config:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.data = self.load()
    
    def load(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
        return self.get_default_config()
    
    def save(self, data):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
    
    @staticmethod
    def get_default_config():
        return {
            'last_directory': '',
            'stay_on_top': False
        }

def handle_error(func_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"{func_name}时出错: {str(e)}")
                # 可以添加通用的错误恢复逻辑
        return wrapper
    return decorator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 设置Windows 10风格
        QApplication.setStyle(QStyleFactory.create('Windows'))
        
        self.setWindowTitle(f"燕云-自动演奏by木木睡没-{VERSION}")
        self.setMinimumSize(650, 550)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 创建配置管理器实例
        self.config_manager = Config()
        # 从配置管理器获取配置
        self.config = self.config_manager.data
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
        
        # 初始化pygame mixer
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"初始化音频系统失败: {str(e)}")
        
        self.is_previewing = False
        
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
        """重写关闭事件，确保正确清理资源"""
        # 停止预览
        if self.is_previewing:
            self.stop_preview()
        
        # 清理pygame
        try:
            pygame.mixer.quit()
        except Exception as e:
            print(f"清理pygame时出错: {e}")
        
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
        """返回当前配置"""
        return self.config_manager.data

    def save_config(self):
        """保存配置文件"""
        config = {
            'last_directory': self.last_directory,
            'stay_on_top': self.stay_on_top.isChecked()
        }
        self.config_manager.save(config)

    def setup_ui(self):
        """设置UI界面"""
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧布局
        left_widget = QWidget()
        left_widget.setFixedWidth(260)
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
        
        # 修改控制按钮布局
        control_layout = QHBoxLayout()
        
        # 合并播放/暂停按钮
        self.play_pause_button = QPushButton("播放")
        self.play_pause_button.setEnabled(False)
        self.play_pause_button.clicked.connect(self.toggle_play)
        control_layout.addWidget(self.play_pause_button)
        
        # 停止按钮
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_playback)
        control_layout.addWidget(self.stop_button)
        
        # 预览按钮
        self.preview_button = QPushButton("预览")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self.toggle_preview)
        control_layout.addWidget(self.preview_button)
        
        right_layout.addLayout(control_layout)
        
        # 添加说明文字（移到底部）
        right_layout.addStretch()  # 添加弹性空间
        
        # 添加使用说明
        usage_label = QLabel("注意：工具支持36键模式!\n使用说明：\n1. 使用管理员权限启动\n2. 选择MIDI文件\n3. 选择要播放的音轨\n4. 点击播放按钮开始演奏")
        usage_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        right_layout.addWidget(usage_label)
        
        # 添加快捷键说明
        shortcut_label = QLabel("快捷键说明：\nAlt + 减号键(-) 播放/暂停\nAlt + 等号键(=) 停止播放\nAlt + 方向键上 上一首\nAlt + 方向键下 下一首")
        shortcut_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        right_layout.addWidget(shortcut_label)
        
        main_layout.addWidget(right_widget)

    def setup_keyboard_hooks(self):
        """设置全局键盘钩子"""
        try:
            # 使用CONTROL_KEYS中定义的组合键
            keyboard.add_hotkey(CONTROL_KEYS['START_PAUSE'], 
                              lambda: self.safe_key_handler(self.pause_playback))
            keyboard.add_hotkey(CONTROL_KEYS['STOP'], 
                              lambda: self.safe_key_handler(self.stop_playback))
            keyboard.add_hotkey(CONTROL_KEYS['PREV_SONG'], 
                              lambda: self.safe_key_handler(lambda: self.change_song(-1)))
            keyboard.add_hotkey(CONTROL_KEYS['NEXT_SONG'], 
                              lambda: self.safe_key_handler(lambda: self.change_song(1)))
        except Exception as e:
            print(f"设置键盘钩子时出错: {str(e)}")
            # 尝试清理所有热键
            try:
                keyboard.unhook_all()
            except Exception as e:
                print(f"清理键盘钩子时出错: {str(e)}")

    def safe_key_handler(self, func):
        """安全地处理键盘事件，添加防抖动和状态检查"""
        try:
            current_time = time.time()
            if current_time - self.last_key_time < self.key_cooldown:
                return
            
            self.last_key_time = current_time
            
            # 确保窗口可见且未最小化
            if self.isVisible() and not self.isMinimized():
                func()
                
        except Exception as e:
            print(f"处理键盘事件时出错: {str(e)}")

    def _load_midi_files(self, dir_path):
        """加载指定目录下的所有MIDI文件"""
        midi_files = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(('.mid', '.midi')):
                    midi_files.append(os.path.join(root, file))
        return midi_files

    def select_directory(self):
        """选择MIDI文件夹"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "选择MIDI文件夹",
                self.last_directory
            )
            
            if dir_path:
                self.last_directory = dir_path
                self.save_config()
                self.midi_files = self._load_midi_files(dir_path)
                # 清空并更新歌曲列表
                self.song_list.clear()
                for file in self.midi_files:
                    self.song_list.addItem(os.path.basename(file))
                
                # 如果有文件，选中第一个
                if self.midi_files:
                    self.song_list.setCurrentRow(0)
                    self.current_index = 0
                    self.play_pause_button.setEnabled(True)
                    self.stop_button.setEnabled(True)
                    self.play_pause_button.setText("播放")
                    self.play_pause_button.setStyleSheet("""
                        QPushButton {
                            background-color: #5cb85c;
                            color: white;
                            border: 1px solid #4cae4c;
                        }
                        QPushButton:hover {
                            background-color: #449d44;
                            border-color: #398439;
                        }
                    """)
                
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
                    # 先分析音轨信息
                    self.midi_player.analyze_tracks(mid)
                    # 然后更新音轨列表显示
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
                    
                # 启用播放和停止按钮
                self.play_pause_button.setEnabled(True)
                self.stop_button.setEnabled(True)
                self.preview_button.setEnabled(True)
                
                # 如果正在预览，停止预览
                if self.is_previewing:
                    self.stop_preview()
                    
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
        try:
            # 修改 has_file 的判断逻辑
            has_file = self.current_index >= 0 and len(self.midi_files) > 0
            is_playing = self.midi_player.playing
            is_paused = self.midi_player.paused
            
            # 更新播放/暂停按钮状态
            self.play_pause_button.setEnabled(has_file)
            if is_playing:
                if is_paused:  # 如果暂停中
                    self.play_pause_button.setText("继续")
                else:  # 如果正在播放
                    self.play_pause_button.setText("暂停")
                self.play_pause_button.setStyleSheet("""
                    QPushButton {
                        background-color: #f0ad4e;
                        color: white;
                        border: 1px solid #eea236;
                    }
                    QPushButton:hover {
                        background-color: #ec971f;
                        border-color: #d58512;
                    }
                """)
            else:  # 如果未播放
                self.play_pause_button.setText("播放")
                self.play_pause_button.setStyleSheet("")
            
            # 更新停止按钮状态
            self.stop_button.setEnabled(is_playing)
            
            # 更新预览按钮状态（如果存在）
            if hasattr(self, 'preview_button'):
                self.preview_button.setEnabled(has_file and not is_playing)
            
        except Exception as e:
            print(f"更新按钮状态时出错: {str(e)}")

    def start_playback(self):
        """开始播放MIDI文件"""
        try:
            if self.current_index < 0 or not self.midi_files:
                return
            
            current_file = self.midi_files[self.current_index]
            current_row = self.tracks_list.currentRow()
            
            # 启动播放线程
            self.play_thread = threading.Thread(
                target=self.midi_player.play_midi,
                args=(current_file, current_row)
            )
            self.play_thread.start()
            
            # 更新UI状态
            self.update_ui("playback")
            
        except Exception as e:
            print(f"开始播放时出错: {str(e)}")

    @pyqtSlot(str)
    def update_ui_state(self, state):
        """统一处理UI状态更新"""
        try:
            # 确保在主线程中执行
            if QThread.currentThread() != QApplication.instance().thread():
                QMetaObject.invokeMethod(self, "update_ui_state",
                                       Qt.QueuedConnection,
                                       Q_ARG(str, state))
                return
            
            self.update_button_states()
            
            if state == "play":
                if not self.progress_timer.isActive():
                    self.progress_timer.start()
            elif state == "stop":
                if self.progress_timer.isActive():
                    self.progress_timer.stop()
                self.time_label.setText("剩余时间: 00:00")
            elif state == "pause":
                if self.midi_player.paused:
                    if self.progress_timer.isActive():
                        self.progress_timer.stop()
                else:
                    if not self.progress_timer.isActive():
                        self.progress_timer.start()
        except Exception as e:
            print(f"更新UI状态时出错: {str(e)}")

    def stop_playback(self):
        self.midi_player.stop()
        # 使用 QMetaObject.invokeMethod 在主线程中更新 UI
        QMetaObject.invokeMethod(self, "update_ui_after_stop",
                               Qt.QueuedConnection)

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
            
            # 检查是否有可用的音轨信息
            if not hasattr(self.midi_player, 'tracks_info') or not self.midi_player.tracks_info:
                self.tracks_list.addItem("◆ 全部音轨")
                return
            
            # 首先计算所有音轨的总体信息
            total_notes = 0
            total_playable = 0
            min_note = float('inf')
            max_note = float('-inf')
            
            for track in self.midi_player.tracks_info:
                if 'notes' in track:
                    track_notes = track['notes']
                    if track_notes:  # 确保有音符
                        total_notes += len(track_notes)
                        min_note = min(min_note, min(track_notes))
                        max_note = max(max_note, max(track_notes))
                        playable_notes = sum(1 for note in track_notes 
                                           if 36 <= (note + self.midi_player.note_offset) <= 96)
                        total_playable += playable_notes
            
            # 添加全部音轨选项，包含详细信息
            if min_note != float('inf'):
                adjusted_min = min_note + self.midi_player.note_offset
                adjusted_max = max_note + self.midi_player.note_offset
                all_tracks_text = (f"◆ 全部音轨 [原始范围: {min_note}-{max_note}, "
                                 f"调整后: {adjusted_min}-{adjusted_max}, "
                                 f"可播放: {total_playable}/{total_notes}]")
            else:
                all_tracks_text = "◆ 全部音轨"
            self.tracks_list.addItem(all_tracks_text)
            
            # 添加各个音轨的详细信息
            for i, track in enumerate(self.midi_player.tracks_info):
                if 'notes' in track and track['notes']:
                    track_notes = track['notes']
                    min_note = min(track_notes)
                    max_note = max(track_notes)
                    adjusted_min = min_note + self.midi_player.note_offset
                    adjusted_max = max_note + self.midi_player.note_offset
                    playable_notes = sum(1 for note in track_notes 
                                       if 36 <= (note + self.midi_player.note_offset) <= 96)
                    track_text = (f"◇ 音轨 {i} [原始范围: {min_note}-{max_note}, "
                                f"调整后: {adjusted_min}-{adjusted_max}, "
                                f"可播放: {playable_notes}/{len(track_notes)}]")
                    self.tracks_list.addItem(track_text)
            
            # 默认选择全部音轨
            if self.tracks_list.count() > 0:
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
            
            # 如果正在预览，重新开始预览
            if self.is_previewing:
                self.stop_preview()
                self.start_preview()
            
        except Exception as e:
            print(f"选择音轨时出错: {str(e)}")
            # 发生错误时重置为全部音轨
            self.tracks_list.setCurrentRow(0)
            self.midi_player.set_track(None)

    @handle_error("过滤歌曲")
    def filter_songs(self, text):
        """根据搜索文本过滤歌曲列表"""
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

    def toggle_play(self):
        """切换播放/暂停状态"""
        try:
            if not self.midi_player.playing:
                self.start_playback()
            else:
                self.pause_playback()
        except Exception as e:
            print(f"切换播放状态时出错: {str(e)}")

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.AltModifier:  # 检查是否按下 Alt 键
            if event.key() == Qt.Key_Minus:  # 减号键
                self.pause_playback()
            elif event.key() == Qt.Key_Equal:  # 等号键
                self.stop_playback()
            elif event.key() == Qt.Key_Up:  # 上箭头
                self.change_song(-1)
            elif event.key() == Qt.Key_Down:  # 下箭头
                self.change_song(1)

    def update_ui(self, update_type):
        """统一处理UI更新"""
        if update_type == "playback":
            self.update_button_states()
            if not self.progress_timer.isActive():
                self.progress_timer.start()
        elif update_type == "stop":
            self.update_button_states()
            if self.progress_timer.isActive():
                self.progress_timer.stop()
            self.time_label.setText("剩余时间: 00:00")
        # ... 其他更新类型 ...

    def load_directory(self, dir_path):
        """加载指定目录的MIDI文件"""
        self.midi_files = self._load_midi_files(dir_path)
        self.search_input.clear()
        self.update_song_list()

    def update_song_list(self):
        """更新歌曲列表显示"""
        self.song_list.clear()
        for file in self.midi_files:
            self.song_list.addItem(os.path.basename(file))

    @pyqtSlot()
    def update_ui_after_playback(self):
        """在播放开始后更新UI状态"""
        self.update_ui_state("play")

    @pyqtSlot()
    def update_ui_after_stop(self):
        """停止播放后更新UI"""
        self.update_ui_state("stop")

    @pyqtSlot()
    def update_ui_after_pause(self):
        """暂停播放后更新UI"""
        self.update_ui_state("pause")

    def toggle_preview(self):
        """切换预览状态"""
        try:
            if not self.is_previewing:
                self.start_preview()
            else:
                self.stop_preview()
        except Exception as e:
            print(f"切换预览状态时出错: {str(e)}")

    def start_preview(self):
        """开始预览MIDI文件"""
        try:
            if self.current_index < 0 or not self.midi_files:
                return
            
            current_file = self.midi_files[self.current_index]
            
            # 停止当前播放
            pygame.mixer.music.stop()
            
            try:
                # 获取当前选中的音轨
                current_row = self.tracks_list.currentRow()
                if current_row < 0:
                    return
                
                # 创建临时MIDI文件用于预览
                mid = mido.MidiFile(current_file)
                preview_mid = mido.MidiFile()
                preview_mid.ticks_per_beat = mid.ticks_per_beat
                
                # 创建一个包含所有控制消息的轨道
                control_track = mido.MidiTrack()
                
                # 如果选择"全部音轨"（索引0），则添加所有音轨
                if current_row == 0:
                    # 首先收集所有控制消息
                    for track in mid.tracks:
                        for msg in track:
                            # 复制所有控制类消息到控制轨道
                            if msg.type in ['set_tempo', 'time_signature', 'key_signature', 
                                          'program_change', 'control_change']:
                                control_track.append(msg.copy())
                    
                    # 添加控制轨道
                    preview_mid.tracks.append(control_track)
                    
                    # 然后添加所有音轨的音符（应用音高调整）
                    for track in mid.tracks:
                        track_copy = mido.MidiTrack()
                        for msg in track:
                            if msg.type == 'note_on' or msg.type == 'note_off':
                                msg_copy = msg.copy()
                                # 只对 note_on 和 note_off 消息调整音高
                                adjusted_note = self.midi_player._adjust_note(msg.note)
                                if self.midi_player.PLAYABLE_MIN <= adjusted_note <= self.midi_player.PLAYABLE_MAX:
                                    msg_copy.note = adjusted_note
                                    track_copy.append(msg_copy)
                        if len(track_copy) > 0:  # 只添加包含音符的音轨
                            preview_mid.tracks.append(track_copy)
                else:
                    # 否则只添加选中的音轨
                    track_index = current_row - 1  # 减1是因为第一项是"全部音轨"
                    if 0 <= track_index < len(mid.tracks):
                        # 首先添加原始轨道的控制消息
                        for msg in mid.tracks[track_index]:
                            if msg.type in ['set_tempo', 'time_signature', 'key_signature', 
                                          'program_change', 'control_change']:
                                control_track.append(msg.copy())
                        preview_mid.tracks.append(control_track)
                        
                        # 然后添加音符消息（应用音高调整）
                        track_copy = mido.MidiTrack()
                        for msg in mid.tracks[track_index]:
                            if msg.type == 'note_on' or msg.type == 'note_off':
                                msg_copy = msg.copy()
                                # 只对 note_on 和 note_off 消息调整音高
                                adjusted_note = self.midi_player._adjust_note(msg.note)
                                if self.midi_player.PLAYABLE_MIN <= adjusted_note <= self.midi_player.PLAYABLE_MAX:
                                    msg_copy.note = adjusted_note
                                    track_copy.append(msg_copy)
                        if len(track_copy) > 0:
                            preview_mid.tracks.append(track_copy)
                
                # 确保至少有一个音轨
                if len(preview_mid.tracks) < 1:
                    print("没有找到可播放的音轨")
                    return
                
                # 创建临时文件
                temp_dir = os.path.dirname(current_file)
                if not os.path.exists(temp_dir):
                    temp_dir = os.path.dirname(os.path.abspath(__file__))
                temp_file = os.path.join(temp_dir, f"_temp_preview_{os.path.basename(current_file)}")
                
                try:
                    preview_mid.save(temp_file)
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    
                    # 更新状态和按钮
                    self.is_previewing = True
                    self.preview_button.setText("停止预览")
                    self.preview_button.setStyleSheet("""
                        QPushButton {
                            background-color: #d9534f;
                            color: white;
                            border: 1px solid #d43f3a;
                        }
                        QPushButton:hover {
                            background-color: #c9302c;
                            border-color: #ac2925;
                        }
                    """)
                finally:
                    # 确保在加载后删除临时文件
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception as e:
                        print(f"删除临时文件时出错: {str(e)}")
                
            except Exception as e:
                print(f"预览MIDI文件时出错: {str(e)}")
                self.stop_preview()
                
        except Exception as e:
            print(f"开始预览时出错: {str(e)}")
            self.stop_preview()

    def stop_preview(self):
        """停止预览"""
        try:
            pygame.mixer.music.stop()
            self.is_previewing = False
            self.preview_button.setText("预览")
            self.preview_button.setStyleSheet("")
        except Exception as e:
            print(f"停止预览时出错: {str(e)}")

    def load_tracks(self, midi_file):
        """加载MIDI文件的音轨信息"""
        try:
            self.tracks_list.clear()
            mid = mido.MidiFile(midi_file)
            
            # 添加"全部音轨"选项
            all_notes = []  # 存储所有音轨的所有音符事件
            track_notes_dict = {}  # 用字典存储每个音轨的音符信息
            
            # 首先统计所有音轨的音符信息
            for i, track in enumerate(mid.tracks):
                track_notes = []  # 存储当前音轨的所有音符事件（包括重复音符）
                
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:  # 只统计 note_on 事件
                        track_notes.append(msg.note)
                        all_notes.append(msg.note)
            
                if track_notes:  # 只处理包含音符的音轨
                    track_notes_dict[i] = track_notes
            
            # 计算全部音轨的统计信息
            if all_notes:  # 使用所有音符事件
                min_note = min(all_notes)
                max_note = max(all_notes)
                total_notes = len(all_notes)  # 所有音符事件的总数
                playable_notes = sum(1 for note in all_notes 
                                   if 36 <= (note + self.midi_player.note_offset) <= 96)
                
                # 添加全部音轨选项
                adjusted_min = min_note + self.midi_player.note_offset
                adjusted_max = max_note + self.midi_player.note_offset
                all_tracks_text = (f"全部音轨 [原始范围: {min_note}-{max_note}, "
                                 f"调整后: {adjusted_min}-{adjusted_max}, "
                                 f"可播放: {playable_notes}/{total_notes}]")
                self.tracks_list.addItem(all_tracks_text)
            
            # 添加单个音轨
            for i, track_notes in track_notes_dict.items():
                if track_notes:  # 确保音轨有音符
                    min_note = min(track_notes)
                    max_note = max(track_notes)
                    total_notes = len(track_notes)  # 使用所有音符事件的数量
                    playable_notes = sum(1 for note in track_notes 
                                       if 36 <= (note + self.midi_player.note_offset) <= 96)
                    
                    track_text = (f"音轨 {i} [原始范围: {min_note}-{max_note}, "
                                f"调整后: {min_note + self.midi_player.note_offset}-"
                                f"{max_note + self.midi_player.note_offset}, "
                                f"可播放: {playable_notes}/{total_notes}]")
                    self.tracks_list.addItem(track_text)
            
            # 默认选择第一个音轨
            if self.tracks_list.count() > 0:
                self.tracks_list.setCurrentRow(0)
                
        except Exception as e:
            print(f"加载音轨时出错: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 