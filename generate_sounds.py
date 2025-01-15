from synthesizer import Player, Synthesizer, Waveform
import os
import numpy as np
from scipy.io import wavfile

def generate_piano_note(note_number, duration=1.0, sample_rate=44100):
    """生成钢琴音符的音频数据"""
    # 计算频率 (A4 = 69 = 440Hz)
    frequency = 440.0 * (2.0 ** ((note_number - 69) / 12.0))
    
    # 创建合成器和播放器
    synthesizer = Synthesizer(osc1_waveform=Waveform.sine, osc1_volume=1.0, use_osc2=False)
    player = Player()
    player.open_stream()
    
    # 生成音频数据
    samples = synthesizer.generate_constant_wave(frequency, duration)
    
    # 应用包络（ADSR）
    attack = int(0.05 * sample_rate)
    decay = int(0.1 * sample_rate)
    sustain_level = 0.7
    release = int(0.3 * sample_rate)
    
    envelope = np.ones(len(samples))
    # Attack
    envelope[:attack] = np.linspace(0, 1, attack)
    # Decay
    envelope[attack:attack+decay] = np.linspace(1, sustain_level, decay)
    # Sustain (already set to sustain_level)
    # Release
    envelope[-release:] = np.linspace(sustain_level, 0, release)
    
    # 应用包络
    samples = samples * envelope
    
    return samples

def create_sounds_directory():
    """创建sounds目录"""
    sounds_dir = 'sounds'
    if not os.path.exists(sounds_dir):
        os.makedirs(sounds_dir)
    return sounds_dir

def generate_all_notes():
    """生成所有需要的音符文件"""
    sounds_dir = create_sounds_directory()
    
    # 生成从MIDI音符48到83的音频文件（对应游戏的音域）
    for note in range(48, 84):
        print(f"生成音符 {note}")
        samples = generate_piano_note(note)
        output_path = os.path.join(sounds_dir, f"{note}.wav")
        wavfile.write(output_path, 44100, (samples * 32767).astype(np.int16))

if __name__ == "__main__":
    print("开始生成音符音频文件...")
    generate_all_notes()
    print("音符音频文件生成完成！") 