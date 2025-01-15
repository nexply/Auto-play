import os
import json
from typing import Dict, Optional

class PresetManager:
    """参数预设管理器"""
    def __init__(self, preset_dir: str = "presets"):
        self.preset_dir = preset_dir
        self._ensure_preset_dir()
        
    def _ensure_preset_dir(self):
        """确保预设目录存在"""
        if not os.path.exists(self.preset_dir):
            os.makedirs(self.preset_dir)
    
    def _get_preset_path(self, song_name: str, mode: str = '21key') -> str:
        """获取预设文件路径"""
        safe_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_'))
        return os.path.join(self.preset_dir, f"{safe_name}_{mode}.json")
    
    def save_preset(self, song_name: str, params: Dict, mode: str = '21key') -> bool:
        """保存预设"""
        try:
            preset_path = self._get_preset_path(song_name, mode)
            params['mode'] = mode  # 保存模式信息
            with open(preset_path, 'w', encoding='utf-8') as f:
                json.dump(params, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存预设时出错: {str(e)}")
            return False
    
    def load_preset(self, song_name: str) -> Optional[Dict]:
        """加载预设"""
        try:
            preset_path = self._get_preset_path(song_name)
            if os.path.exists(preset_path):
                with open(preset_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"加载预设时出错: {str(e)}")
            return None
    
    def delete_preset(self, song_name: str) -> bool:
        """删除预设"""
        try:
            preset_path = self._get_preset_path(song_name)
            if os.path.exists(preset_path):
                os.remove(preset_path)
            return True
        except Exception as e:
            print(f"删除预设时出错: {str(e)}")
            return False 
#触发更新