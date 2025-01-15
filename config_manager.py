import os
import json
import logging

# 新建配置管理类
class ConfigManager:
    def __init__(self):
        self.config_file = "config.json"
        self.default_config = {
            'last_directory': '',
            'stay_on_top': False,
            'key_cooldown': 0.2,
            'window_check_interval': 0.2
        }
        
    def load(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return {**self.default_config, **json.load(f)}
            return self.default_config.copy()
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
            return self.default_config.copy() 