import os
import shutil
import re
import sys
import subprocess

def get_version():
    """从main.py中获取版本号"""
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"读取版本号时出错: {str(e)}")
    return "1.0.0"  # 默认版本号

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

def ensure_pyinstaller():
    """确保 PyInstaller 正确安装"""
    try:
        # 尝试导入 PyInstaller
        import PyInstaller
        return True
    except ImportError:
        print("正在重新安装 PyInstaller...")
        try:
            # 使用 subprocess 运行 pip 命令
            subprocess.check_call([sys.executable, '-m', 'pip', 'uninstall', 'pyinstaller', '-y'])
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
            return True
        except Exception as e:
            print(f"安装 PyInstaller 失败: {str(e)}")
            return False

def build_exe():
    """构建exe文件"""
    # 确保 PyInstaller 已正确安装
    if not ensure_pyinstaller():
        return False
        
    # 获取版本号和设置输出目录
    version = get_version()
    output_dir = "dist/yyslsAuto-play"
    exe_name = f"燕云自动演奏_v{version}"
    
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_dir, 'icon.ico')
    runtime_hook = os.path.join(current_dir, 'runtime_hook.py')
    
    # 确保runtime_hook.py存在
    if not os.path.exists(runtime_hook):
        print("错误: 未找到 runtime_hook.py")
        return False
    
    try:
        # 清理旧的构建文件
        clean_build()
        
        print(f"开始构建版本 {version}...")
        
        # 使用 subprocess 运行 PyInstaller
        cmd = [
            sys.executable,
            '-m',
            'PyInstaller',
            'main.py',
            f'--name={exe_name}',
            '--onefile',
            '--windowed',
            f'--icon={icon_path}',
            '--clean',
            f'--runtime-hook={runtime_hook}',
            '--add-data=icon.ico;.',
            '--uac-admin',
            '--hidden-import=win32gui',
            '--hidden-import=win32con',
            '--hidden-import=keyboard',
            '--hidden-import=mido',
            '--hidden-import=rtmidi',
            '--hidden-import=json',
            '--hidden-import=PyQt5',
            '--hidden-import=PyQt5.QtCore',
            '--hidden-import=PyQt5.QtGui',
            '--hidden-import=PyQt5.QtWidgets',
            '--hidden-import=pygame',
            '--hidden-import=pygame.mixer',
            '--hidden-import=pygame._sdl2',
            '--hidden-import=pygame._sdl2.audio',
            '--hidden-import=pygame.mixer_music',
            '--exclude-module=matplotlib',
            '--exclude-module=numpy',
            '--exclude-module=pandas',
            '--exclude-module=scipy',
            '--exclude-module=PIL',
            f'--distpath={output_dir}'
        ]
        
        subprocess.check_call(cmd)
        
        # 检查构建结果
        exe_path = os.path.join(output_dir, f"{exe_name}.exe")
        if os.path.exists(exe_path):
            # 复制必要文件到输出目录
            if os.path.exists('README.md'):
                shutil.copy2('README.md', output_dir)
            if os.path.exists('LICENSE'):
                shutil.copy2('LICENSE', output_dir)
                
            # 创建zip文件
            zip_name = f"yyslsAuto-play_{version}.zip"
            shutil.make_archive(
                os.path.join('dist', f"yyslsAuto-play_{version}"),
                'zip',
                output_dir
            )
            
            print("\n构建成功！")
            print(f"exe文件位置: {exe_path}")
            print(f"zip文件位置: dist/{zip_name}")
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
        print("1. exe文件在 dist/yyslsAuto-play 目录中")
        print("2. 请确保以管理员身份运行程序")
        print("3. 首次运行可能需要等待几秒钟")
    else:
        print("\n构建失败，请检查错误信息") 