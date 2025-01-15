import json
import time
from typing import List, Dict, Union, Optional
from dataclasses import dataclass

@dataclass
class KeyEvent:
    """按键事件"""
    key: str           # 按键
    press: bool       # True为按下，False为释放
    time: float       # 事件时间（相对于序列开始）
    velocity: int = 127  # 按键力度（可选）

class KeySequence:
    """按键序列管理器"""
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
            self.events.append(KeyEvent(key, press, current_time, velocity))
    
    def save_to_file(self, filepath: str):
        """保存序列到文件"""
        sequence_data = {
            'events': [
                {
                    'key': e.key,
                    'press': e.press,
                    'time': e.time,
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
            sequence.events = [
                KeyEvent(**event) for event in data['events']
            ]
        return sequence
    
    def get_formatted_sequence(self) -> str:
        """获取格式化的序列字符串"""
        if not self.events:
            return "空序列"
            
        result = []
        last_time = 0
        
        for event in self.events:
            # 计算与上一个事件的时间间隔
            interval = event.time - last_time
            last_time = event.time
            
            # 添加时间间隔（如果有）
            if interval > 0.01:  # 忽略极小的间隔
                result.append(f"[等待 {interval:.3f}秒]")
            
            # 添加按键事件
            action = "按下" if event.press else "释放"
            result.append(f"{action} {event.key}")
        
        return "\n".join(result)