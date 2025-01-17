import os
import sys
import site
import subprocess
import winreg

def check_dll_registration():
    """检查 PyWin32 DLL 是否正确注册"""
    try:
        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Python\PythonCore", 0, winreg.KEY_READ)
        print("Python 注册表项存在")
    except WindowsError:
        print("警告: Python 注册表项不存在")

def find_post_install_script():
    """查找 post-install 脚本的位置"""
    possible_locations = [
        os.path.join(site.getsitepackages()[0], 'pywin32_system32', 'Scripts', 'pywin32_postinstall.py'),
        os.path.join(site.getsitepackages()[0], 'Scripts', 'pywin32_postinstall.py'),
        os.path.join(sys.prefix, 'Scripts', 'pywin32_postinstall.py')
    ]
    
    for loc in possible_locations:
        if os.path.exists(loc):
            print(f"找到 post-install 脚本: {loc}")
            return loc
            
    print("在以下位置未找到 post-install 脚本:")
    for loc in possible_locations:
        print(f"- {loc}")
    return None

def main():
    print(f"Python 路径: {sys.executable}")
    print(f"Site-packages 路径: {site.getsitepackages()[0]}")
    
    check_dll_registration()
    
    script_path = find_post_install_script()
    if not script_path:
        print("错误: 无法找到 pywin32_postinstall.py")
        return

    try:
        print("正在运行 post-install 脚本...")
        result = subprocess.run(
            [sys.executable, script_path, '-install'],
            capture_output=True,
            text=True
        )
        print("输出:", result.stdout)
        if result.stderr:
            print("错误:", result.stderr)
        
        if result.returncode == 0:
            print("PyWin32 修复完成")
        else:
            print(f"PyWin32 安装失败，返回码: {result.returncode}")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main() 