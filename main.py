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
        
        # 初始化预览状态
        self.is_previewing = False
        
        # 初始化pygame mixer（如果还没有初始化）
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100)
            except Exception as e:
                print(f"初始化音频系统失败: {str(e)}")
        
        # 初始化其他属性
        self.current_index = -1
        self.midi_files = []
        self.midi_player = MidiPlayer()
        # 连接窗口切换失败信号
        self.midi_player.window_switch_failed.connect(self.handle_window_switch_failed)
        
        # 用于更新进度条的计时器
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.setInterval(100)  # 每100ms更新一次
        
        # 预览按钮
        self.preview_button = QPushButton("预览")
        self.preview_button.clicked.connect(self.toggle_preview)
        self.preview_button.setEnabled(False)  # 初始状态禁用
        
        # 添加窗口状态检查定时器
        self.window_check_timer = QTimer()
        self.window_check_timer.timeout.connect(self.check_window_state)
        self.window_check_timer.start(200)  # 每200ms检查一次
        
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
        """关闭窗口时的处理"""
        try:
            # 停止预览
            if hasattr(self, 'is_previewing') and self.is_previewing:
                self.stop_preview()
            
            # 停止播放
            if hasattr(self, 'midi_player'):
                self.midi_player.stop()
            
            # 保存配置
            if hasattr(self, 'config'):
                self.config['last_directory'] = self.last_directory
                self.config_manager.save(self.config)
            
            event.accept()
            
        except Exception as e:
            print(f"关闭窗口时出错: {str(e)}")
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
        try:
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
            
            # 创建音轨详情区域的垂直布局
            tracks_layout = QVBoxLayout()
            
            # 修改音轨列表标签为详情展示
            tracks_label = QLabel("音轨详情")
            tracks_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: #333333;
                    padding: 5px;
                }
            """)
            tracks_layout.addWidget(tracks_label)
            
            # 添加当前歌曲名称标签
            self.current_song_label = QLabel("当前歌曲：未选择")
            self.current_song_label.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    color: #666666;
                    padding: 2px 5px;
                }
            """)
            tracks_layout.addWidget(self.current_song_label)
            
            # 创建音轨列表
            self.tracks_list = QListWidget()
            self.tracks_list.itemSelectionChanged.connect(self.track_selected)
            tracks_layout.addWidget(self.tracks_list)
            
            right_layout.addLayout(tracks_layout)
            
            # 添加时间显示
            self.time_label = QLabel("剩余时间: 00:00")
            self.time_label.setAlignment(Qt.AlignCenter)
            self.time_label.setStyleSheet("QLabel { padding: 5px; }")
            right_layout.addWidget(self.time_label)
            
            # 修改控制按钮布局
            control_layout = QHBoxLayout()
            
            # 播放/暂停按钮
            self.play_button = QPushButton("播放")
            self.play_button.setEnabled(False)
            self.play_button.clicked.connect(self.toggle_play)
            control_layout.addWidget(self.play_button)
            
            # 停止按钮
            self.stop_button = QPushButton("停止")
            self.stop_button.setEnabled(False)
            self.stop_button.clicked.connect(self.stop_playback)
            control_layout.addWidget(self.stop_button)
            
            # 预览按钮
            self.preview_button = QPushButton("预览")
            self.preview_button.clicked.connect(self.toggle_preview)
            self.preview_button.setEnabled(False)
            control_layout.addWidget(self.preview_button)
            
            right_layout.addLayout(control_layout)
            
            # 添加说明文字（移到底部）
            right_layout.addStretch()
            
            # 添加使用说明
            usage_label = QLabel("注意：工具支持36键模式!\n使用说明：\n1. 使用管理员权限启动\n2. 选择MIDI文件\n3. 选择要播放的音轨\n4. 点击播放按钮开始演奏")
            usage_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
            right_layout.addWidget(usage_label)
            
            # 添加快捷键说明
            shortcut_label = QLabel("快捷键说明：\nAlt + 减号键(-) 播放/暂停\nAlt + 等号键(=) 停止播放")
            shortcut_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
            right_layout.addWidget(shortcut_label)
            
            main_layout.addWidget(right_widget)
            
        except Exception as e:
            print(f"设置UI界面时出错: {str(e)}")

    def setup_keyboard_hooks(self):
        """设置键盘快捷键"""
        try:
            # 播放/暂停
            keyboard.add_hotkey(CONTROL_KEYS['START_PAUSE'], self.toggle_play, 
                              suppress=True, trigger_on_release=True)
            
            # 停止
            keyboard.add_hotkey(CONTROL_KEYS['STOP'], self.stop_playback,
                              suppress=True, trigger_on_release=True)
            
            print("键盘快捷键设置完成")
            
        except Exception as e:
            print(f"设置键盘快捷键时出错: {str(e)}")

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
                    self.play_button.setEnabled(True)
                    self.stop_button.setEnabled(True)
                    self.play_button.setText("播放")
                    self.play_button.setStyleSheet("""
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
                self.play_button.setEnabled(True)
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
            self.play_button.setEnabled(has_file)
            if is_playing:
                if is_paused:  # 如果暂停中
                    self.play_button.setText("继续")
                else:  # 如果正在播放
                    self.play_button.setText("暂停")
                self.play_button.setStyleSheet("""
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
                self.play_button.setText("播放")
                self.play_button.setStyleSheet("")
            
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
            
            # 确保停止当前播放
            self.midi_player.stop()
            
            # 启动播放线程
            self.play_thread = threading.Thread(
                target=self.midi_player.play_midi,
                args=(current_file, current_row),
                daemon=True
            )
            self.play_thread.start()
            
            # 更新UI状态
            self.update_ui("playback")
            print("开始播放")
            
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
        """停止播放"""
        try:
            self.midi_player.stop()
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=1.0)
            self.play_thread = None
            self.update_ui("stop")
            print("停止播放")
        except Exception as e:
            print(f"停止播放时出错: {str(e)}")

    def pause_playback(self):
        """暂停播放"""
        try:
            if not self.midi_player.playing:
                return
            
            if self.midi_player.paused:
                # 如果当前是暂停状态，尝试恢复播放
                if self.midi_player.resume():
                    self.update_ui("playback")  # 更新为播放状态
                    print("继续播放")
                else:
                    # 如果恢复失败（比如找不到窗口），则停止播放
                    self.stop_playback()
                    print("无法恢复播放，已停止")
            else:
                # 如果当前是播放状态，尝试暂停
                if self.midi_player.pause():
                    self.update_ui("pause")  # 更新为暂停状态
                    print("暂停播放")
                
        except Exception as e:
            print(f"暂停播放时出错: {str(e)}")

    def change_song(self, delta):
        """切换歌曲"""
        try:
            if not self.midi_files:
                return
                
            # 停止当前播放
            self.stop_playback()  # 这会触发UI更新
            
            # 计算新的索引
            new_index = (self.current_index + delta) % len(self.midi_files)
            if new_index < 0:
                new_index = len(self.midi_files) - 1
                
            print(f"切换歌曲: 当前索引 {self.current_index}, 新索引 {new_index}")
            
            # 更新索引和UI
            self.current_index = new_index
            self.song_list.setCurrentRow(new_index)
            
            # 自动开始播放新选择的歌曲
            self.start_playback()
            
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
        """更新音轨列表显示"""
        try:
            self.tracks_list.clear()
            
            # 更新当前歌曲名称
            if 0 <= self.current_index < len(self.midi_files):
                current_song = os.path.basename(self.midi_files[self.current_index])
                self.current_song_label.setText(f"当前歌曲：{current_song}")
            else:
                self.current_song_label.setText("当前歌曲：未选择")
                return  # 如果没有选择歌曲，直接返回
            
            # 获取当前MIDI文件
            current_file = self.midi_files[self.current_index]
            mid = mido.MidiFile(current_file)
            
            # 获取所有音轨的音符信息
            all_notes = []
            track_notes_dict = {}
            
            # 首先统计所有音轨的音符信息
            for i, track in enumerate(mid.tracks):
                track_notes = []
                track_velocities = []
                
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        track_notes.append(msg.note)
                        track_velocities.append(msg.velocity)
                        all_notes.append(msg.note)
                
                if track_notes:  # 只处理包含音符的音轨
                    track_notes_dict[i] = {
                        'notes': track_notes,
                        'velocity': track_velocities,
                        'channel': getattr(msg, 'channel', 0)
                    }
            
            # 计算全部音轨的统计信息
            if all_notes:
                min_note = min(all_notes)
                max_note = max(all_notes)
                total_notes = len(all_notes)
                playable_notes = sum(1 for note in all_notes 
                                   if 36 <= (note + self.midi_player.note_offset) <= 96)
                
                # 计算平均力度
                all_velocities = []
                for track_info in track_notes_dict.values():
                    all_velocities.extend(track_info['velocity'])
                avg_velocity = sum(all_velocities) / len(all_velocities) if all_velocities else 0
                
                # 添加全部音轨选项，包含详细信息
                all_tracks_text = (
                    f"◆ 全部音轨 [音符总数: {total_notes}]\n"
                    f"├ 音符范围: {min_note}-{max_note} → {min_note + self.midi_player.note_offset}-"
                    f"{max_note + self.midi_player.note_offset}\n"
                    f"├ 可播放: {playable_notes}/{total_notes} ({playable_notes/total_notes*100:.1f}%)\n"
                    f"└ 平均力度: {avg_velocity:.1f}"
                )
                self.tracks_list.addItem(all_tracks_text)
                
                # 添加各个音轨的详细信息
                for i, track_info in track_notes_dict.items():
                    track_notes = track_info['notes']
                    velocities = track_info['velocity']
                    channel = track_info['channel']
                    
                    min_note = min(track_notes)
                    max_note = max(track_notes)
                    total_notes = len(track_notes)
                    playable_notes = sum(1 for note in track_notes 
                                       if 36 <= (note + self.midi_player.note_offset) <= 96)
                    avg_velocity = sum(velocities) / len(velocities) if velocities else 0
                    
                    track_text = (
                        f"◇ 音轨 {i} [音符数: {total_notes}, 通道: {channel}]\n"
                        f"├ 音符范围: {min_note}-{max_note} → "
                        f"{min_note + self.midi_player.note_offset}-{max_note + self.midi_player.note_offset}\n"
                        f"├ 可播放: {playable_notes}/{total_notes} ({playable_notes/total_notes*100:.1f}%)\n"
                        f"└ 平均力度: {avg_velocity:.1f}"
                    )
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

    def update_ui(self, state):
        """更新UI状态"""
        try:
            if state == "playback":
                # 播放状态，显示暂停按钮
                self.play_button.setText("暂停")
                self.play_button.setStyleSheet("""
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
                self.stop_button.setEnabled(True)
                self.preview_button.setEnabled(False)
                
            elif state == "pause":
                # 暂停状态，显示继续按钮
                self.play_button.setText("继续")
                self.play_button.setStyleSheet("""
                    QPushButton {
                        background-color: #5bc0de;
                        color: white;
                        border: 1px solid #46b8da;
                    }
                    QPushButton:hover {
                        background-color: #31b0d5;
                        border-color: #269abc;
                    }
                """)
                self.stop_button.setEnabled(True)
                self.preview_button.setEnabled(False)
                
            elif state == "stop":
                # 停止状态，显示播放按钮
                self.play_button.setText("播放")
                self.play_button.setStyleSheet("""
                    QPushButton {
                        background-color: #5cb85c;
                        color: white;
                        border: 1px solid #4cae4c;
                    }
                    QPushButton:hover {
                        background-color: #449d44;
                        border-color: #398439;
                    }
                    QPushButton:disabled {
                        background-color: #f0f0f0;
                        color: #888;
                        border: 1px solid #ccc;
                    }
                """)
                self.stop_button.setEnabled(False)
                self.preview_button.setEnabled(True)
                
                # 重置播放状态
                if hasattr(self, 'midi_player'):
                    self.midi_player.playing = False
                    self.midi_player.paused = False
                
        except Exception as e:
            print(f"更新UI状态时出错: {str(e)}")

    def check_window_state(self):
        """定期检查窗口状态并更新UI"""
        try:
            if self.midi_player.playing:
                if self.midi_player.auto_paused:
                    self.update_ui("pause")  # 自动暂停时更新UI
                elif not self.midi_player.paused:  # 如果不是暂停状态，确保显示为播放状态
                    self.update_ui("playback")
                elif self.midi_player.paused and not self.midi_player.auto_paused:
                    # 如果是手动暂停状态，确保显示为暂停状态
                    self.update_ui("pause")
        except Exception as e:
            print(f"检查窗口状态时出错: {str(e)}")

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
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            
            # 获取当前选中的音轨
            current_row = self.tracks_list.currentRow()
            if current_row < 0:
                return
            
            # 加载MIDI文件
            mid = mido.MidiFile(current_file)
            
            # 创建临时MIDI文件用于预览
            preview_mid = mido.MidiFile()
            preview_mid.ticks_per_beat = mid.ticks_per_beat
            
            # 创建控制轨道
            control_track = mido.MidiTrack()
            preview_mid.tracks.append(control_track)
            
            # 处理音轨
            if current_row == 0:  # 全部音轨
                for track in mid.tracks:
                    track_copy = mido.MidiTrack()
                    for msg in track:
                        if msg.type in ['note_on', 'note_off']:
                            msg_copy = msg.copy()
                            if hasattr(msg, 'note'):
                                adjusted_note = msg.note + self.midi_player.note_offset
                                if 36 <= adjusted_note <= 96:
                                    msg_copy.note = adjusted_note
                                    track_copy.append(msg_copy)
                        elif msg.type in ['set_tempo', 'time_signature']:
                            control_track.append(msg.copy())
                    if len(track_copy) > 0:
                        preview_mid.tracks.append(track_copy)
            else:  # 单个音轨
                track_index = current_row - 1
                if track_index < len(mid.tracks):
                    track = mid.tracks[track_index]
                    track_copy = mido.MidiTrack()
                    for msg in track:
                        if msg.type in ['note_on', 'note_off']:
                            msg_copy = msg.copy()
                            if hasattr(msg, 'note'):
                                adjusted_note = msg.note + self.midi_player.note_offset
                                if 36 <= adjusted_note <= 96:
                                    msg_copy.note = adjusted_note
                                    track_copy.append(msg_copy)
                        elif msg.type in ['set_tempo', 'time_signature']:
                            control_track.append(msg.copy())
                    if len(track_copy) > 0:
                        preview_mid.tracks.append(track_copy)
            
            if len(preview_mid.tracks) <= 1:  # 只有控制轨道
                print("没有可播放的音符")
                return
            
            # 修改临时文件的创建方式：直接在当前目录创建
            temp_file = f"_preview_{os.path.basename(current_file)}"
            
            try:
                # 如果已存在同名临时文件，先删除
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception as e:
                        print(f"删除已存在的临时文件失败: {str(e)}")
                        return
                    
                # 保存并播放预览文件
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
                
                # 添加预览完成检测
                self.preview_check_timer = QTimer()
                self.preview_check_timer.timeout.connect(self.check_preview_status)
                self.preview_check_timer.start(100)  # 每100ms检查一次
                
            finally:
                # 设置延迟删除临时文件
                QTimer.singleShot(1000, lambda: self.cleanup_temp_file(temp_file))
                
        except Exception as e:
            print(f"预览时出错: {str(e)}")
            self.stop_preview()

    def check_preview_status(self):
        """检查预览播放状态"""
        if self.is_previewing and not pygame.mixer.music.get_busy():
            self.stop_preview()
            if hasattr(self, 'preview_check_timer') and self.preview_check_timer.isActive():
                self.preview_check_timer.stop()

    def cleanup_temp_file(self, file_path):
        """清理临时文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"清理临时文件失败: {str(e)}")

    def stop_preview(self):
        """停止预览"""
        try:
            pygame.mixer.music.stop()
            self.is_previewing = False
            self.preview_button.setText("预览")
            # 设置默认样式而不是清空样式表
            self.preview_button.setStyleSheet("""
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
                QPushButton:disabled {
                    background-color: #f0f0f0;
                    color: #888;
                    border: 1px solid #ccc;
                }
            """)
            
            # 停止预览状态检查定时器
            if hasattr(self, 'preview_check_timer') and self.preview_check_timer.isActive():
                self.preview_check_timer.stop()
            
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

    def song_list_clicked(self):
        """处理歌曲列表点击事件"""
        try:
            # 检查是否在播放或暂停状态
            if self.midi_player.playing:
                # 显示提示信息
                print("请先停止当前播放再选择新歌曲")
                # 恢复之前的选中状态
                if 0 <= self.current_index < self.song_list.count():
                    self.song_list.setCurrentRow(self.current_index)
                return
            
            new_index = self.song_list.currentRow()
            if new_index != self.current_index:
                # 更新索引
                self.current_index = new_index
                print(f"选择新歌曲: 索引 {new_index}")
                
                # 更新音轨列表
                if 0 <= new_index < len(self.midi_files):
                    try:
                        mid = mido.MidiFile(self.midi_files[new_index])
                        self.midi_player.analyze_tracks(mid)
                        self.update_tracks_list()
                    except Exception as e:
                        print(f"加载MIDI文件失败: {str(e)}")
                        return
                
                # 启用播放按钮
                self.play_button.setEnabled(True)
                self.stop_button.setEnabled(False)  # 新选择歌曲时停止按钮应该禁用
                self.preview_button.setEnabled(True)
                
                # 如果正在预览，停止预览
                if self.is_previewing:
                    self.stop_preview()
                
        except Exception as e:
            print(f"处理歌曲选择时出错: {str(e)}")

    def handle_window_switch_failed(self):
        """处理窗口切换失败的情况"""
        try:
            # 停止播放
            self.stop_playback()
            # 更新UI状态
            self.update_ui("stop")
            print("由于无法找到目标窗口，已停止播放")
        except Exception as e:
            print(f"处理窗口切换失败时出错: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 