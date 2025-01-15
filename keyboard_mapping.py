# 定义游戏音域的音符映射
GAME_NOTES = {
    # 高音区
    'Q': {'note': 72, 'name': '宫'},  # 高音宫
    'W': {'note': 74, 'name': '商'},  # 高音商
    'E': {'note': 76, 'name': '角'},  # 高音角
    'R': {'note': 77, 'name': '清角'},  # 高音清角
    'T': {'note': 79, 'name': '徵'},  # 高音徵
    'Y': {'note': 81, 'name': '羽'},  # 高音羽
    'U': {'note': 83, 'name': '变宫'},  # 高音变宫

    # 中音区
    'A': {'note': 60, 'name': '宫'},  # 中音宫
    'S': {'note': 62, 'name': '商'},  # 中音商
    'D': {'note': 64, 'name': '角'},  # 中音角
    'F': {'note': 65, 'name': '清角'},  # 中音清角
    'G': {'note': 67, 'name': '徵'},  # 中音徵
    'H': {'note': 69, 'name': '羽'},  # 中音羽
    'J': {'note': 71, 'name': '变宫'},  # 中音变宫

    # 低音区
    'Z': {'note': 48, 'name': '宫'},  # 低音宫
    'X': {'note': 50, 'name': '商'},  # 低音商
    'C': {'note': 52, 'name': '角'},  # 低音角
    'V': {'note': 53, 'name': '清角'},  # 低音清角
    'B': {'note': 55, 'name': '徵'},  # 低音徵
    'N': {'note': 57, 'name': '羽'},  # 低音羽
    'M': {'note': 59, 'name': '变宫'},  # 低音变宫
}

# 创建反向映射：MIDI音符到按键
NOTE_TO_KEY = {info['note']: key.lower() for key, info in GAME_NOTES.items()}

# 定义五声音阶的音程关系
PENTATONIC_INTERVALS = [
    0,  # 宫
    2,  # 商
    4,  # 角
    5,  # 清角
    7,  # 徵
    9,  # 羽
    11  # 变宫
]

# 定义每个八度的基准音符
OCTAVE_BASES = {
    'low': 48,    # 低音宫
    'middle': 60, # 中音宫
    'high': 72    # 高音宫
}

# 控制键映射
CONTROL_KEYS = {
    'START_PAUSE': '-',  # 播放/暂停
    'STOP': '=',        # 停止播放
    'PREV_SONG': 'up',  # 上一首
    'NEXT_SONG': 'down', # 下一首
    'FORCE_STOP': 'esc'  # 强制停止弹奏
} 

# 添加音符特性定义
NOTE_PROPERTIES = {
    # 宫调式音阶特性
    'GONG': {
        'primary': [0, 4, 7],     # 宫、角、徵（主要音）
        'secondary': [2, 9],      # 商、羽（次要音）
        'passing': [5, 11],       # 清角、变宫（经过音）
        'ornamental': [1, 3, 6, 8, 10]  # 装饰音
    },
    
    # 各音的情感特性权重
    'EMOTION': {
        0: 1.0,   # 宫：稳定
        2: 0.9,   # 商：坚定
        4: 0.95,  # 角：柔和
        5: 0.8,   # 清角：明亮
        7: 0.95,  # 徵：活跃
        9: 0.9,   # 羽：优美
        11: 0.8   # 变宫：变化
    }
}

# 36键模式的音符映射
GAME_NOTES_36KEY = {
    # 高音区
    'shift+Q': {'note': 84, 'name': '高音宫'},   # 高音宫
    'shift+W': {'note': 86, 'name': '高音商'},   # 高音商
    'shift+E': {'note': 88, 'name': '高音角'},   # 高音角
    'shift+R': {'note': 89, 'name': '高音清角'}, # 高音清角
    'shift+T': {'note': 91, 'name': '高音徵'},   # 高音徵
    'shift+Y': {'note': 93, 'name': '高音羽'},   # 高音羽
    'shift+U': {'note': 95, 'name': '高音变宫'}, # 高音变宫
    
    # 中高音区
    'Q': {'note': 72, 'name': '中高音宫'},
    'W': {'note': 74, 'name': '中高音商'},
    'E': {'note': 76, 'name': '中高音角'},
    'R': {'note': 77, 'name': '中高音清角'},
    'T': {'note': 79, 'name': '中高音徵'},
    'Y': {'note': 81, 'name': '中高音羽'},
    'U': {'note': 83, 'name': '中高音变宫'},
    
    # 中音区
    'A': {'note': 60, 'name': '中音宫'},
    'S': {'note': 62, 'name': '中音商'},
    'D': {'note': 64, 'name': '中音角'},
    'F': {'note': 65, 'name': '中音清角'},
    'G': {'note': 67, 'name': '中音徵'},
    'H': {'note': 69, 'name': '中音羽'},
    'J': {'note': 71, 'name': '中音变宫'},
    
    # 中低音区
    'Z': {'note': 48, 'name': '中低音宫'},
    'X': {'note': 50, 'name': '中低音商'},
    'C': {'note': 52, 'name': '中低音角'},
    'V': {'note': 53, 'name': '中低音清角'},
    'B': {'note': 55, 'name': '中低音徵'},
    'N': {'note': 57, 'name': '中低音羽'},
    'M': {'note': 59, 'name': '中低音变宫'},
    
    # 低音区
    'ctrl+Z': {'note': 36, 'name': '低音宫'},
    'ctrl+X': {'note': 38, 'name': '低音商'},
    'ctrl+C': {'note': 40, 'name': '低音角'},
    'ctrl+V': {'note': 41, 'name': '低音清角'},
    'ctrl+B': {'note': 43, 'name': '低音徵'},
    'ctrl+N': {'note': 45, 'name': '低音羽'},
    'ctrl+M': {'note': 47, 'name': '低音变宫'},
}

# 创建36键模式的反向映射
NOTE_TO_KEY_36KEY = {info['note']: key for key, info in GAME_NOTES_36KEY.items()}

# 36键模式的八度基准音
OCTAVE_BASES_36KEY = {
    'low': 36,     # 低音宫
    'mid_low': 48, # 中低音宫
    'middle': 60,  # 中音宫
    'mid_high': 72,# 中高音宫
    'high': 84     # 高音宫
}

# 定义两种模式的配置
PLAY_MODES = {
    '21key': {
        'name': '21键模式',
        'notes': GAME_NOTES,
        'note_to_key': NOTE_TO_KEY,
        'octave_bases': OCTAVE_BASES,
        'playable_min': 48,  # 低音宫
        'playable_max': 83   # 高音变宫
    },
    '36key': {
        'name': '36键模式',
        'notes': GAME_NOTES_36KEY,
        'note_to_key': NOTE_TO_KEY_36KEY,
        'octave_bases': OCTAVE_BASES_36KEY,
        'playable_min': 36,  # 低音宫
        'playable_max': 95   # 高音变宫
    }
}