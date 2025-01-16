# 燕云自动演奏工具

这是一个用于自动演奏MIDI文件的工具，专门为《燕云十六声》游戏设计。

## 功能特点

- 支持 36 键模式
- 支持 MIDI 文件播放
- 自动音高调整
- 多音轨支持
- 窗口焦点检测
- 播放控制（播放/暂停/停止）
- 文件夹批量加载
- 搜索功能
- 窗口置顶选项

## 系统要求

- Windows 10 或更高版本
- 管理员权限（用于键盘控制）

## 使用方法

1. **下载和运行**
   - 从 [Releases](../../releases) 页面下载最新版本的`燕云自动演奏.exe`
   - 将exe文件放在单独的文件夹中
   - 右键点击exe文件，选择"以管理员身份运行"

2. **基本操作**
   - 选择MIDI文件夹：点击"选择MIDI文件夹"按钮
   - 选择音轨：在右侧列表中选择要播放的音轨
   - 播放控制：使用界面按钮或快捷键控制播放

3. **快捷键**
   - Alt + 减号键(-) - 播放/暂停
   - Alt + 等号键(=) - 停止播放
   - Alt + 方向键上 - 上一首
   - Alt + 方向键下 - 下一首

## 开发者信息

### 环境配置

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/Auto-play.git
cd Auto-play
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 修复 PyWin32（如果需要）：
```bash
python fix_pywin32.py
```

### 运行程序

有两种方式运行程序：

1. 直接运行（开发模式）：
```bash
# 以管理员权限运行 PowerShell 或命令提示符
python main.py
```

2. 打包后运行：
```bash
# 先打包
python build.py
# 运行生成的 exe 文件（需要管理员权限）
./dist/燕云自动演奏.exe
```

### 项目结构

- `main.py` - 主程序入口
- `midi_player.py` - MIDI播放核心逻辑
- `keyboard_mapping.py` - 键盘映射配置
- `build.py` - 打包脚本
- `requirements.txt` - 项目依赖
- `icon.ico` - 程序图标

## ⚠️ 注意事项

### 管理员权限
- 程序需要管理员权限才能正常触发键盘事件
- 请务必以管理员身份运行程序

### 配置文件
- 程序会自动创建 `config.json` 保存配置
- 配置文件包含最后访问的目录和窗口置顶状态

### 游戏设置
- 确保游戏窗口标题为"燕云十六声"
- 建议在游戏中设置合适的按键映射

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## 📝 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI框架
- [mido](https://mido.readthedocs.io/) - MIDI文件处理
- [keyboard](https://github.com/boppreh/keyboard) - 键盘控制 