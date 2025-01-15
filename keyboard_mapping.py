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