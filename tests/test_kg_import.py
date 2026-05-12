import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.neo4j_loader import Neo4jLoader


class _FakeSession:
    def __init__(self, run_records: List[Dict[str, Any]]):
        self._run_records = run_records

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query: str, **kwargs: Any) -> None:
        self._run_records.append({"query": query, "kwargs": kwargs})


class _FakeDriver:
    def __init__(self):
        self.connected = False
        self.closed = False
        self.run_records: List[Dict[str, Any]] = []

    def verify_connectivity(self) -> None:
        self.connected = True

    def session(self, database: str = "neo4j") -> _FakeSession:  # noqa: ARG002
        return _FakeSession(self.run_records)

    def close(self) -> None:
        self.closed = True


def _write_sample_dataset(project_root: Path) -> None:
    diseases_dir = project_root / "DataCleaned" / "Diseases"
    drugs_dir = project_root / "DataCleaned" / "Drugs"
    nursing_dir = project_root / "DataCleaned" / "NursingHomes"
    insurance_dir = project_root / "DataCleaned" / "Insurance"
    diseases_dir.mkdir(parents=True, exist_ok=True)
    drugs_dir.mkdir(parents=True, exist_ok=True)
    nursing_dir.mkdir(parents=True, exist_ok=True)
    insurance_dir.mkdir(parents=True, exist_ok=True)

    diseases = [
        {
            "name": "高血压",
            "icd_code": "I10",
            "intro": "血压持续升高",
            "symptom": ["头痛", "眩晕"],
            "drug": ["氨氯地平"],
            "cure_dept": "心内科",
            "neopathy": ["冠心病"],
        },
        {
            "name": "糖尿病",
            "icd_code": "E14",
            "intro": "血糖代谢异常",
            "symptom": ["多饮", "多尿"],
            "drug": ["二甲双胍"],
            "cure_dept": "内分泌科",
            "neopathy": [],
        },
    ]
    with open(diseases_dir / "diseases.json", "w", encoding="utf-8") as f:
        json.dump(diseases, f, ensure_ascii=False, indent=2)

    medicines = {
        "慢病": {
            "medicines": [
                {"name": "氨氯地平", "category_code": "A01", "dosage": "5mg"},
                {"name": "二甲双胍", "category_code": "A02", "dosage": "500mg"},
            ]
        }
    }
    with open(drugs_dir / "medicine.json", "w", encoding="utf-8") as f:
        json.dump(medicines, f, ensure_ascii=False, indent=2)

    with open(nursing_dir / "nursing_homes.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["名称", "城市", "性质", "床位", "地址", "特色服务"])
        writer.writeheader()
        writer.writerow(
            {"名称": "康宁养老院", "城市": "上海", "性质": "民营", "床位": "120", "地址": "浦东新区", "特色服务": "慢病管理"}
        )
        writer.writerow(
            {"名称": "安康护理中心", "城市": "北京", "性质": "公办", "床位": "80", "地址": "朝阳区", "特色服务": "术后康复"}
        )

    insurances = [
        {
            "产品名称": "银发守护2026",
            "险种分类": "医疗险",
            "承保公司": "示例保险A",
            "承保年龄": "60-80岁",
            "保障期限": "1年",
            "价格": "2000元/年",
            "产品描述": "覆盖高血压与糖尿病并提供门诊管理",
        },
        {
            "产品名称": "长护无忧",
            "险种分类": "护理险",
            "承保公司": "示例保险B",
            "承保年龄": "55-75岁",
            "保障期限": "终身",
            "价格": "按年龄核保",
            "产品描述": "面向老年慢病人群",
        },
    ]
    with open(insurance_dir / "insurance_info.json", "w", encoding="utf-8") as f:
        json.dump(insurances, f, ensure_ascii=False, indent=2)


def _read_progress(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_neo4j_connection_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_driver = _FakeDriver()

    def _fake_driver_factory(uri: str, auth: Any) -> _FakeDriver:  # noqa: ARG001
        return fake_driver

    monkeypatch.setattr("src.neo4j_loader.GraphDatabase.driver", _fake_driver_factory)

    loader = Neo4jLoader()
    loader.connect()

    assert loader.driver is fake_driver
    assert fake_driver.connected is True

    loader.close()
    assert fake_driver.closed is True


def test_import_progress_count_validation(tmp_path: Path) -> None:
    _write_sample_dataset(tmp_path)
    fake_driver = _FakeDriver()

    loader = Neo4jLoader()
    loader.driver = fake_driver
    loader._project_root = tmp_path

    loader.load_all(clear_db=True)

    progress_dir = tmp_path / "import_logs"
    diseases = _read_progress(progress_dir / "Diseases_progress.json")
    drugs = _read_progress(progress_dir / "Drugs_progress.json")
    nursing = _read_progress(progress_dir / "NursingHomes_progress.json")
    insurances = _read_progress(progress_dir / "Insurances_progress.json")

    assert diseases["total"] == 2
    assert diseases["imported"] == 2
    assert diseases["failed_batches"] == []

    assert drugs["total"] == 2
    assert drugs["imported"] == 2
    assert drugs["failed_batches"] == []

    assert nursing["total"] == 2
    assert nursing["imported"] == 2
    assert nursing["failed_batches"] == []

    assert insurances["total"] == 2
    assert insurances["imported"] == 2
    assert insurances["failed_batches"] == []
