import os
import yaml
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class Config:
    def __init__(self, config_file="config.yaml"):
        self.config_data = self._load_yaml(config_file)

    def _load_yaml(self, file_path):
        if not os.path.exists(file_path):
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def neo4j_uri(self):
        return os.getenv("NEO4J_URI", "bolt://localhost:7687")

    @property
    def neo4j_user(self):
        return os.getenv("NEO4J_USER", "neo4j")

    @property
    def neo4j_password(self):
        return os.getenv("NEO4J_PASSWORD", "password")

    @property
    def neo4j_db(self):
        return self.config_data.get("neo4j", {}).get("database", "neo4j")

config = Config()