import yaml
import os
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv

def get_project_root() -> Path:
    """
    获取项目根目录路径。
    """
    current_path = Path(__file__).resolve()
    for parent in [current_path] + list(current_path.parents):
        if (parent / "config.yaml").exists():
            return parent
    return current_path.parent.parent.parent

def load_config() -> Dict[str, Any]:
    """
    加载 config.yaml 配置文件。
    """
    root = get_project_root()
    config_path = root / "config.yaml"
    if not config_path.exists():
        return {}
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# 全局配置对象
config = load_config()
load_dotenv(get_project_root() / ".env")
