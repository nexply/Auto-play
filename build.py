import os
import sys
import shutil
from PyInstaller.__main__ import run

def clean_build():
    """清理构建文件夹"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"已删除 {dir_name} 目录")
    
    for pattern in files_to_clean:
        for file in os.listdir('.'):
            if file.endswith('.spec'):
                os.remove(file)
                print(f"已删除 {file}")

def build_exe():
    """构建exe文件"""
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 定义图标路径
    icon_path = os.path.join(current_dir, 'icon.ico')
    
    # 确保runtime_hook.py存在
    runtime_hook = os.path.join(current_dir, 'runtime_hook.py')
    if not os.path.exists(runtime_hook):
        print("错误: 未找到 runtime_hook.py")
        return False
    
    # PyInstaller 参数
    args = [
        'main.py',  # 主程序文件
        '--name=燕云自动演奏',  # 输出文件名
        '--onefile',  # 打包成单个文件
        '--windowed',  # 使用 GUI 模式
        f'--icon={icon_path}',  # 设置图标
        '--clean',  # 清理临时文件
        f'--runtime-hook={runtime_hook}',  # 运行时钩子
        '--add-data=icon.ico;.',  # 添加图标文件
        '--uac-admin',  # 请求管理员权限
        '--hidden-import=win32gui',  # 添加隐式导入
        '--hidden-import=win32con',
        '--hidden-import=keyboard',
        '--hidden-import=mido',
        '--hidden-import=rtmidi',
        '--hidden-import=json',
        '--hidden-import=PyQt5',
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        # 排除一些不需要的模块以减小文件大小
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=PIL',
    ]
    
    try:
        # 清理旧的构建文件
        clean_build()
        
        print("开始构建...")
        run(args)
        
        # 检查构建结果
        exe_path = os.path.join('dist', '燕云自动演奏.exe')
        if os.path.exists(exe_path):
            print(f"\n构建成功！exe文件位置: {exe_path}")
            return True
        else:
            print("\n构建失败：未找到输出文件")
            return False
            
    except Exception as e:
        print(f"\n构建过程中出错: {str(e)}")
        return False

if __name__ == '__main__':
    if build_exe():
        print("\n提示：")
        print("1. exe文件在 dist 目录中")
        print("2. 请确保以管理员身份运行程序")
        print("3. 首次运行可能需要等待几秒钟")
    else:
        print("\n构建失败，请检查错误信息") 