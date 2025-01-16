import os
import time
import threading
import keyboard
import mido
import ctypes
from keyboard_mapping import NOTE_TO_KEY
from collections import defaultdict
import weakref

# 延迟导入 win32gui
def get_win32gui():
    try:
        import win32gui
        return win32gui
    except ImportError:
        print("警告: 无法导入 win32gui，窗口检测功能将不可用")
        return None

def is_admin():
    """检查是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def check_admin_rights():
    """检查管理员权限并打印说明"""
    if not is_admin():
        print("\n警告: 该工具需要使用管理员权限运行，不然无法成功触发按键。")
        print("请右键点击程序，选择'以管理员身份运行'后重试。\n")
        return False
    return True

class MidiPlayer:
    def __init__(self):
        self._win32gui = get_win32gui()
        # 检查管理员权限
        if not check_admin_rights():
            raise PermissionError("需要管理员权限才能运行此工具")
            
        self.playing = False
        self.paused = False
        self.current_file = None
        self.play_thread = None
        self._pressed_keys = set()
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 时间相关变量
        self.start_time = 0
        self.pause_time = 0
        self.total_pause_time = 0
        self.total_time = 0
        
        # 音轨相关
        self.tracks_info = []
        self.selected_track = None
        
        # 音高调整
        self.note_offset = 0  # 整体音高偏移量
        
        # 目标窗口名称
        self.target_window_name = "燕云十六声"
        
        # 窗口监控
        self.window_check_interval = 0.2  # 增加到0.2秒
        self.last_window_check = 0
        self.last_window_state = False  # 缓存窗口状态
        self.auto_paused = False  # 标记是否因窗口切换而暂停
        
        # 性能优化：缓存
        self._note_key_cache = {}  # 缓存音符到按键的映射
        self._weak_refs = weakref.WeakSet()  # 用于避免循环引用
        self._cached_mid = None  # 缓存当前MIDI文件对象
        
        # 性能优化：预计算的常量
        self.PLAYABLE_MIN = 48  # 最低音（低音1）
        self.PLAYABLE_MAX = 83  # 最高音（高音7）
        self.PLAYABLE_RANGE = self.PLAYABLE_MAX - self.PLAYABLE_MIN

    def get_current_time(self):
        """获取当前播放时间（秒）"""
        try:
            if not self.playing:
                return 0
                
            with self._lock:
                if self.paused:
                    if self.pause_time:
                        return (self.pause_time - self.start_time - self.total_pause_time) / 1000
                    return 0
                    
                current = time.time() * 1000 - self.start_time - self.total_pause_time
                # 确保不超过总时长
                return min(current / 1000, self.total_time)
                
        except Exception as e:
            print(f"获取当前时间时出错: {str(e)}")
            return 0

    def get_total_time(self):
        """获取总时长（秒）"""
        return self.total_time

    def _calculate_total_time(self, mid):
        """计算MIDI文件总时长"""
        try:
            max_ticks = 0
            current_ticks = 0
            
            # 获取基准tempo
            base_tempo = 500000  # 默认值
            for msg in mid.tracks[0]:
                if msg.type == 'set_tempo':
                    base_tempo = msg.tempo
                    break
            
            # 计算最大tick数
            for track in mid.tracks:
                current_ticks = 0
                for msg in track:
                    current_ticks += msg.time
                    max_ticks = max(max_ticks, current_ticks)
            
            # 使用原始tempo计算基础时长
            seconds = (max_ticks * base_tempo) / (mid.ticks_per_beat * 1000000)
            self.total_time = max(seconds, 0)  # 确保时长不为负
            return self.total_time
            
        except Exception as e:
            print(f"计算总时长时出错: {str(e)}")
            self.total_time = 0
            return 0

    def _press_key(self, key):
        """按下键位"""
        try:
            if key not in self._pressed_keys:
                if '+' in key:  # 处理组合键
                    parts = key.split('+')
                    modifier, base_key = parts[0], parts[1]
                    try:
                        # 批量处理按键操作
                        keyboard.press(modifier)
                        keyboard.press(base_key)
                        keyboard.release(modifier)
                        keyboard.release(base_key)
                    except Exception as e:
                        print(f"组合键操作出错 {key}: {str(e)}")
                        return
                else:
                    try:
                        keyboard.press(key)
                    except Exception as e:
                        print(f"单键操作出错 {key}: {str(e)}")
                        return
                self._pressed_keys.add(key)
        except Exception as e:
            print(f"按键处理出错 {key}: {str(e)}")

    def _release_key(self, key):
        """释放键位"""
        try:
            if key in self._pressed_keys:
                if '+' in key:  # 处理组合键
                    try:
                        keyboard.release(key.split('+')[1])
                    except Exception as e:
                        print(f"组合键释放出错 {key}: {str(e)}")
                        return
                else:
                    try:
                        keyboard.release(key)
                    except Exception as e:
                        print(f"单键释放出错 {key}: {str(e)}")
                        return
                self._pressed_keys.remove(key)
        except Exception as e:
            print(f"释放按键出错 {key}: {str(e)}")

    def _release_all_keys(self):
        """释放所有按下的键位"""
        try:
            # 创建按键列表的副本进行迭代
            keys_to_release = list(self._pressed_keys)
            for key in keys_to_release:
                self._release_key(key)
            
            # 确保修饰键被释放
            try:
                keyboard.release('shift')
                keyboard.release('ctrl')
            except Exception as e:
                print(f"释放修饰键时出错: {str(e)}")
                
            self._pressed_keys.clear()
        except Exception as e:
            print(f"释放所有按键时出错: {str(e)}")
            # 强制清空按键集合
            self._pressed_keys.clear()

    def analyze_tracks(self, mid):
        """分析MIDI文件的音轨信息并计算最佳音高偏移"""
        try:
            self.tracks_info = []
            all_notes = []
            note_frequency = defaultdict(int)
            channel_info = {}
            
            # 使用更高效的数据结构
            channel_notes = defaultdict(int)
            
            # 一次性收集所有信息
            for track in mid.tracks:
                for msg in track:
                    if msg.type == 'note_on' and hasattr(msg, 'channel') and msg.velocity > 0:
                        channel = msg.channel
                        channel_notes[channel] += 1
                        all_notes.append(msg.note)
                        note_frequency[msg.note] += 1
                    elif msg.type == 'track_name' and hasattr(msg, 'channel'):
                        try:
                            track_name = self._decode_track_name(msg.name)
                            if track_name:
                                channel = msg.channel
                                if channel not in channel_info:
                                    channel_info[channel] = {'name': track_name, 'notes_count': 0}
                        except:
                            continue
            
            # 合并信息
            for channel, count in channel_notes.items():
                name = channel_info.get(channel, {}).get('name', f'音轨 {channel+1}')
                if count > 0:
                    self.tracks_info.append({
                        'channel': channel,
                        'name': name,
                        'notes_count': count
                    })
            
            # 如果没有找到任何音轨，添加默认音轨
            if not self.tracks_info:
                self.tracks_info.append({
                    'channel': 0,
                    'name': '默认音轨',
                    'notes_count': 0
                })
            
            # 计算最佳偏移量
            if all_notes:
                self._calculate_best_offset(all_notes, note_frequency)
            
            return self.tracks_info
            
        except Exception as e:
            print(f"分析音轨时出错: {str(e)}")
            return [{'channel': 0, 'name': '默认音轨', 'notes_count': 0}]

    def _decode_track_name(self, name):
        """解码音轨名称"""
        if isinstance(name, bytes):
            # 尝试不同的编码方式
            encodings = ['utf-8', 'gbk', 'gb2312', 'shift-jis', 'ascii']
            for encoding in encodings:
                try:
                    decoded = name.decode(encoding)
                    # 如果成功解码并且结果看起来是有效的
                    if decoded and not any(ord(c) < 32 for c in decoded):
                        return decoded
                except:
                    continue
        elif isinstance(name, str):
            return name
        return None

    def _calculate_best_offset(self, all_notes, note_frequency):
        """计算最佳音高偏移"""
        try:
            min_note = min(all_notes)
            max_note = max(all_notes)
            note_range = max_note - min_note
            
            # 计算当前音符范围的中心
            current_center = (min_note + max_note) / 2
            # 计算目标范围的中心
            target_center = (self.PLAYABLE_MIN + self.PLAYABLE_MAX) / 2
            
            # 初始偏移量：将当前范围中心对齐到目标范围中心
            base_offset = int(target_center - current_center)
            
            # 尝试不同的偏移量，找到最佳匹配
            best_offset = base_offset
            best_playable = 0
            
            # 在基础偏移量附近搜索最佳偏移
            for offset in range(base_offset - 12, base_offset + 13):  # 上下一个八度范围内搜索
                playable_count = sum(1 for note in all_notes 
                                   if self.PLAYABLE_MIN <= note + offset <= self.PLAYABLE_MAX)
                if playable_count > best_playable:
                    best_playable = playable_count
                    best_offset = offset
            
            self.note_offset = best_offset
            
            # 打印调试信息
            print(f"音符范围: {min_note}-{max_note} (范围: {note_range})")
            print(f"偏移量: {self.note_offset}")
            print(f"调整后范围: {min_note + self.note_offset}-{max_note + self.note_offset}")
            print(f"可播放音符数: {sum(1 for note in all_notes if self.PLAYABLE_MIN <= note + self.note_offset <= self.PLAYABLE_MAX)}/{len(all_notes)}")
            
        except Exception as e:
            print(f"计算音高偏移时出错: {str(e)}")
            self.note_offset = 0

    def set_track(self, channel):
        """设置要播放的音轨"""
        self.selected_track = channel

    def _find_game_window(self):
        """查找游戏窗口"""
        try:
            hwnd = self._win32gui.FindWindow(None, self.target_window_name)
            if hwnd:
                return hwnd
            return None
        except Exception as e:
            print(f"查找窗口时出错: {str(e)}")
            return None

    def _switch_to_game_window(self):
        """切换到游戏窗口"""
        try:
            hwnd = self._find_game_window()
            if hwnd:
                # 确保窗口未最小化
                if self._win32gui.IsIconic(hwnd):
                    self._win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                # 将窗口置于前台
                self._win32gui.SetForegroundWindow(hwnd)
                return True
            return False
        except Exception as e:
            print(f"切换窗口时出错: {str(e)}")
            return False

    def play_file(self, midi_file):
        """播放MIDI文件"""
        try:
            if not os.path.exists(midi_file):
                print(f"文件不存在: {midi_file}")
                return
            
            # 停止当前播放
            self.stop()
            
            try:
                # 加载并缓存MIDI文件
                mid = mido.MidiFile(midi_file)
                
                # 预计算总时长和分析音轨
                total_time = self._calculate_total_time(mid)
                tracks_info = self.analyze_tracks(mid)
                
                # 尝试切换到游戏窗口
                if not self._switch_to_game_window():
                    print(f"警告: 未找到游戏窗口 '{self.target_window_name}'，请确保游戏已启动")
                    return
                
                # 设置新的播放状态
                with self._lock:
                    self.current_file = midi_file
                    self._cached_mid = mid  # 在设置其他状态之前缓存MIDI文件
                    self.total_time = total_time
                    self.tracks_info = tracks_info
                    self.playing = True
                    self.paused = False
                    self.start_time = time.time() * 1000
                    self.total_pause_time = 0
                    
                self.play_thread = threading.Thread(target=self._play_thread)
                self.play_thread.daemon = True
                self.play_thread.start()
                
            except (EOFError, OSError, ValueError) as e:
                print(f"MIDI文件损坏或格式不正确: {str(e)}")
                self.stop()
                raise
                
        except Exception as e:
            print(f"播放文件时出错: {str(e)}")
            self.stop()

    def _play_thread(self):
        """MIDI播放线程"""
        try:
            if not self._cached_mid:
                print("未找到缓存的MIDI文件")
                return
                
            last_pause_check = time.time()
            
            # 获取播放状态的本地副本
            with self._lock:
                is_playing = self.playing
                is_paused = self.paused
                selected_track = self.selected_track
            
            # 使用缓存的MIDI文件
            for msg in self._cached_mid.play(meta_messages=True):
                # 快速检查播放状态
                with self._lock:
                    is_playing = self.playing
                    is_paused = self.paused
                    if not is_playing:
                        break
                
                # 检查窗口状态并处理暂停
                current_time = time.time()
                if current_time - last_pause_check >= 0.1:
                    # 检查窗口状态
                    if not self._check_active_window():
                        if not self.auto_paused and not is_paused:
                            print("窗口切换，自动暂停播放")
                            with self._lock:
                                self.paused = True
                                self.auto_paused = True
                            is_paused = True
                    elif self.auto_paused and is_paused:
                        print("窗口恢复，继续播放")
                        with self._lock:
                            self.paused = False
                            self.auto_paused = False
                        is_paused = False
                    
                    # 更新状态
                    with self._lock:
                        is_playing = self.playing
                        is_paused = self.paused
                        selected_track = self.selected_track
                        if self.pause_time:
                            pause_duration = current_time * 1000 - self.pause_time
                            self.total_pause_time += pause_duration
                            self.pause_time = 0
                    
                    last_pause_check = current_time
                
                # 处理暂停
                if is_paused:
                    time.sleep(0.1)
                    continue
                
                # 处理音符消息
                if msg.type == 'note_on' and hasattr(msg, 'channel'):
                    if selected_track is None or msg.channel == selected_track:
                        note = self._adjust_note(msg.note)
                        if note in NOTE_TO_KEY:
                            if msg.velocity > 0:
                                self._press_key(NOTE_TO_KEY[note])
                            else:
                                self._release_key(NOTE_TO_KEY[note])
                elif msg.type == 'note_off' and hasattr(msg, 'channel'):
                    if selected_track is None or msg.channel == selected_track:
                        note = self._adjust_note(msg.note)
                        if note in NOTE_TO_KEY:
                            self._release_key(NOTE_TO_KEY[note])
                
                if not is_playing:
                    break
            
            # 播放结束后清理
            self.stop()
            
        except Exception as e:
            print(f"播放时出错: {str(e)}")
            self.stop()

    def pause(self):
        """暂停或继续播放"""
        with self._lock:
            if self.playing:
                # 如果是自动暂停，不允许手动继续播放，除非窗口已经恢复
                if self.auto_paused and not self._check_active_window():
                    print("请切换到游戏窗口后再继续播放")
                    return
                    
                # 如果要继续播放，先检查游戏窗口
                if self.paused and not self._switch_to_game_window():
                    print(f"警告: 未找到游戏窗口 '{self.target_window_name}'，请确保游戏已启动")
                    return
                    
                self.paused = not self.paused
                self.auto_paused = False  # 清除自动暂停标记
                if not self.paused:
                    self.pause_time = 0

    def stop(self):
        """停止播放"""
        try:
            # 先标记停止状态
            with self._lock:
                was_playing = self.playing
                self.playing = False
                self.paused = False
                self.auto_paused = False
                self.start_time = 0
                self.pause_time = 0
                self.total_pause_time = 0
            
            # 释放所有按键
            self._release_all_keys()
            
            # 如果之前在播放，等待线程结束
            if was_playing and self.play_thread and self.play_thread.is_alive():
                try:
                    self.play_thread.join(timeout=0.5)
                except:
                    pass
            
            # 清理缓存
            with self._lock:
                self._cached_mid = None
                self._note_key_cache.clear()  # 清除音符缓存
            
        except Exception as e:
            print(f"停止播放时出错: {str(e)}")
            self._release_all_keys()

    def _adjust_note(self, note):
        """调整音符音高，保持相对关系"""
        # 使用缓存
        cache_key = (note, self.note_offset)
        if cache_key not in self._note_key_cache:
            self._note_key_cache[cache_key] = note + self.note_offset
        return self._note_key_cache[cache_key] 

    def _check_active_window(self):
        """检查当前活动窗口是否为目标窗口"""
        try:
            current_time = time.time()
            # 使用缓存的状态
            if current_time - self.last_window_check < self.window_check_interval:
                return self.last_window_state
                
            self.last_window_check = current_time
            active_window = self._win32gui.GetForegroundWindow()
            window_title = self._win32gui.GetWindowText(active_window)
            
            # 更新缓存的状态
            self.last_window_state = (window_title == self.target_window_name)
            return self.last_window_state
            
        except Exception as e:
            print(f"检查活动窗口时出错: {str(e)}")
            return False 