import os
import time
import threading
import keyboard
import mido
import win32gui
import ctypes
from keyboard_mapping import NOTE_TO_KEY, PENTATONIC_INTERVALS, PLAY_MODES
from collections import defaultdict
import weakref
import pygame.mixer
import pygame
from sound_manager import SoundManager
from note_range_optimizer import NoteRangeOptimizer
from typing import Optional, Tuple, Dict, List
from key_sender import KeySender
from key_sequence import KeySequence, KeyEvent

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
    def __init__(self, mode='21key'):
        """初始化播放器
        Args:
            mode: 演奏模式 ('21key' 或 '36key')
        """
        # 基本属性
        self.current_file = None
        self.playing = False
        self.paused = False
        self.play_thread = None
        self.selected_track = None
        self.tracks_info = []
        self.note_offset = 0
        self.playback_speed = 1.0
        
        # 设置当前模式
        self.set_mode(mode)
        
        # 初始化音符优化器
        self.note_optimizer = NoteRangeOptimizer(mode=mode)
        
        # 初始化声音管理器
        self.sound_manager = SoundManager()
        
        # 初始化按键发送器
        self.key_sender = KeySender()
        
        # 从当前模式获取播放范围和按键映射
        mode_config = PLAY_MODES[mode]
        self.playable_min = mode_config['playable_min']
        self.playable_max = mode_config['playable_max']
        self.note_to_key = mode_config['note_to_key']
        
        # 跟踪当前按下的键
        self._pressed_keys = set()
        
        # 添加缺失的属性
        self._lock = threading.Lock()
        self.total_time = 0
        self.start_time = 0
        self.pause_time = 0
        self.total_pause_time = 0
        self.use_message_mode = False  # 默认使用模拟按键模式
        self.preview_mode = False
        
        # 缓存相关
        self._note_key_cache = {}
        self._cached_mid = None
        
        # 初始化 pygame
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

    def set_mode(self, mode: str):
        """设置演奏模式"""
        if mode not in PLAY_MODES:
            raise ValueError(f"不支持的模式: {mode}")
            
        self.current_mode = mode
        mode_config = PLAY_MODES[mode]
        self.playable_min = mode_config['playable_min']
        self.playable_max = mode_config['playable_max']
        self.note_to_key = mode_config['note_to_key']
        print(f"已切换到{mode_config['name']}")

    def _analyze_tracks(self, mid):
        """分析MIDI文件的音轨信息（内部方法）"""
        tracks_info = []
        
        # 收集所有音符
        all_notes = []
        all_velocities = []
        
        # 添加"所有音轨"选项
        tracks_info.append({
            'index': -1,
            'name': "所有音轨",
            'notes_count': 0,
            'note_range': (0, 0)
        })
        
        for i, track in enumerate(mid.tracks):
            notes = []
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)
                    all_notes.append(msg.note)
                    all_velocities.append(msg.velocity)
            
            if notes:  # 只添加包含音符的音轨
                track_name = track.name if hasattr(track, 'name') else f"音轨 {i+1}"
                tracks_info.append({
                    'index': i,
                    'name': self._decode_track_name(track_name),
                    'notes_count': len(notes),
                    'note_range': (min(notes), max(notes))
                })
        
        # 更新"所有音轨"的信息
        if all_notes:
            tracks_info[0].update({
                'notes_count': len(all_notes),
                'note_range': (min(all_notes), max(all_notes))
            })
        
        # 使用优化器找到最佳偏移
        if all_notes:
            offset, score = self.note_optimizer.find_best_offset(all_notes, all_velocities)
            self.note_offset = offset
            print(f"找到最佳音高偏移: {offset} (得分: {score:.2f})")
        
        return tracks_info

    # 可以保留原来的公共方法作为包装器
    def analyze_tracks(self, mid):
        """分析MIDI文件的音轨信息"""
        try:
            tracks_info = []
            
            # 添加"所有音轨"选项
            tracks_info.append({
                'index': -1,
                'name': "所有音轨",
                'notes_count': 0,
                'note_range': (0, 0)
            })
            
            # 收集所有音符
            all_notes = []
            all_velocities = []
            
            for i, track in enumerate(mid.tracks):
                notes = []
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        notes.append(msg.note)
                        all_notes.append(msg.note)
                        all_velocities.append(msg.velocity)
                
                if notes:  # 只添加包含音符的音轨
                    track_name = track.name if hasattr(track, 'name') else f"音轨 {i+1}"
                    tracks_info.append({
                        'index': i,
                        'name': self._decode_track_name(track_name),
                        'notes_count': len(notes),
                        'note_range': (min(notes), max(notes))
                    })
            
            # 更新"所有音轨"的信息
            if all_notes:
                tracks_info[0].update({
                    'notes_count': len(all_notes),
                    'note_range': (min(all_notes), max(all_notes))
                })
            
            # 使用优化器找到最佳偏移
            if all_notes:
                offset, score = self.note_optimizer.find_best_offset(all_notes, all_velocities)
                self.note_offset = offset
                print(f"找到最佳音高偏移: {offset} (得分: {score:.2f})")
            
            self.tracks_info = tracks_info
            return tracks_info
            
        except Exception as e:
            print(f"分析音轨时出错: {str(e)}")
            return []

    def get_current_time(self):
        """获取当前播放时间"""
        try:
            with self._lock:
                if not self.playing:
                    return 0
                if self.paused:
                    return self.pause_time - self.start_time - self.total_pause_time
                return time.time() - self.start_time - self.total_pause_time
        except Exception as e:
            print(f"获取当前时间时出错: {str(e)}")
            return 0

    def get_total_time(self):
        """获取总时长"""
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

    def _press_key(self, key: str):
        """按下按键"""
        try:
            if key not in self._pressed_keys:
                if self.use_message_mode:
                    if not self.key_sender:
                        self.key_sender = KeySender()
                    self.key_sender.send_key(key, True)
                else:
                    # 处理组合键
                    if '+' in key:
                        parts = key.split('+')
                        # 按下修饰键
                        for modifier in parts[:-1]:
                            keyboard.press(modifier.lower())
                        # 按下主键
                        keyboard.press(parts[-1].lower())
                    else:
                        keyboard.press(key.lower())
                
                self._pressed_keys.add(key)
                print(f"按下按键: {key}")
        except Exception as e:
            print(f"按下按键出错 {key}: {str(e)}")

    def _release_key(self, key: str):
        """释放按键"""
        try:
            if key in self._pressed_keys:
                if self.use_message_mode:
                    if self.key_sender:
                        self.key_sender.send_key(key, False)
                else:
                    # 处理组合键
                    if '+' in key:
                        parts = key.split('+')
                        # 先释放主键
                        keyboard.release(parts[-1].lower())
                        # 再释放修饰键（反序）
                        for modifier in reversed(parts[:-1]):
                            keyboard.release(modifier.lower())
                    else:
                        keyboard.release(key.lower())
                
                self._pressed_keys.remove(key)
                print(f"释放按键: {key}")
        except Exception as e:
            print(f"释放按键出错 {key}: {str(e)}")

    def _release_all_keys(self):
        """释放所有按下的键"""
        try:
            # 创建一个副本，因为在循环中会修改 _pressed_keys
            pressed_keys = self._pressed_keys.copy()
            for key in pressed_keys:
                self._release_key(key)
            self._pressed_keys.clear()
        except Exception as e:
            print(f"释放所有按键时出错: {str(e)}")

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
            hwnd = win32gui.FindWindow(None, self.target_window_name)
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
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                # 将窗口置于前台
                win32gui.SetForegroundWindow(hwnd)
                return True
            return False
        except Exception as e:
            print(f"切换窗口时出错: {str(e)}")
            return False

    def _sanitize_midi_file(self, midi_file: str) -> Tuple[Optional[mido.MidiFile], str]:
        """修复和验证MIDI文件
        Args:
            midi_file: MIDI文件路径
        Returns:
            (修复后的MidiFile对象, 错误信息)
        """
        try:
            # 首先尝试正常加载
            mid = mido.MidiFile(midi_file)
            return mid, ""
        except Exception as e:
            try:
                # 如果正常加载失败，尝试修复模式
                fixed_mid = mido.MidiFile()
                original_mid = mido.MidiFile(midi_file, clip=True)  # 使用clip模式
                
                # 复制文件属性
                fixed_mid.ticks_per_beat = original_mid.ticks_per_beat
                fixed_mid.type = original_mid.type
                
                # 处理每个音轨
                for track in original_mid.tracks:
                    fixed_track = mido.MidiTrack()
                    for msg in track:
                        try:
                            # 修复常见问题
                            if msg.type == 'note_on' or msg.type == 'note_off':
                                # 确保音符值在有效范围内
                                if hasattr(msg, 'note'):
                                    msg.note = max(0, min(127, msg.note))
                                # 确保力度值在有效范围内
                                if hasattr(msg, 'velocity'):
                                    msg.velocity = max(0, min(127, msg.velocity))
                            # 添加修复后的消息
                            fixed_track.append(msg)
                        except Exception as msg_error:
                            print(f"跳过无效的MIDI消息: {msg_error}")
                            continue
                    
                    fixed_mid.tracks.append(fixed_track)
                
                return fixed_mid, "MIDI文件已修复"
            except Exception as fix_error:
                return None, f"无法修复MIDI文件: {str(fix_error)}"

    def play_file(self, file_path: str, preview_mode: bool = False, preview_original: bool = False) -> bool:
        """播放MIDI文件"""
        try:
            if not os.path.exists(file_path):
                return False
            
            self.current_file = file_path
            self.playing = True
            self.paused = False
            self.preview_mode = preview_mode
            
            # 创建播放线程
            def play_thread():
                try:
                    mid = mido.MidiFile(file_path)
                    start_time = time.time()
                    
                    # 重置所有状态
                    self._pressed_keys.clear()
                    self.sound_manager.stop_all()
                    
                    for msg in mid.play():
                        if not self.playing:
                            break
                        
                        if self.paused:
                            time.sleep(0.001)
                            continue
                        
                        if msg.type == 'note_on' or msg.type == 'note_off':
                            # 处理音符事件
                            is_note_on = msg.type == 'note_on' and msg.velocity > 0
                            
                            if preview_mode:
                                # 预览模式：根据是否为原始预览决定是否应用音符偏移
                                note = msg.note if preview_original else (msg.note + self.note_offset)
                                if is_note_on:
                                    self.sound_manager.play_note(note, msg.velocity, preview_original)
                                else:
                                    self.sound_manager.stop_note(note, preview_original)
                            else:
                                # 正常模式：模拟按键
                                adjusted_note = msg.note + self.note_offset
                                if self.playable_min <= adjusted_note <= self.playable_max:
                                    key = self.note_to_key.get(adjusted_note)
                                    if key:
                                        if is_note_on:
                                            self._press_key(key)
                                        else:
                                            self._release_key(key)
                    
                    # 播放结束后清理
                    self.playing = False
                    self._release_all_keys()
                    self.sound_manager.stop_all()
                    
                except Exception as e:
                    print(f"播放线程出错: {str(e)}")
                    self.playing = False
                    self._release_all_keys()
                    self.sound_manager.stop_all()
            
            # 启动播放线程
            self.play_thread = threading.Thread(target=play_thread)
            self.play_thread.daemon = True
            self.play_thread.start()
            return True
            
        except Exception as e:
            print(f"播放MIDI文件时出错: {str(e)}")
            return False 

    def _play_thread(self):
        """MIDI播放线程"""
        try:
            if not self._cached_mid:
                self._cached_mid = mido.MidiFile(self.current_file)
                
            mid = self._cached_mid
            is_playing = True
            
            # 获取选中的音轨和预览模式状态
            with self._lock:
                selected_track = self.selected_track
                preview_mode = self.preview_mode
                preview_original = self.preview_original
            
            # 重置计时器
                with self._lock:
                    self.start_time = time.time() * 1000
                    self.pause_time = 0
                    self.total_pause_time = 0
            
            # 播放MIDI消息
            for msg in mid.play():
                # 检查是否需要暂停或停止
                with self._lock:
                    if not self.playing:
                        is_playing = False
                        break
                    if self.paused:
                        if self.pause_time == 0:
                            self.pause_time = time.time() * 1000
                            time.sleep(0.1)
                            continue
                    elif self.pause_time > 0:
                        self.total_pause_time += time.time() * 1000 - self.pause_time
                        self.pause_time = 0
                    
                    # 更新预览模式状态
                    preview_mode = self.preview_mode
                    preview_original = self.preview_original
                
                # 处理音符消息
                if msg.type == 'note_on' and hasattr(msg, 'channel'):
                    # selected_track 为 None 时会播放所有音轨
                    if selected_track is None or msg.channel == selected_track:
                        note = self._adjust_note(msg.note)
                        if preview_mode:
                            # 预览模式：同时播放原始和调整后的音符
                            if msg.velocity > 0:
                                if preview_original:
                                    # 播放原始音高
                                    self.sound_manager.play_note(msg.note, msg.velocity, True)
                                else:
                                    # 播放调整后的音高
                                    self.sound_manager.play_note(note, msg.velocity, False)
                            else:
                                if preview_original:
                                    self.sound_manager.stop_note(msg.note, True)
                                else:
                                    self.sound_manager.stop_note(note, False)
                        elif note in NOTE_TO_KEY:  # 非预览模式：触发键盘
                            if msg.velocity > 0:
                                self._press_key(NOTE_TO_KEY[note])
                            else:
                                self._release_key(NOTE_TO_KEY[note])
                elif msg.type == 'note_off' and hasattr(msg, 'channel'):
                    if selected_track is None or msg.channel == selected_track:
                        note = self._adjust_note(msg.note)
                        if preview_mode:
                            # 预览模式：停止音符
                            if preview_original:
                                self.sound_manager.stop_note(msg.note, True)
                            else:
                                self.sound_manager.stop_note(note, False)
                        elif note in NOTE_TO_KEY:  # 非预览模式：释放键盘
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
                # 如果是消息模式，不需要检查窗口状态
                if not self.use_message_mode:
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
            
            # 如果是预览模式，停止所有音符
            if hasattr(self, 'preview_mode') and self.preview_mode:
                self.sound_manager.stop_all()
            
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

    def _adjust_note(self, note: int) -> int:
        """智能调整音符"""
        # 使用缓存
        cache_key = (note, self.note_offset)
        if cache_key in self._note_key_cache:
            return self._note_key_cache[cache_key] 
        
        shifted_note = note + self.note_offset
        original_octave = shifted_note // 12
        interval = shifted_note % 12
        
        # 如果音符已经在可播放范围内，尽量保持原样
        if self.PLAYABLE_MIN <= shifted_note <= self.PLAYABLE_MAX:
            if interval in PENTATONIC_INTERVALS:
                # 完全符合要求，直接返回
                self._note_key_cache[cache_key] = shifted_note
                return shifted_note
            else:
                # 在同一个八度内寻找最近的五声音阶音符
                base_note = original_octave * 12
                candidates = []
                for p_interval in PENTATONIC_INTERVALS:
                    candidate = base_note + p_interval
                    if self.PLAYABLE_MIN <= candidate <= self.PLAYABLE_MAX:
                        distance = abs(shifted_note - candidate)
                        candidates.append((candidate, distance))
                
                if candidates:
                    # 选择最近的音符
                    best_note = min(candidates, key=lambda x: x[1])[0]
                    self._note_key_cache[cache_key] = best_note
                    return best_note
        
        # 如果音符超出范围，尝试最小的调整
        if shifted_note < self.PLAYABLE_MIN:
            # 向上找最近的八度
            while shifted_note < self.PLAYABLE_MIN:
                shifted_note += 12
        elif shifted_note > self.PLAYABLE_MAX:
            # 向下找最近的八度
            while shifted_note > self.PLAYABLE_MAX:
                shifted_note -= 12
        
        # 在调整后的八度内找最近的五声音阶音符
        base_note = (shifted_note // 12) * 12
        candidates = []
        for p_interval in PENTATONIC_INTERVALS:
            candidate = base_note + p_interval
            if self.PLAYABLE_MIN <= candidate <= self.PLAYABLE_MAX:
                distance = abs(shifted_note - candidate)
                candidates.append((candidate, distance))
        
        if candidates:
            best_note = min(candidates, key=lambda x: x[1])[0]
            self._note_key_cache[cache_key] = best_note
            return best_note
        
        # 如果还是找不到合适的音符，使用最接近的可播放音符
        best_note = max(min(shifted_note, self.PLAYABLE_MAX), self.PLAYABLE_MIN)
        self._note_key_cache[cache_key] = best_note
        return best_note

    def _check_active_window(self):
        """检查当前活动窗口是否为目标窗口"""
        try:
            # 如果是消息模式，不需要检查窗口状态
            if self.use_message_mode:
                return True
            
            current_time = time.time()
            # 使用缓存的状态
            if current_time - self.last_window_check < self.window_check_interval:
                return self.last_window_state
                
            self.last_window_check = current_time
            active_window = win32gui.GetForegroundWindow()
            window_title = win32gui.GetWindowText(active_window)
            
            # 更新缓存的状态
            self.last_window_state = (window_title == self.target_window_name)
            return self.last_window_state
            
        except Exception as e:
            print(f"检查活动窗口时出错: {str(e)}")
            return False 

    def start_recording(self):
        """开始记录按键序列"""
        self.recording = True
        self.key_sequence.start_recording()
    
    def stop_recording(self):
        """停止记录按键序列"""
        self.recording = False
        self.key_sequence.stop_recording()
    
    def save_sequence(self, filepath: str):
        """保存按键序列"""
        self.key_sequence.save_to_file(filepath)
    
    def load_sequence(self, sequence_file: str) -> bool:
        """加载按键序列"""
        try:
            self.current_sequence = KeySequence.load_from_file(sequence_file)
            # 添加调试信息
            print(f"加载序列: 包含 {len(self.current_sequence.events)} 个事件")
            return True
        except Exception as e:
            print(f"加载序列文件时出错: {str(e)}")
            return False

    def play_loaded_sequence(self):
        """播放已加载的序列"""
        if not hasattr(self, 'current_sequence') or not self.current_sequence.events:
            print("没有可播放的序列")
            return False
        
        def play_thread():
            try:
                self.playing = True
                start_time = time.time() * 1000  # 转换为毫秒
                
                for event in self.current_sequence.events:
                    if not self.playing:
                        break
                        
                    # 根据速度倍率调整等待时间
                    target_time = event.time / self.playback_speed
                    current_time = time.time() * 1000 - start_time
                    wait_time = target_time - current_time
                    
                    if wait_time > 0:
                        time.sleep(wait_time / 1000.0)  # 转换回秒
                    
                    # 执行按键事件
                    if event.press:
                        self._press_key(event.key)
                    else:
                        self._release_key(event.key)
                        
            except Exception as e:
                print(f"播放序列时出错: {str(e)}")
            finally:
                self.playing = False
                self._release_all_keys()
        
        # 在新线程中播放序列
        self.play_thread = threading.Thread(target=play_thread)
        self.play_thread.daemon = True
        self.play_thread.start()
        return True

    def stop_sequence(self):
        """停止序列播放"""
        try:
            # 设置停止标志
            self.playing = False
            
            # 等待播放线程结束
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=1.0)
            
            # 释放所有按键
            self._release_all_keys()
            
            # 清理状态
            self.play_thread = None
            
        except Exception as e:
            print(f"停止序列播放时出错: {str(e)}")
        finally:
            self.playing = False

    def select_track(self, track_info):
        """选择要播放的音轨"""
        try:
            self.selected_track = track_info['index'] if track_info else None
            print(f"已选择音轨: {track_info['name'] if track_info else '所有音轨'}")
        except Exception as e:
            print(f"选择音轨时出错: {str(e)}")

    def convert_and_save_sequence(self, midi_file: str, output_file: str):
        """将MIDI文件转换为按键序列并保存"""
        try:
            # 使用当前的优化器设置创建序列
            mode = '36key' if self.use_36key_mode else '21key'
            
            # 如果有选中的音轨，只转换该音轨
            if self.selected_track:
                sequence = KeySequence.from_midi(
                    midi_file, 
                    mode=mode,
                    note_offset=self.note_offset,
                    selected_track=self.selected_track  # 添加选中的音轨索引
                )
            else:
                sequence = KeySequence.from_midi(
                    midi_file, 
                    mode=mode,
                    note_offset=self.note_offset
                )
            
            # 添加调试信息
            print(f"转换序列: 包含 {len(sequence.events)} 个事件")
            
            sequence.save_to_file(output_file)
            return True
        except Exception as e:
            print(f"转换MIDI文件时出错: {str(e)}")
            return False

    def load_and_play_sequence(self, sequence_file: str):
        """加载并播放按键序列
        Args:
            sequence_file: 序列文件路径
        """
        try:
            sequence = KeySequence.load_from_file(sequence_file)
            self.play_sequence(sequence)
            return True
        except Exception as e:
            print(f"加载序列文件时出错: {str(e)}")
            return False

    def __del__(self):
        """析构函数：清理资源"""
        try:
            self.sound_manager.stop_all()
            pygame.quit()
        except:
            pass 

    def set_play_mode(self, mode: str):
        """设置演奏模式
        Args:
            mode: '21key' 或 '36key'
        """
        self.use_36key_mode = (mode == '36key')
        # 更新优化器的模式
        self.note_optimizer = NoteRangeOptimizer(mode=mode) 

    def set_speed(self, speed: float):
        """设置播放速度"""
        try:
            self.playback_speed = max(0.5, min(2.0, speed))
            print(f"播放速度已更新为: {self.playback_speed:.1f}x")
        except Exception as e:
            print(f"设置播放速度时出错: {str(e)}")
    
    def play_sequence(self, sequence: KeySequence):
        """播放按键序列"""
        if not sequence.events:
            return
            
        self.playing = True
        start_time = time.time() * 1000  # 转换为毫秒
        
        try:
            for event in sequence.events:
                if not self.playing:
                    break
                    
                # 根据速度倍率调整等待时间
                target_time = event.time / self.playback_speed
                current_time = time.time() * 1000 - start_time
                wait_time = target_time - current_time
                
                if wait_time > 0:
                    time.sleep(wait_time / 1000.0)  # 转换回秒
                
                # 执行按键事件
                if event.press:
                    self._press_key(event.key)
                else:
                    self._release_key(event.key)
                    
        except Exception as e:
            print(f"播放序列时出错: {str(e)}")
        finally:
            self.playing = False
            self._release_all_keys() 

    def play_midi(self, midi_file: str, preview_mode: bool = False):
        """播放MIDI文件
        Args:
            midi_file: MIDI文件路径
            preview_mode: 是否为预览模式
        """
        try:
            self.playing = True
            mid = mido.MidiFile(midi_file)
            start_time = time.time() * 1000  # 转换为毫秒
            
            # 跟踪每个音轨的音符状态
            track_note_states = {}
            
            for track_idx, track in enumerate(mid.tracks):
                # 如果选择了特定音轨，只播放该音轨
                if self.selected_track is not None and track_idx != self.selected_track:
                    continue
                    
                track_note_states[track_idx] = {}
                current_time = 0
                
                for msg in track:
                    if not self.playing:
                        break
                        
                    # 计算等待时间（考虑播放速度）
                    wait_time = msg.time * 1000 / mid.ticks_per_beat * 0.5  # 转换为毫秒
                    wait_time = wait_time / self.playback_speed  # 应用速度倍率
                    
                    if wait_time > 0:
                        time.sleep(wait_time / 1000.0)  # 转换回秒
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        # 处理音符按下
                        adjusted_note = msg.note
                        if not preview_mode:
                            adjusted_note += self.note_offset
                        
                        if self.playable_min <= adjusted_note <= self.playable_max:
                            if adjusted_note in self.note_to_key:
                                key = self.note_to_key[adjusted_note]
                                self._press_key(key)
                                track_note_states[track_idx][msg.note] = key
                                
                    elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                        # 处理音符释放
                        if msg.note in track_note_states[track_idx]:
                            key = track_note_states[track_idx][msg.note]
                            self._release_key(key)
                            del track_note_states[track_idx][msg.note]
                            
            self.playing = False
            self._release_all_keys()
            
        except Exception as e:
            print(f"播放MIDI文件时出错: {str(e)}")
            self.playing = False
            self._release_all_keys() 

    def play_midi_file(self, midi_file: str):
        """播放MIDI文件"""
        try:
            print(f"开始播放MIDI文件，当前速度: {self.playback_speed:.1f}x")
            self.playing = True
            mid = mido.MidiFile(midi_file)
            start_time = time.time()
            tempo = 500000  # 默认tempo (microseconds per beat)
            
            # 跟踪每个音轨的音符状态
            track_note_states = {}
            
            for track_idx, track in enumerate(mid.tracks):
                if self.selected_track is not None and track_idx != self.selected_track:
                    continue
                    
                track_note_states[track_idx] = {}
                current_time = 0
                
                for msg in track:
                    if not self.playing:
                        break
                    
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                        continue
                        
                    # 计算等待时间（考虑播放速度和tempo）
                    seconds_per_tick = tempo / (mid.ticks_per_beat * 1000000)
                    wait_time = msg.time * seconds_per_tick / self.playback_speed
                    
                    if wait_time > 0:
                        time.sleep(wait_time)
                        if msg.time > 0:  # 只在有实际延迟时打印
                            print(f"等待时间: {wait_time:.3f}秒 (原始: {msg.time * seconds_per_tick:.3f}秒)")
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        adjusted_note = msg.note + self.note_offset
                        if self.playable_min <= adjusted_note <= self.playable_max:
                            if adjusted_note in self.note_to_key:
                                key = self.note_to_key[adjusted_note]
                                self._press_key(key)
                                track_note_states[track_idx][msg.note] = key
                                print(f"按下音符: {msg.note} -> {key}")
                                
                    elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                        if msg.note in track_note_states[track_idx]:
                            key = track_note_states[track_idx][msg.note]
                            self._release_key(key)
                            del track_note_states[track_idx][msg.note]
                            print(f"释放音符: {msg.note} -> {key}")
            
            self.playing = False
            self._release_all_keys()
            print("MIDI文件播放完成")
            
        except Exception as e:
            print(f"播放MIDI文件时出错: {str(e)}")
            self.playing = False
            self._release_all_keys()

    def preview_midi(self, midi_file: str, use_original: bool = True):
        """预览MIDI文件"""
        try:
            print(f"开始预览MIDI文件，使用原始音高: {use_original}, 当前速度: {self.playback_speed:.1f}x")
            self.playing = True
            self.preview_mode = True  # 设置预览模式
            mid = mido.MidiFile(midi_file)
            start_time = time.time()
            tempo = 500000  # 默认tempo
            
            track_note_states = {}
            
            for track_idx, track in enumerate(mid.tracks):
                if self.selected_track is not None and track_idx != self.selected_track:
                    continue
                    
                track_note_states[track_idx] = {}
                
                for msg in track:
                    if not self.playing:
                        break
                    
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                        continue
                        
                    seconds_per_tick = tempo / (mid.ticks_per_beat * 1000000)
                    wait_time = msg.time * seconds_per_tick / self.playback_speed
                    
                    if wait_time > 0:
                        time.sleep(wait_time)
                        if msg.time > 0:
                            print(f"预览等待时间: {wait_time:.3f}秒 (原始: {msg.time * seconds_per_tick:.3f}秒)")
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        note = msg.note
                        if not use_original:
                            note += self.note_offset
                            
                        if self.playable_min <= note <= self.playable_max:
                            if note in self.note_to_key:
                                key = self.note_to_key[note]
                                self._press_key(key)
                                track_note_states[track_idx][msg.note] = key
                                print(f"预览按下音符: {msg.note} -> {key}")
                                
                    elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                        if msg.note in track_note_states[track_idx]:
                            key = track_note_states[track_idx][msg.note]
                            self._release_key(key)
                            del track_note_states[track_idx][msg.note]
            
            self.playing = False
            self.preview_mode = False  # 恢复非预览模式
            self._release_all_keys()
            print("MIDI预览完成")
            
        except Exception as e:
            print(f"预览MIDI文件时出错: {str(e)}")
            self.playing = False
            self.preview_mode = False
            self._release_all_keys()

    def start_playback(self):
        """开始播放"""
        try:
            if not self.current_file:
                print("没有选择MIDI文件")
                return False
            
            if self.playing:
                print("已经在播放中")
                return False
            
            def play_thread():
                try:
                    self.playing = True
                    # 使用新的播放方法
                    self.play_midi_file(self.current_file)
                except Exception as e:
                    print(f"播放线程出错: {str(e)}")
                finally:
                    self.playing = False
                    self._release_all_keys()
            
            # 在新线程中播放
            self.play_thread = threading.Thread(target=play_thread)
            self.play_thread.daemon = True
            self.play_thread.start()
            return True
            
        except Exception as e:
            print(f"启动播放失败: {str(e)}")
            return False

    def toggle_preview(self, use_original: bool = True):
        """切换预览模式
        Args:
            use_original: 是否使用原始音高
        """
        try:
            if not self.current_file:
                print("没有选择MIDI文件")
                return
            
            if self.playing:
                self.stop_playback()
            else:
                def preview_thread():
                    try:
                        self.playing = True
                        # 使用新的预览方法
                        self.preview_midi(self.current_file, use_original)
                    except Exception as e:
                        print(f"预览线程出错: {str(e)}")
                    finally:
                        self.playing = False
                        self._release_all_keys()
                
                # 在新线程中预览
                self.play_thread = threading.Thread(target=preview_thread)
                self.play_thread.daemon = True
                self.play_thread.start()
                
        except Exception as e:
            print(f"切换预览模式时出错: {str(e)}") 

    def set_current_file(self, file_path: str):
        """设置当前MIDI文件"""
        try:
            self.current_file = file_path
            print(f"已设置当前文件: {file_path}")
            # 分析新文件的音轨
            self.analyze_tracks(mido.MidiFile(file_path))
        except Exception as e:
            print(f"设置当前文件时出错: {str(e)}") 

    def stop_playback(self):
        """停止播放"""
        try:
            with self._lock:
                self.playing = False
                self.paused = False
                self._release_all_keys()
                self.total_time = 0
                self.start_time = 0
                self.pause_time = 0
                self.total_pause_time = 0
        except Exception as e:
            print(f"停止播放时出错: {str(e)}") 