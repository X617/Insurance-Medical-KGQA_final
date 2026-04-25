import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any

from neo4j import GraphDatabase
from src.config import config
from src.utils.config_loader import get_project_root

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Neo4jLoader:
    """增强型 Neo4j 导入器：支持批量导入、进度记录与失败记录。"""

    def __init__(self):
        self.uri = config.neo4j_uri
        self.user = config.neo4j_user
        self.password = config.neo4j_password
        self.driver = None
        self._project_root = Path(get_project_root())

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed.")

    def clear_database(self):
        """清空数据库中的所有节点和关系（慎用）。"""
        query = "MATCH (n) DETACH DELETE n"
        with self.driver.session(database=config.neo4j_db) as session:
            session.run(query)
        logger.warning("Database cleared.")

    def create_constraints(self):
        """创建节点唯一性约束，避免重复。"""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Disease) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Drug) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Symptom) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NursingHome) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Insurance) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Department) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Population) REQUIRE n.name IS UNIQUE",
        ]
        with self.driver.session(database=config.neo4j_db) as session:
            for q in constraints:
                try:
                    session.run(q)
                    logger.info(f"Constraint created/verified: {q}")
                except Exception as e:
                    logger.warning(f"Failed to create constraint {q}: {e}")

    def load_all(self, clear_db: bool = True) -> None:
        """执行所有数据加载任务（疾病/药品/养老院/保险）。"""
        if clear_db:
            self.clear_database()
        self.create_constraints()

        data_dir = self._project_root / "DataCleaned"
        if not data_dir.exists():
            logger.error(f"DataCleaned directory not found under project root: {self._project_root}")
            return

        self._load_diseases(data_dir / "Diseases" / "diseases.json")
        self._load_drugs(data_dir / "Drugs" / "medicine.json")
        self._load_nursing_homes(data_dir / "NursingHomes" / "nursing_homes.csv")
        self._load_insurances(data_dir / "Insurance" / "insurance_info.json")

    def _batch_run(self, query: str, data: List[Dict[str, Any]], label: str, batch_size: int = 1000) -> None:
        total = len(data)
        logger.info(f"Starting import for {label}. Total records: {total}")

        logs_dir = self._project_root / "import_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        progress_file = logs_dir / f"{label}_progress.json"
        failed_dir = logs_dir / f"{label}_failed"
        failed_dir.mkdir(parents=True, exist_ok=True)

        imported = 0
        failed_batches = []

        with self.driver.session(database=config.neo4j_db) as session:
            for i in range(0, total, batch_size):
                batch = data[i : i + batch_size]
                try:
                    session.run(query, batch=batch)
                    imported = min(i + batch_size, total)
                    logger.info(f"Imported {label}: {imported}/{total}")
                except Exception as e:
                    logger.error(f"Error importing batch {i//batch_size} for {label}: {e}")
                    # 保存失败批次以便后续检查
                    failed_path = failed_dir / f"failed_batch_{i//batch_size}.json"
                    try:
                        with open(failed_path, "w", encoding="utf-8") as ff:
                            json.dump(batch, ff, ensure_ascii=False, indent=2)
                        failed_batches.append(str(failed_path))
                    except Exception as ex:
                        logger.error(f"Failed to write failed batch file: {ex}")

        # 写入进度文件
        try:
            with open(progress_file, "w", encoding="utf-8") as pf:
                json.dump({"label": label, "total": total, "imported": imported, "failed_batches": failed_batches}, pf, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write progress file for {label}: {e}")

        logger.info(f"Finished importing {label}. Imported: {imported}, Failed batches: {len(failed_batches)}")

    def _load_diseases(self, file_path: Path) -> None:
        if not file_path.exists():
            logger.warning(f"Diseases file not found: {file_path}")
            return

        logger.info(f"Loading diseases from {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        processed = []
        for item in data:
            props = {
                "name": item.get("name"),
                "icd_code": item.get("icd_code"),
                "intro": item.get("intro"),
            }
            symptoms = item.get("symptom", []) or []
            drugs = item.get("drug", []) or []
            dept = item.get("cure_dept", "")

            processed.append({"props": props, "symptoms": symptoms, "drugs": drugs, "dept": dept, "neopathy": item.get("neopathy", []) or []})

        query = """
        UNWIND $batch AS row
        MERGE (d:Disease {name: row.props.name})
        SET d += row.props

        FOREACH (s_name IN row.symptoms |
            MERGE (s:Symptom {name: s_name})
            MERGE (d)-[:HAS_SYMPTOM]->(s)
        )

        FOREACH (ignore IN CASE WHEN row.dept <> '' THEN [1] ELSE [] END |
            MERGE (dept:Department {name: row.dept})
            MERGE (d)-[:BELONGS_TO_DEPT]->(dept)
        )

        FOREACH (d_name IN row.drugs |
            MERGE (dg:Drug {name: d_name})
            MERGE (d)-[:TREATED_BY]->(dg)
        )

        FOREACH (n_name IN row.neopathy |
            MERGE (nd:Disease {name: n_name})
            MERGE (d)-[:HAS_COMPLICATION]->(nd)
        )
        """

        self._batch_run(query, processed, "Diseases")

    def _load_drugs(self, file_path: Path) -> None:
        if not file_path.exists():
            logger.warning(f"Drugs file not found: {file_path}")
            return

        logger.info(f"Loading drugs from {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        processed = []
        # 兼容 medicine.json 的分类结构
        if isinstance(data, dict):
            for _, content in data.items():
                meds = content.get("medicines") if isinstance(content, dict) else []
                for med in meds or []:
                    props = {"name": med.get("name"), "category_code": med.get("category_code"), "dosage": med.get("dosage")}
                    processed.append(props)
        elif isinstance(data, list):
            for med in data:
                processed.append({"name": med.get("name")})

        query = """
        UNWIND $batch AS row
        MERGE (m:Drug {name: row.name})
        SET m += row
        """

        self._batch_run(query, processed, "Drugs")

    def _load_nursing_homes(self, file_path: Path) -> None:
        if not file_path.exists():
            logger.warning(f"Nursing homes file not found: {file_path}")
            return

        logger.info(f"Loading nursing homes from {file_path}...")
        processed = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("名称") or row.get("name")
                if not name or not name.strip():
                    continue
                props = {"name": name.strip(), "city": row.get("城市"), "nature": row.get("性质"), "beds": row.get("床位"), "address": row.get("地址"), "services": row.get("特色服务")}
                processed.append(props)

        query = """
        UNWIND $batch AS row
        MERGE (n:NursingHome {name: row.name})
        SET n += row
        """

        self._batch_run(query, processed, "NursingHomes")

    def _load_insurances(self, file_path: Path) -> None:
        if not file_path.exists():
            logger.warning(f"Insurance file not found: {file_path}")
            return

        logger.info(f"Loading insurances from {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        processed = []
        for item in data or []:
            props = {"name": item.get("产品名称") or item.get("name"), "category": item.get("险种分类"), "company": item.get("承保公司"), "age_limit": item.get("承保年龄"), "duration": item.get("保障期限"), "price_desc": item.get("价格"), "description": item.get("产品描述", "")}
            processed.append(props)

        query = """
        UNWIND $batch AS row
        MERGE (i:Insurance {name: row.name})
        SET i += row

        FOREACH (ignore IN CASE WHEN row.age_limit CONTAINS '老年' OR row.age_limit CONTAINS '60' THEN [1] ELSE [] END |
            MERGE (p:Population {name: '老年人'})
            MERGE (i)-[:TARGETS_POPULATION]->(p)
        )

        FOREACH (ignore IN CASE WHEN row.description CONTAINS '高血压' THEN [1] ELSE [] END |
            MERGE (d:Disease {name: '高血压'})
            MERGE (i)-[:COVERS_DISEASE]->(d)
        )

        FOREACH (ignore IN CASE WHEN row.description CONTAINS '糖尿病' THEN [1] ELSE [] END |
            MERGE (d:Disease {name: '糖尿病'})
            MERGE (i)-[:COVERS_DISEASE]->(d)
        )
        """

        self._batch_run(query, processed, "Insurances")


if __name__ == "__main__":
    loader = Neo4jLoader()
    try:
        loader.connect()
        loader.load_all(clear_db=True)
    finally:
        loader.close()