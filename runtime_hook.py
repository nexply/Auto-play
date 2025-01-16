import os
import sys

def setup_environment():
    # 确保临时文件目录存在
    temp_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', '燕云自动演奏')
    os.makedirs(temp_dir, exist_ok=True)
    
    # 设置工作目录
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))

setup_environment() 