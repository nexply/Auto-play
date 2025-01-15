import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from midi_player import MidiPlayer
import json
import time
import keyboard
from keyboard_mapping import CONTROL_KEYS

CONFIG_FILE = "config.json"

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("燕云-自动演奏")
        self.root.geometry("800x600")
        
        # 初始化播放器和状态变量
        self.midi_player = MidiPlayer()
        self.midi_files = []
        self.current_index = -1
        self.last_key_time = 0
        self.key_cooldown = 0.2
        
        # 加载配置
        self.config = self.load_config()
        self.last_directory = self.config.get('last_directory', '')
        
        self.setup_ui()
        self.setup_keyboard_hooks()
        
        # 如果有上次的目录，自动加载
        if self.last_directory:
            self.refresh_midi_files()
        
        # 更新进度的定时器
        self.update_progress()
        
        # 设置窗口关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_ui(self):
        # 主布局
        main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板
        left_frame = ttk.Frame(main_frame)
        main_frame.add(left_frame)
        
        # 置顶复选框
        self.stay_on_top_var = tk.BooleanVar(value=self.config.get('stay_on_top', False))
        stay_on_top_cb = ttk.Checkbutton(left_frame, text="窗口置顶", 
                                        variable=self.stay_on_top_var,
                                        command=self.toggle_stay_on_top)
        stay_on_top_cb.pack(pady=5)
        
        # 选择文件夹按钮
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(pady=5)
        
        select_btn = ttk.Button(button_frame, text="选择MIDI文件夹", 
                              command=self.select_directory)
        select_btn.pack(side=tk.LEFT, padx=2)
        
        refresh_btn = ttk.Button(button_frame, text="刷新文件", 
                               command=self.refresh_midi_files)
        refresh_btn.pack(side=tk.LEFT, padx=2)
        
        # 搜索框
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.filter_songs())
        search_entry = ttk.Entry(left_frame, textvariable=self.search_var)
        search_entry.pack(pady=5, fill=tk.X)
        
        # 歌曲列表
        self.song_list = tk.Listbox(left_frame)
        self.song_list.pack(fill=tk.BOTH, expand=True, pady=5)
        self.song_list.bind('<<ListboxSelect>>', self.song_selected)
        
        # 右侧面板
        right_frame = ttk.Frame(main_frame)
        main_frame.add(right_frame)
        
        # 音轨选择
        ttk.Label(right_frame, text="选择音轨:").pack(pady=5)
        self.tracks_list = tk.Listbox(right_frame)
        self.tracks_list.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tracks_list.bind('<<ListboxSelect>>', self.track_selected)
        
        # 时间显示
        self.time_label = ttk.Label(right_frame, text="剩余时间: 00:00")
        self.time_label.pack(pady=5)
        
        # 控制按钮
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(pady=5)
        
        self.play_btn = ttk.Button(control_frame, text="播放", 
                                 command=self.toggle_play, state=tk.DISABLED)
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(control_frame, text="暂停", 
                                  command=self.pause_playback, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="停止", 
                                 command=self.stop_playback, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # 预览控制按钮
        preview_frame = ttk.Frame(control_frame)
        preview_frame.pack(side=tk.LEFT, padx=5)
        
        self.preview_original_btn = ttk.Button(preview_frame, text="预览原始", 
                                             command=lambda: self.toggle_preview(True),
                                             state=tk.DISABLED)
        self.preview_original_btn.pack(side=tk.LEFT, padx=2)
        
        self.preview_adjusted_btn = ttk.Button(preview_frame, text="预览调整", 
                                             command=lambda: self.toggle_preview(False),
                                             state=tk.DISABLED)
        self.preview_adjusted_btn.pack(side=tk.LEFT, padx=2)
        
        # 使用说明
        ttk.Label(right_frame, text="使用说明：\n"
                 "1. 使用管理员权限启动\n"
                 "2. 选择MIDI文件\n"
                 "3. 选择要播放的音轨\n"
                 "4. 点击播放按钮开始演奏").pack(pady=10)
                 
        ttk.Label(right_frame, text="快捷键说明：\n"
                 "减号键(-) - 播放/暂停\n"
                 "等号键(=) - 停止播放\n"
                 "方向键上 - 上一首\n"
                 "方向键下 - 下一首\n"
                 "ESC键 - 强制停止弹奏").pack(pady=10)
        
        # 添加参数调整面板
        params_frame = ttk.LabelFrame(right_frame, text="音域优化参数")
        params_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # 权重调整滑块
        self.weight_vars = {}
        weights_frame = ttk.Frame(params_frame)
        weights_frame.pack(fill=tk.X, pady=5)
        
        # 创建权重调整滑块
        weight_names = {
            'coverage': '音符覆盖率',
            'density': '音符密度',
            'melody': '旋律线条',
            'transition': '音符跳转',
            'pentatonic': '五声音阶',
            'octave_balance': '八度平衡'
        }
        
        for key, name in weight_names.items():
            frame = ttk.Frame(weights_frame)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(frame, text=f"{name}:").pack(side=tk.LEFT, padx=5)
            self.weight_vars[key] = tk.DoubleVar(value=self.midi_player.note_optimizer.weights[key])
            scale = ttk.Scale(frame, from_=0.0, to=1.0, 
                             variable=self.weight_vars[key],
                             command=lambda *args, k=key: self.update_weight(k))
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # 显示具体数值
            value_label = ttk.Label(frame, width=4)
            value_label.pack(side=tk.LEFT, padx=5)
            self.weight_vars[key].trace('w', 
                lambda *args, l=value_label, v=self.weight_vars[key]: 
                l.configure(text=f"{v.get():.2f}"))
        
        # 八度权重调整
        octaves_frame = ttk.LabelFrame(params_frame, text="八度区域权重")
        octaves_frame.pack(fill=tk.X, pady=5)
        
        self.octave_vars = {}
        octave_names = {
            'low': '低音区',
            'middle': '中音区',
            'high': '高音区'
        }
        
        for key, name in octave_names.items():
            frame = ttk.Frame(octaves_frame)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(frame, text=f"{name}:").pack(side=tk.LEFT, padx=5)
            self.octave_vars[key] = tk.DoubleVar(value=0.33)  # 默认平均分配
            scale = ttk.Scale(frame, from_=0.0, to=1.0,
                             variable=self.octave_vars[key],
                             command=lambda *args, k=key: self.update_octave_weight(k))
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            value_label = ttk.Label(frame, width=4)
            value_label.pack(side=tk.LEFT, padx=5)
            self.octave_vars[key].trace('w',
                lambda *args, l=value_label, v=self.octave_vars[key]:
                l.configure(text=f"{v.get():.2f}"))
        
        # 添加重置按钮
        ttk.Button(params_frame, text="重置为默认值",
                   command=self.reset_optimization_params).pack(pady=5)

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 默认配置
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
                'stay_on_top': self.stay_on_top_var.get()
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")

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
            # 修改为强制停止弹奏
            keyboard.on_press_key(CONTROL_KEYS['FORCE_STOP'], 
                                lambda e: self.safe_key_handler(self.force_stop_playback), 
                                suppress=True)
        except Exception as e:
            print(f"设置键盘钩子时出错: {str(e)}")

    def safe_key_handler(self, func):
        """安全地处理键盘事件，添加防抖动"""
        try:
            current_time = time.time()
            if current_time - self.last_key_time < self.key_cooldown:
                return
            
            self.last_key_time = current_time
            func()
        except Exception as e:
            print(f"处理键盘事件时出错: {str(e)}")

    def select_directory(self):
        """选择MIDI文件夹"""
        try:
            dir_path = filedialog.askdirectory(
                title="选择MIDI文件夹",
                initialdir=self.last_directory
            )
            
            if dir_path:
                # 更新最后访问的目录
                self.last_directory = dir_path
                self.save_config()
                
                # 刷新文件列表
                self.refresh_midi_files()
                
        except Exception as e:
            print(f"选择文件夹时出错: {str(e)}")
            messagebox.showerror("错误", f"选择文件夹时出错: {str(e)}")

    def song_selected(self, event=None):
        """处理歌曲选择"""
        try:
            selection = self.song_list.curselection()
            if not selection:
                return
            
            index = selection[0]
            if 0 <= index < len(self.midi_files):
                self.current_index = index
                
                try:
                    # 加载MIDI文件并分析音轨
                    import mido
                    mid = mido.MidiFile(self.midi_files[index])
                    self.midi_player.analyze_tracks(mid)
                    self.update_tracks_list()
                except Exception as e:
                    print(f"加载MIDI文件时出错: {str(e)}")
                    messagebox.showerror("错误", f"加载MIDI文件时出错: {str(e)}")
                    return
                
                # 启用控制按钮
                self.enable_buttons()
        except Exception as e:
            print(f"选择歌曲时出错: {str(e)}")

    def update_tracks_list(self):
        """更新音轨列表"""
        try:
            self.tracks_list.delete(0, tk.END)
            
            # 添加"全部音轨"选项
            self.tracks_list.insert(tk.END, "◆ 全部音轨")
            
            # 添加各个音轨信息
            if hasattr(self.midi_player, 'tracks_info'):
                for track in self.midi_player.tracks_info:
                    track_info = f"◇ {track['name']} [音符: {track['notes_count']}]"
                    self.tracks_list.insert(tk.END, track_info)
            
            # 默认选择全部音轨
            self.tracks_list.selection_set(0)
            self.midi_player.set_track(None)
        except Exception as e:
            print(f"更新音轨列表时出错: {str(e)}")

    def track_selected(self, event=None):
        """处理音轨选择"""
        try:
            selection = self.tracks_list.curselection()
            if not selection:
                return
            
            current_row = selection[0]
            
            # 检查是否选择了"全部音轨"
            if current_row == 0:
                self.midi_player.set_track(None)
            else:
                # 设置选中的音轨
                if current_row - 1 < len(self.midi_player.tracks_info):
                    channel = self.midi_player.tracks_info[current_row - 1]['channel']
                    self.midi_player.set_track(channel)
            
            # 如果正在播放，重新开始播放选中的音轨
            if self.midi_player.playing:
                self.stop_playback()
                self.start_playback()
        except Exception as e:
            print(f"选择音轨时出错: {str(e)}")

    def enable_buttons(self):
        """启用控制按钮"""
        self.play_btn['state'] = tk.NORMAL
        self.pause_btn['state'] = tk.NORMAL
        self.stop_btn['state'] = tk.NORMAL
        self.preview_original_btn['state'] = tk.NORMAL
        self.preview_adjusted_btn['state'] = tk.NORMAL

    def disable_buttons(self):
        """禁用控制按钮"""
        self.play_btn['state'] = tk.DISABLED
        self.pause_btn['state'] = tk.DISABLED
        self.stop_btn['state'] = tk.DISABLED
        self.preview_original_btn['state'] = tk.DISABLED
        self.preview_adjusted_btn['state'] = tk.DISABLED

    def toggle_stay_on_top(self):
        """切换窗口置顶状态"""
        if self.stay_on_top_var.get():
            self.root.attributes('-topmost', True)
        else:
            self.root.attributes('-topmost', False)
        self.save_config()
        
    def format_time(self, seconds):
        """将秒数格式化为 mm:ss 格式"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def update_progress(self):
        """更新进度显示"""
        try:
            if self.midi_player.playing and not self.midi_player.paused:
                current_time = self.midi_player.get_current_time()
                total_time = self.midi_player.get_total_time()
                
                if total_time > 0:
                    remaining_time = max(0, total_time - current_time)
                    self.time_label['text'] = f"剩余时间: {self.format_time(remaining_time)}"
                    
                    # 如果播放结束，自动停止
                    if remaining_time == 0:
                        self.stop_playback()
            
            # 继续更新进度
            self.root.after(100, self.update_progress)
        except Exception as e:
            print(f"更新进度时出错: {str(e)}")

    def start_playback(self):
        """开始播放"""
        try:
            if self.current_index >= 0:
                self.midi_player.play_file(self.midi_files[self.current_index])
                self.update_button_states()
        except Exception as e:
            print(f"开始播放时出错: {str(e)}")
            messagebox.showerror("错误", f"开始播放时出错: {str(e)}")

    def stop_playback(self):
        """停止播放"""
        try:
            self.midi_player.stop()
            self.update_button_states()
            self.time_label['text'] = "剩余时间: 00:00"
        except Exception as e:
            print(f"停止播放时出错: {str(e)}")

    def pause_playback(self):
        """暂停/继续播放"""
        try:
            if self.midi_player.playing:
                self.midi_player.pause()
                self.update_button_states()
            else:
                # 只有在有选中的歌曲时才开始播放
                if self.current_index >= 0:
                    self.start_playback()
        except Exception as e:
            print(f"暂停/继续播放时出错: {str(e)}")

    def toggle_play(self):
        """切换播放/暂停状态"""
        if not self.midi_player.playing:
            self.start_playback()
        else:
            self.pause_playback()

    def change_song(self, delta):
        """切换歌曲"""
        try:
            if not self.midi_files:
                return
            
            # 计算新的索引
            new_index = (self.current_index + delta) % len(self.midi_files)
            if new_index < 0:  # 处理负数索引
                new_index = len(self.midi_files) - 1
            
            # 更新列表选择
            self.song_list.selection_clear(0, tk.END)
            self.song_list.selection_set(new_index)
            self.song_list.see(new_index)  # 确保新选中的项可见
            
            # 触发歌曲选择事件
            self.song_selected()
            
            # 如果正在播放，停止当前播放并开始新歌曲
            was_playing = self.midi_player.playing
            if was_playing:
                self.stop_playback()
                self.start_playback()
            
        except Exception as e:
            print(f"切换歌曲时出错: {str(e)}")

    def update_button_states(self):
        """更新按钮状态"""
        try:
            if self.midi_player.playing:
                if hasattr(self.midi_player, 'preview_mode') and self.midi_player.preview_mode:
                    self.play_btn['text'] = "播放"
                    self.preview_original_btn['text'] = "预览原始"
                    self.preview_adjusted_btn['text'] = "预览调整"
                else:
                    if self.midi_player.paused:
                        self.play_btn['text'] = "继续"
                        self.pause_btn['text'] = "已暂停"
                    else:
                        self.play_btn['text'] = "播放中"
                        self.pause_btn['text'] = "暂停"
                    self.preview_original_btn['text'] = "预览原始"
                    self.preview_adjusted_btn['text'] = "预览调整"
            else:
                self.play_btn['text'] = "播放"
                self.pause_btn['text'] = "暂停"
                self.preview_original_btn['text'] = "预览原始"
                self.preview_adjusted_btn['text'] = "预览调整"
        except Exception as e:
            print(f"更新按钮状态时出错: {str(e)}")

    def filter_songs(self):
        """根据搜索文本过滤歌曲列表"""
        try:
            search_text = self.search_var.get().lower()
            self.song_list.delete(0, tk.END)
            
            if not search_text:
                # 如果搜索框为空，显示所有歌曲
                for file in self.midi_files:
                    self.song_list.insert(tk.END, os.path.basename(file))
            else:
                # 否则显示匹配的歌曲
                for file in self.midi_files:
                    filename = os.path.basename(file).lower()
                    if search_text in filename:
                        self.song_list.insert(tk.END, os.path.basename(file))
            
            # 如果之前有选中的歌曲，尝试重新选中
            if self.current_index >= 0 and self.current_index < len(self.midi_files):
                current_file = os.path.basename(self.midi_files[self.current_index])
                # 查找当前歌曲在过滤后列表中的位置
                for i in range(self.song_list.size()):
                    if self.song_list.get(i) == current_file:
                        self.song_list.selection_set(i)
                        self.song_list.see(i)
                        break
        except Exception as e:
            print(f"过滤歌曲时出错: {str(e)}")

    def on_closing(self):
        """窗口关闭时的处理"""
        try:
            # 停止播放
            if self.midi_player.playing:
                self.midi_player.stop()
            
            # 保存配置
            self.save_config()
            
            # 移除所有键盘钩子
            keyboard.unhook_all()
            
            # 销毁窗口
            self.root.destroy()
        except Exception as e:
            print(f"关闭窗口时出错: {str(e)}")
            self.root.destroy()

    def quit_application(self):
        """退出应用程序"""
        try:
            print("正在退出应用程序...")
            # 停止播放
            if self.midi_player.playing:
                self.midi_player.stop()
            
            # 保存配置
            self.save_config()
            
            # 移除所有键盘钩子
            keyboard.unhook_all()
            
            # 销毁窗口
            self.root.destroy()
        except Exception as e:
            print(f"退出应用程序时出错: {str(e)}")
            self.root.destroy()

    def force_stop_playback(self):
        """强制停止弹奏"""
        try:
            if self.midi_player.playing:
                print("强制停止弹奏...")
                self.stop_playback()
                # 可以在这里添加额外的清理操作
        except Exception as e:
            print(f"强制停止弹奏时出错: {str(e)}")
        
    def toggle_preview(self, is_original=False):
        """切换预览播放状态"""
        try:
            if not self.midi_player.playing:
                if self.current_index >= 0:
                    # 开始预览播放
                    btn = self.preview_original_btn if is_original else self.preview_adjusted_btn
                    btn['text'] = "停止预览"
                    self.midi_player.play_file(self.midi_files[self.current_index], 
                                             preview_mode=True,
                                             preview_original=is_original)
            else:
                # 停止预览
                self.stop_playback()
                self.preview_original_btn['text'] = "预览原始"
                self.preview_adjusted_btn['text'] = "预览调整"
        except Exception as e:
            print(f"切换预览状态时出错: {str(e)}")
        
    def update_weight(self, key):
        """更新权重参数"""
        try:
            value = self.weight_vars[key].get()
            self.midi_player.note_optimizer.weights[key] = value
            # 如果当前有选中的歌曲，重新计算优化
            if self.current_index >= 0:
                self.reanalyze_current_song()
        except Exception as e:
            print(f"更新权重参数时出错: {str(e)}")

    def update_octave_weight(self, key):
        """更新八度权重"""
        try:
            # 更新八度权重
            weights = {k: v.get() for k, v in self.octave_vars.items()}
            # 归一化权重
            total = sum(weights.values())
            if total > 0:
                normalized_weights = {k: v/total for k, v in weights.items()}
                self.midi_player.note_optimizer.octave_weights = normalized_weights
                # 重新分析当前歌曲
                if self.current_index >= 0:
                    self.reanalyze_current_song()
        except Exception as e:
            print(f"更新八度权重时出错: {str(e)}")

    def reset_optimization_params(self):
        """重置优化参数为默认值"""
        try:
            # 重置权重
            default_weights = {
                'coverage': 0.3,
                'density': 0.2,
                'melody': 0.2,
                'transition': 0.1,
                'pentatonic': 0.1,
                'octave_balance': 0.1
            }
            
            # 更新UI和优化器
            for key, value in default_weights.items():
                self.weight_vars[key].set(value)
                self.midi_player.note_optimizer.weights[key] = value
            
            # 重置八度权重
            default_octave_weights = {'low': 0.3, 'middle': 0.4, 'high': 0.3}
            for key, value in default_octave_weights.items():
                self.octave_vars[key].set(value)
            
            self.midi_player.note_optimizer.octave_weights = default_octave_weights
            
            # 重新分析当前歌曲
            if self.current_index >= 0:
                self.reanalyze_current_song()
        except Exception as e:
            print(f"重置优化参数时出错: {str(e)}")

    def reanalyze_current_song(self):
        """重新分析当前歌曲"""
        try:
            if self.current_index >= 0:
                # 停止当前播放
                was_playing = self.midi_player.playing
                if was_playing:
                    self.stop_playback()
                
                # 重新加载和分析MIDI文件
                mid = mido.MidiFile(self.midi_files[self.current_index])
                self.midi_player.analyze_tracks(mid)
                
                # 如果之前在播放，则重新开始播放
                if was_playing:
                    self.start_playback()
        except Exception as e:
            print(f"重新分析歌曲时出错: {str(e)}")
        
    def refresh_midi_files(self):
        """刷新MIDI文件列表"""
        try:
            if not self.last_directory:
                return
            
            # 保存当前选中的文件名（如果有）
            current_file = None
            if self.current_index >= 0 and self.current_index < len(self.midi_files):
                current_file = os.path.basename(self.midi_files[self.current_index])
            
            # 重新加载目录中的所有MIDI文件
            self.midi_files = []
            for root, _, files in os.walk(self.last_directory):
                for file in files:
                    if file.lower().endswith(('.mid', '.midi')):
                        self.midi_files.append(os.path.join(root, file))
            
            # 清空并更新歌曲列表
            self.song_list.delete(0, tk.END)
            for file in self.midi_files:
                self.song_list.insert(tk.END, os.path.basename(file))
            
            # 尝试恢复之前选中的文件
            if current_file:
                for i, file in enumerate(self.midi_files):
                    if os.path.basename(file) == current_file:
                        self.song_list.selection_set(i)
                        self.song_list.see(i)
                        self.current_index = i
                        break
            # 如果没有找到之前的文件但列表不为空，选中第一个
            elif self.midi_files:
                self.song_list.selection_set(0)
                self.current_index = 0
            
            if self.midi_files:
                self.enable_buttons()
            else:
                self.disable_buttons()
            
        except Exception as e:
            print(f"刷新MIDI文件列表时出错: {str(e)}")
        
    # ... [其他方法的实现与原QT版本类似，只需要调整UI相关的代码] 