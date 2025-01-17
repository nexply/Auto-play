import os
import time
import threading
import keyboard
import mido
import ctypes
from keyboard_mapping import NOTE_TO_KEY
from collections import defaultdict
import weakref
from PyQt5.QtCore import QObject, pyqtSignal

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
    except OSError:
        return False

def check_admin_rights():
    """检查管理员权限并打印说明"""
    if not is_admin():
        print("\n警告: 该工具需要使用管理员权限运行，不然无法成功触发按键。")
        print("请右键点击程序，选择'以管理员身份运行'后重试。\n")
        return False
    return True

class MidiPlayer(QObject):  # 继承QObject以支持信号
    window_switch_failed = pyqtSignal()  # 添加新信号
    
    def __init__(self):
        super().__init__()  # 调用父类初始化
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
        self.PLAYABLE_MIN = 36  # 最低音（C2）
        self.PLAYABLE_MAX = 96  # 最高音（C7）
        self.PLAYABLE_RANGE = self.PLAYABLE_MAX - self.PLAYABLE_MIN
        
        # 添加音符映射范围
        self.NOTE_RANGES = [
            (36, 47),  # 低音区域 C2-B2
            (48, 59),  # 中低音区域 C3-B3
            (60, 71),  # 中音区域 C4-B4
            (72, 83),  # 中高音区域 C5-B5
            (84, 96)   # 高音区域 C6-C7
        ]
        
        # 添加备用窗口列表
        self.window_titles = [
            "燕云十六声",  # 主窗口
            "新建文本文档",  # 备用窗口1
        ]
        self.current_window_index = 0  # 当前使用的窗口索引

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
                print(f"按下键位: {key}")
                if '+' in key:
                    parts = key.split('+')
                    modifier, base_key = parts[0], parts[1]
                    keyboard.press(modifier)
                    keyboard.press(base_key)
                    self._pressed_keys.add(key)
                else:
                    keyboard.press(key)
                    self._pressed_keys.add(key)
        except Exception as e:
            print(f"按键处理出错 {key}: {str(e)}")
            # 确保出错时也释放按键
            try:
                if '+' in key:
                    parts = key.split('+')
                    keyboard.release(parts[1])
                    keyboard.release(parts[0])
                else:
                    keyboard.release(key)
            except:
                pass
            if key in self._pressed_keys:
                self._pressed_keys.remove(key)

    def _release_key(self, key):
        """释放键位"""
        try:
            if key in self._pressed_keys:
                print(f"释放键位: {key}")
                if '+' in key:
                    parts = key.split('+')
                    keyboard.release(parts[1])  # 先释放基础键
                    keyboard.release(parts[0])  # 再释放修饰键
                else:
                    keyboard.release(key)
                self._pressed_keys.remove(key)
        except Exception as e:
            print(f"释放按键出错 {key}: {str(e)}")
            # 确保出错时也从集合中移除
            if key in self._pressed_keys:
                self._pressed_keys.remove(key)

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
        """分析MIDI文件的音轨"""
        try:
            tracks_info = []
            for track in mid.tracks:
                messages = []
                current_time = 0
                
                for msg in track:
                    current_time += msg.time
                    if msg.type in ['note_on', 'note_off']:
                        # 创建消息的副本，并设置绝对时间
                        msg_copy = msg.copy()
                        msg_copy.time = current_time
                        messages.append(msg_copy)
                
                if messages:
                    tracks_info.append({
                        'messages': messages,
                        'channel': None
                    })
            
            return tracks_info
            
        except Exception as e:
            print(f"分析音轨时出错: {str(e)}")
            return []

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
                except UnicodeDecodeError:  # 替换裸异常为具体异常类型
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
        """切换到游戏窗口，使用模糊匹配"""
        try:
            def enum_windows_callback(hwnd, window_list):
                title = self._win32gui.GetWindowText(hwnd)
                # 对每个目标标题进行模糊匹配
                for target_title in self.window_titles:
                    if target_title.lower() in title.lower():
                        window_list.append((hwnd, title, target_title))
                return True
                
            window_list = []
            self._win32gui.EnumWindows(enum_windows_callback, window_list)
            
            if not window_list:
                print("未找到任何匹配的游戏窗口")
                self.window_switch_failed.emit()  # 发送信号
                self.playing = False  # 停止播放
                return False
                
            # 尝试切换到当前选择的窗口
            current_title = self.window_titles[self.current_window_index]
            for hwnd, title, matched_title in window_list:
                if matched_title == current_title:
                    try:
                        self._win32gui.SetForegroundWindow(hwnd)
                        self.target_window_name = title  # 更新为实际的窗口标题
                        return True
                    except Exception as e:
                        print(f"切换到窗口 {title} 失败: {str(e)}")
            
            # 如果当前选择的窗口不可用，尝试其他窗口
            for hwnd, title, matched_title in window_list:
                try:
                    self._win32gui.SetForegroundWindow(hwnd)
                    self.current_window_index = self.window_titles.index(matched_title)
                    self.target_window_name = title
                    return True
                except Exception as e:
                    print(f"切换到窗口 {title} 失败: {str(e)}")
                    continue
                
            # 如果所有窗口都切换失败
            print("所有目标窗口都无法切换")
            self.window_switch_failed.emit()  # 发送信号
            self.playing = False  # 停止播放
            return False
            
        except Exception as e:
            print(f"切换到游戏窗口时出错: {str(e)}")
            self.window_switch_failed.emit()  # 发送信号
            self.playing = False  # 停止播放
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
        """统一的暂停处理"""
        with self._lock:
            if self.playing:
                was_paused = self.paused
                self.paused = not was_paused
                
                if self.paused:  # 暂停播放
                    self.pause_time = time.time() * 1000
                    self._release_all_keys()  # 确保释放所有按键
                    print("暂停播放")
                else:  # 继续播放
                    # 切换到目标窗口
                    if not self._switch_to_game_window():
                        print("无法切换到目标窗口，保持暂停状态")
                        self.paused = True
                        return False
                    
                    if self.pause_time:
                        self.total_pause_time += time.time() * 1000 - self.pause_time
                    self.pause_time = 0
                    print("继续播放")
                
                return True
            return False

    def resume(self):
        """恢复播放"""
        try:
            # 在恢复播放前检查窗口状态
            if not self._switch_to_game_window():
                print("无法找到目标窗口，无法恢复播放")
                self.window_switch_failed.emit()  # 发送窗口切换失败信号
                return False
            
            with self._lock:
                if not self.playing or not self.paused:
                    return False
                
                self.paused = False
                if self.pause_time:
                    self.total_pause_time += time.time() * 1000 - self.pause_time
                self.pause_time = 0
                self.auto_paused = False
                return True
            
        except Exception as e:
            print(f"恢复播放时出错: {str(e)}")
            return False

    def stop(self):
        """统一的停止播放处理"""
        with self._lock:
            self.playing = False
            self.paused = False
            self.auto_paused = False
            self.current_file = None
            self._release_all_keys()
            print("停止播放")

    def _adjust_note(self, note):
        """智能调整音符音高，尽量保持原始音乐的相对关系"""
        try:
            # 使用缓存
            cache_key = (note, self.note_offset)
            if cache_key in self._note_key_cache:
                return self._note_key_cache[cache_key]

            adjusted_note = note + self.note_offset

            # 如果音符已经在可播放范围内，直接返回
            if self.PLAYABLE_MIN <= adjusted_note <= self.PLAYABLE_MAX:
                self._note_key_cache[cache_key] = adjusted_note
                return adjusted_note

            # 找到最近的可播放区域
            best_range = None
            min_distance = float('inf')
            
            for note_range in self.NOTE_RANGES:
                range_center = (note_range[0] + note_range[1]) / 2
                distance = abs(adjusted_note - range_center)
                if distance < min_distance:
                    min_distance = distance
                    best_range = note_range

            # 将音符映射到最近的可播放区域
            if best_range:
                if adjusted_note < best_range[0]:
                    adjusted_note = best_range[0] + (adjusted_note % 12)
                elif adjusted_note > best_range[1]:
                    adjusted_note = best_range[1] - (11 - (adjusted_note % 12))

                # 确保音符在可播放范围内
                adjusted_note = max(self.PLAYABLE_MIN, min(adjusted_note, self.PLAYABLE_MAX))
                
                # 缓存结果
                self._note_key_cache[cache_key] = adjusted_note
                return adjusted_note

            # 如果无法调整，返回原始音符
            return note

        except Exception as e:
            print(f"调整音符时出错: {str(e)}")
            return note

    def _check_active_window(self):
        """检查目标窗口是否处于活动状态"""
        try:
            if not self._win32gui:
                return True
            
            active_window = self._win32gui.GetForegroundWindow()
            active_title = self._win32gui.GetWindowText(active_window).lower()
            
            # 检查当前活动窗口是否匹配任何目标窗口
            for title in self.window_titles:
                if title.lower() in active_title:
                    return True
            
            return False
            
        except Exception as e:
            print(f"检查窗口状态时出错: {str(e)}")
            return True  # 出错时默认返回True以避免意外暂停

    def play_track(self, track_info):
        """播放单个音轨"""
        try:
            last_pause_check = time.time()
            last_time = 0
            
            print("\n开始播放音轨:")
            print(f"消息总数: {len(track_info['messages'])}")
            
            # 确保切换到目标窗口
            if not self._switch_to_game_window():
                print("无法切换到目标窗口，暂停播放")
                self.pause()
                return
            
            for msg in track_info['messages']:
                if not self.playing:
                    break
                    
                # 计算相对时间并处理延时
                relative_time = msg.time - last_time if hasattr(msg, 'time') else 0
                if relative_time > 0:
                    time.sleep(relative_time / 1000)
                last_time = msg.time if hasattr(msg, 'time') else last_time
                
                # 定期检查窗口状态
                current_time = time.time()
                if current_time - last_pause_check >= self.window_check_interval:
                    window_active = self._check_active_window()
                    last_pause_check = current_time
                    
                    if not window_active and not self.paused:
                        print("\n目标窗口失去焦点，自动暂停")
                        self.auto_paused = True
                        self.pause()  # 使用统一的暂停处理
                        continue
                
                # 处理暂停状态
                while self.paused:
                    time.sleep(0.1)
                    if not self.playing:  # 如果在暂停时停止播放
                        break
                    continue

                if not self.playing:
                    break

                # 处理音符消息
                if msg.type == 'note_on' and msg.velocity > 0:
                    if track_info.get('channel') is None or msg.channel == track_info['channel']:
                        note = self._adjust_note(msg.note)
                        if note in NOTE_TO_KEY:
                            key = NOTE_TO_KEY[note]
                            print(f"音符信息: {msg.note}(原始) -> {note}(调整后) -> {key}(按键)")
                            keyboard.press(key)
                            time.sleep(0.05)
                            keyboard.release(key)
                
            print("\n音轨播放完成")
            
        except Exception as e:
            print(f"\n播放音轨时出错: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self._release_all_keys()

    def play_midi(self, midi_file, track_index=None):
        """播放MIDI文件"""
        try:
            if not os.path.exists(midi_file):
                print(f"MIDI文件不存在: {midi_file}")
                return
            
            # 设置播放状态
            with self._lock:
                self.playing = True
                self.paused = False
                self.current_file = midi_file
                self.start_time = time.time() * 1000
                self.pause_time = 0
                self.total_pause_time = 0
            
            # 分析MIDI文件
            mid = mido.MidiFile(midi_file)
            self._calculate_total_time(mid)  # 计算总时长
            tracks_info = self.analyze_tracks(mid)
            
            if not tracks_info:
                print("没有找到可播放的音轨")
                self.stop()
                return
            
            # 确保窗口处于活动状态
            if not self._switch_to_game_window():
                print("无法切换到游戏窗口，停止播放")
                self.stop()
                return
            
            # 选择要播放的音轨
            try:
                # 将所有音轨的消息按时间顺序合并
                merged_messages = []
                
                # 修正：确保 track_index 是有效的整数
                if track_index is not None:
                    try:
                        track_index = int(track_index)
                    except ValueError:
                        track_index = 0
                
                print(f"准备播放音轨，索引: {track_index}, 总音轨数: {len(tracks_info)}")
                
                if track_index is None or track_index <= 0:  # 播放所有音轨
                    print("播放所有音轨")
                    for track in tracks_info:
                        merged_messages.extend(track['messages'])
                elif track_index <= len(tracks_info):  # 播放指定音轨
                    print(f"播放音轨 {track_index}")
                    merged_messages = tracks_info[track_index - 1]['messages']
                else:
                    print(f"无效的音轨索引: {track_index}，音轨数量: {len(tracks_info)}")
                    self.stop()
                    return
                
                if not merged_messages:
                    print("没有可播放的消息")
                    self.stop()
                    return
                    
                # 按时间顺序排序所有消息
                merged_messages.sort(key=lambda x: x.time)
                print(f"总消息数: {len(merged_messages)}")
                
                # 创建一个包含所有消息的单一音轨信息
                merged_track = {
                    'messages': merged_messages,
                    'channel': None  # 允许所有通道
                }
                
                # 播放合并后的音轨
                self.play_track(merged_track)
                
            except Exception as e:
                print(f"播放音轨时出错: {str(e)}")
                import traceback
                traceback.print_exc()
                self.stop()
                
        except Exception as e:
            print(f"播放MIDI文件时出错: {str(e)}")
            self.stop() 