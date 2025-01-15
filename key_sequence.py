import json
import time
import mido
from typing import List, Dict, Union, Optional
from dataclasses import dataclass
from keyboard_mapping import PLAY_MODES

@dataclass
class KeyEvent:
    """按键事件"""
    key: str           # 按键
    press: bool       # True为按下，False为释放
    time: float       # 事件时间（相对于序列开始）
    note: int = 0     # MIDI音符编号
    velocity: int = 127  # 按键力度

class KeySequence:
    def __init__(self):
        self.events: List[KeyEvent] = []
        self.start_time: float = 0
        self.recording: bool = False
    
    def start_recording(self):
        """开始记录"""
        self.events.clear()
        self.start_time = time.time()
        self.recording = True
    
    def stop_recording(self):
        """停止记录"""
        self.recording = False
    
    def add_event(self, key: str, press: bool, velocity: int = 127):
        """添加按键事件"""
        if self.recording:
            current_time = time.time() - self.start_time
            self.events.append(KeyEvent(
                key=key,
                press=press,
                time=current_time,
                velocity=velocity
            ))
    
    @classmethod
    def from_midi(cls, midi_file: str, mode: str = '21key', note_offset: int = 0, selected_track: int = None) -> 'KeySequence':
        """从MIDI文件创建按键序列
        Args:
            midi_file: MIDI文件路径
            mode: 演奏模式 ('21key' 或 '36key')
            note_offset: 音符偏移量
            selected_track: 选中的音轨索引（如果指定，则只转换该音轨）
        """
        sequence = cls()
        mid = mido.MidiFile(midi_file)
        
        # 获取当前模式的按键映射
        note_to_key = PLAY_MODES[mode]['note_to_key']
        playable_min = PLAY_MODES[mode]['playable_min']
        playable_max = PLAY_MODES[mode]['playable_max']
        
        # 计算时间转换因子
        tempo = 500000  # 默认tempo (microseconds per beat)
        ticks_per_beat = mid.ticks_per_beat
        
        def ticks_to_ms(ticks, current_tempo):
            """将ticks转换为毫秒，考虑当前tempo"""
            return (ticks * current_tempo) / (ticks_per_beat * 1000)
        
        # 收集所有音符事件和tempo变化
        raw_events = []
        tempo_changes = []  # 记录所有tempo变化
        
        # 跟踪每个音符在每个音轨上的状态
        track_note_states = {}  # {track_idx: {note: is_pressed}}
        
        for track_idx, track in enumerate(mid.tracks):
            # 如果指定了音轨，只处理选中的音轨
            if selected_track is not None and track_idx != selected_track:
                continue
            
            current_ticks = 0
            track_note_states[track_idx] = {}
            
            for msg in track:
                current_ticks += msg.time
                
                # 记录tempo变化
                if msg.type == 'set_tempo':
                    tempo_changes.append({
                        'tick': current_ticks,
                        'tempo': msg.tempo
                    })
                    continue
                    
                # 处理音符事件
                if msg.type in ['note_on', 'note_off']:
                    is_press = msg.type == 'note_on' and msg.velocity > 0
                    current_state = track_note_states[track_idx].get(msg.note, False)
                    
                    # 只在状态真正改变时记录事件
                    if is_press != current_state:
                        raw_events.append({
                            'tick': current_ticks,
                            'note': msg.note,
                            'velocity': msg.velocity,
                            'is_press': is_press,
                            'track': track_idx
                        })
                        track_note_states[track_idx][msg.note] = is_press
        
        # 按时间和优先级排序（按下优先于释放）
        raw_events.sort(key=lambda x: (x['tick'], not x['is_press']))
        tempo_changes.sort(key=lambda x: x['tick'])
        
        # 计算实际时间（考虑tempo变化）
        def calculate_real_time(tick):
            """计算考虑tempo变化后的实际时间"""
            current_tempo = 500000  # 默认tempo
            last_tempo_tick = 0
            last_tempo_time = 0
            
            for tempo_change in tempo_changes:
                if tempo_change['tick'] > tick:
                    break
                delta_ticks = tempo_change['tick'] - last_tempo_tick
                last_tempo_time += ticks_to_ms(delta_ticks, current_tempo)
                last_tempo_tick = tempo_change['tick']
                current_tempo = tempo_change['tempo']
            
            remaining_ticks = tick - last_tempo_tick
            return last_tempo_time + ticks_to_ms(remaining_ticks, current_tempo)
        
        # 转换为按键事件，合并所有音轨的事件
        note_states = {}  # 全局音符状态
        all_events = []
        
        for event in raw_events:
            adjusted_note = event['note'] + note_offset
            
            if playable_min <= adjusted_note <= playable_max and adjusted_note in note_to_key:
                key = note_to_key[adjusted_note]
                current_state = note_states.get(adjusted_note, False)
                
                # 检查状态变化的有效性
                if event['is_press'] != current_state:
                    event_time = calculate_real_time(event['tick'])
                    all_events.append(KeyEvent(
                        key=key,
                        press=event['is_press'],
                        time=event_time,
                        note=adjusted_note,
                        velocity=event['velocity'] if event['is_press'] else 0
                    ))
                    note_states[adjusted_note] = event['is_press']
        
        sequence.events = all_events
        
        # 验证序列的完整性
        note_validation = {}
        for event in sequence.events:
            note = event.note
            if event.press:
                if note in note_validation and note_validation[note]:
                    print(f"警告: 音符 {note} 重复按下")
                note_validation[note] = True
            else:
                if note not in note_validation or not note_validation[note]:
                    print(f"警告: 音符 {note} 在未按下的情况下释放")
                note_validation[note] = False
        
        # 检查序列结束时是否有未释放的音符
        unreleased_notes = [note for note, state in note_validation.items() if state]
        if unreleased_notes:
            print(f"警告: 序列结束时有未释放的音符: {unreleased_notes}")
            # 自动添加释放事件
            last_time = sequence.events[-1].time if sequence.events else 0
            for note in unreleased_notes:
                key = note_to_key[note]
                sequence.events.append(KeyEvent(
                    key=key,
                    press=False,
                    time=last_time + 1,  # 在最后一个事件后1毫秒
                    note=note,
                    velocity=0
                ))
        
        # 调试信息
        print(f"MIDI转换统计:")
        print(f"- 原始事件数: {len(raw_events)}")
        print(f"- Tempo变化数: {len(tempo_changes)}")
        print(f"- 转换后事件数: {len(sequence.events)}")
        print(f"- 按下事件数: {sum(1 for e in sequence.events if e.press)}")
        print(f"- 释放事件数: {sum(1 for e in sequence.events if not e.press)}")
        if tempo_changes:
            print(f"- Tempo范围: {min(t['tempo'] for t in tempo_changes)} - {max(t['tempo'] for t in tempo_changes)}")
        
        return sequence
    
    def get_formatted_sequence(self) -> str:
        """获取格式化的序列字符串"""
        if not self.events:
            return "空序列"
            
        result = []
        last_time = 0
        
        for event in self.events:
            # 计算与上一个事件的时间间隔（毫秒）
            interval = event.time - last_time
            last_time = event.time
            
            # 添加时间间隔（如果有）
            if interval > 1:  # 忽略1毫秒以下的间隔
                result.append(f"[等待 {interval:.3f}毫秒]")
            
            # 添加按键事件
            action = "按下" if event.press else "释放"
            note_info = f"(音符:{event.note})" if event.note else ""
            result.append(f"{action} {event.key} {note_info}")
        
        return "\n".join(result)
    
    def save_to_file(self, filepath: str):
        """保存序列到文件"""
        sequence_data = {
            'events': [
                {
                    'key': e.key,
                    'press': e.press,
                    'time': e.time,
                    'note': e.note,
                    'velocity': e.velocity
                } for e in self.events
            ]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(sequence_data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'KeySequence':
        """从文件加载序列"""
        sequence = cls()
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            sequence.events = [KeyEvent(**event) for event in data['events']]
        return sequence