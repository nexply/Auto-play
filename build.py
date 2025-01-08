import PyInstaller.__main__
import os

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 定义图标路径
icon_path = os.path.join(current_dir, 'icon.ico')

# PyInstaller参数
params = [
    'main.py',                            # 主程序文件
    '--name=燕云自动演奏',                 # 生成的exe名称
    '--onefile',                          # 打包成单个文件
    '--noconsole',                        # 不显示控制台窗口
    '--clean',                            # 清理临时文件
    f'--icon={icon_path}',                # 设置图标
    '--add-data=icon.ico;.',              # 添加图标文件
    '--hidden-import=keyboard',           # 添加隐式导入
    '--hidden-import=mido',
    '--hidden-import=rtmidi',
    '--hidden-import=json',
    '--hidden-import=PyQt5',
    '--hidden-import=win32gui',
    '--hidden-import=win32con',
    '--hidden-import=keyboard_mapping',
    '--hidden-import=midi_player',
]

# 执行打包
PyInstaller.__main__.run(params) 