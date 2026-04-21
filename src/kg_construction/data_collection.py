# 数据收集：原始数据加载与路径配置（实现版）
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import csv

from src.utils.config_loader import get_project_root


class DataCollector:
    """数据收集类：按配置加载医疗、保险等原始数据。

    说明：
    - 默认读取项目根目录下 `DataCleaned` 目录中的常见文件（Diseases/Drugs/Insurance/NursingHomes）。
    - 可通过 `config` 覆盖文件路径或设置 `base_path`。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        base = self.config.get("base_path")
        if base:
            self._base_path: Path = Path(base)
        else:
            self._base_path = Path(get_project_root())

    def set_base_path(self, base_path: str) -> None:
        """设置项目根路径，后续路径均相对此路径解析。"""
        self._base_path = Path(base_path)

    def _resolve_path(self, path_str: str) -> Path:
        """将配置中的相对路径解析为绝对路径。"""
        p = Path(path_str)
        if not p.is_absolute():
            p = self._base_path / p
        return p

    def get_medical_sources(self) -> List[str]:
        """返回医疗数据源路径列表（默认包含疾病与药品数据）。"""
        return self.config.get("medical", [
            "DataCleaned/Diseases/diseases.json",
            "DataCleaned/Drugs/medicine.json",
        ])

    def get_insurance_sources(self) -> List[str]:
        """返回保险类数据源路径列表（默认包含产品与养老院数据）。"""
        return self.config.get("insurance", [
            "DataCleaned/Insurance/insurance_info.json",
            "DataCleaned/NursingHomes/nursing_homes.csv",
        ])

    def _load_json(self, p: Path) -> Any:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_csv(self, p: Path) -> List[Dict[str, Any]]:
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [r for r in reader]

    def load_medical(self) -> Dict[str, Any]:
        """加载所有医疗相关原始数据（JSON/CSV），返回以文件名为键的数据字典。"""
        out: Dict[str, Any] = {}
        for path in self.get_medical_sources():
            p = self._resolve_path(path)
            if not p.exists():
                continue
            if p.suffix.lower() == ".json":
                try:
                    out[p.name] = self._load_json(p)
                except Exception:
                    out[p.name] = []
            elif p.suffix.lower() in (".csv", ".tsv"):
                out[p.name] = self._load_csv(p)
        return out

    def load_insurance(self) -> Dict[str, Any]:
        """加载保险/养老院类数据，返回以文件名为键的数据字典。"""
        out: Dict[str, Any] = {}
        for path in self.get_insurance_sources():
            p = self._resolve_path(path)
            if not p.exists():
                continue
            if p.suffix.lower() == ".json":
                try:
                    out[p.name] = self._load_json(p)
                except Exception:
                    out[p.name] = []
            elif p.suffix.lower() in (".csv", ".tsv"):
                out[p.name] = self._load_csv(p)
        return out

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """加载全部配置的数据源并返回结构化结果。"""
        return {
            "medical": self.load_medical(),
            "insurance": self.load_insurance(),
        }
