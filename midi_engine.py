import mido
import keyboard
import time
from typing import Optional, List, Dict, Callable

class MidiEngine:
    """
    MIDI播放引擎核心类
    独立于UI的MIDI文件管理和播放控制
    """
    def __init__(self):
        self.midi_files: List[str] = []  # MIDI文件列表
        self.current_index: int = -1  # 当前播放的文件索引
        self.current_track: Optional[int] = None  # 当前选中的音轨
        self.playing: bool = False  # 是否正在播放
        self.paused: bool = False  # 是否暂停
        
        # 回调函数
        self.on_playback_started: Optional[Callable] = None
        self.on_playback_stopped: Optional[Callable] = None
        self.on_playback_paused: Optional[Callable] = None
        self.on_track_changed: Optional[Callable] = None
        self.on_song_changed: Optional[Callable] = None
        
        # 播放状态
        self._current_time: float = 0
        self._total_time: float = 0
        self.tracks_info: List[Dict] = []

    def load_directory(self, directory: str) -> List[str]:
        """加载目录中的所有MIDI文件"""
        self.midi_files = []
        # ... 实现文件加载逻辑 ...
        return self.midi_files

    def analyze_midi_file(self, file_path: str) -> Dict:
        """分析MIDI文件信息"""
        try:
            mid = mido.MidiFile(file_path)
            # ... 实现MIDI分析逻辑 ...
            return {
                'tracks': self.tracks_info,
                'duration': mid.length
            }
        except Exception as e:
            print(f"分析MIDI文件出错: {str(e)}")
            return {}

    def play(self, index: Optional[int] = None) -> bool:
        """开始播放指定索引的MIDI文件"""
        if index is not None:
            self.current_index = index
        
        if not (0 <= self.current_index < len(self.midi_files)):
            return False

        try:
            # ... 实现播放逻辑 ...
            self.playing = True
            self.paused = False
            
            if self.on_playback_started:
                self.on_playback_started()
            return True
        except Exception as e:
            print(f"播放出错: {str(e)}")
            return False

    def pause(self) -> None:
        """暂停/继续播放"""
        self.paused = not self.paused
        if self.on_playback_paused:
            self.on_playback_paused(self.paused)

    def stop(self) -> None:
        """停止播放"""
        self.playing = False
        self.paused = False
        if self.on_playback_stopped:
            self.on_playback_stopped()

    def set_track(self, track_index: Optional[int]) -> None:
        """设置当前音轨"""
        self.current_track = track_index
        if self.on_track_changed:
            self.on_track_changed(track_index)

    def get_playback_status(self) -> Dict:
        """获取当前播放状态"""
        return {
            'playing': self.playing,
            'paused': self.paused,
            'current_time': self._current_time,
            'total_time': self._total_time,
            'current_file': self.midi_files[self.current_index] if self.current_index >= 0 else None
        } 
#触发更新