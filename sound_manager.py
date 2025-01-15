import os
import pygame
from typing import Dict

class SoundManager:
    """音符音频管理类"""
    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        
        # 加载音符音频文件
        self.sounds: Dict[int, pygame.mixer.Sound] = {}
        self._load_sounds()
        
        # 当前播放的声音通道
        self.active_channels: Dict[int, pygame.mixer.Channel] = {}
        
        # 添加音轨标识
        self.active_channels_original = {}  # 原始音轨的通道
        self.active_channels_adjusted = {}  # 调整后音轨的通道
        
        # 分配通道组
        total_channels = 64
        pygame.mixer.set_num_channels(total_channels)
        self.channels_original = [pygame.mixer.Channel(i) for i in range(total_channels//2)]
        self.channels_adjusted = [pygame.mixer.Channel(i) for i in range(total_channels//2, total_channels)]
    
    def _load_sounds(self):
        """加载音符音频文件"""
        sounds_dir = os.path.join(os.path.dirname(__file__), 'sounds')
        if not os.path.exists(sounds_dir):
            print(f"警告: 未找到音频文件目录 {sounds_dir}")
            return
            
        for file in os.listdir(sounds_dir):
            if file.endswith('.wav'):
                try:
                    note = int(file.split('.')[0])  # 文件名为音符编号
                    sound_path = os.path.join(sounds_dir, file)
                    self.sounds[note] = pygame.mixer.Sound(sound_path)
                except Exception as e:
                    print(f"加载音频文件出错 {file}: {str(e)}")
    
    def play_note(self, note: int, velocity: int = 127, is_original: bool = False):
        """播放音符
        Args:
            note: 音符编号
            velocity: 力度值
            is_original: 是否为原始音高
        """
        if note in self.sounds:
            volume = min(velocity / 127.0, 1.0)
            
            # 根据类型选择通道组
            channels = self.channels_original if is_original else self.channels_adjusted
            active_channels = self.active_channels_original if is_original else self.active_channels_adjusted
            
            # 获取空闲通道
            for channel in channels:
                if not channel.get_busy():
                    channel.set_volume(volume)
                    channel.play(self.sounds[note])
                    active_channels[note] = channel
                    break
    
    def stop_note(self, note: int, is_original: bool = False):
        """停止音符"""
        active_channels = self.active_channels_original if is_original else self.active_channels_adjusted
        if note in active_channels:
            channel = active_channels[note]
            channel.stop()
            del active_channels[note]
    
    def stop_all(self):
        """停止所有音符"""
        for channel in self.channels_original + self.channels_adjusted:
            channel.stop()
        self.active_channels_original.clear()
        self.active_channels_adjusted.clear() 
#触发更新