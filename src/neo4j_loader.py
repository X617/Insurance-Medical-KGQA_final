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
    
    def create_indices(self):
        """创建索引以优化查询性能。"""
        indices = [
            # 常用查询字段索引
            "CREATE INDEX IF NOT EXISTS FOR (d:Disease) ON (d.icd_code)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Drug) ON (d.category_code)",
            "CREATE INDEX IF NOT EXISTS FOR (n:NursingHome) ON (n.city)",
            "CREATE INDEX IF NOT EXISTS FOR (i:Insurance) ON (i.category)",
            "CREATE INDEX IF NOT EXISTS FOR (i:Insurance) ON (i.age_limit)",
            # 关系查询加速
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_SYMPTOM]-() ON (r)",
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:TREATED_BY]-() ON (r)",
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:COVERS_DISEASE]-() ON (r)",
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:TARGETS_POPULATION]-() ON (r)",
        ]
        with self.driver.session(database=config.neo4j_db) as session:
            for q in indices:
                try:
                    session.run(q)
                    logger.info(f"Index created/verified: {q}")
                except Exception as e:
                    logger.warning(f"Failed to create index {q}: {e}")

    def load_all(self, clear_db: bool = True) -> None:
        """执行所有数据加载任务（疾病/药品/养老院/保险）。"""
        if clear_db:
            self.clear_database()
        self.create_constraints()
        self.create_indices()

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


    def get_graph_statistics(self) -> dict:
        """获取图谱统计信息，用于数据质量检查。"""
        stats = {}
        queries = {
            "disease_count": "MATCH (d:Disease) RETURN count(d) as count",
            "drug_count": "MATCH (d:Drug) RETURN count(d) as count",
            "symptom_count": "MATCH (s:Symptom) RETURN count(s) as count",
            "nursing_home_count": "MATCH (n:NursingHome) RETURN count(n) as count",
            "insurance_count": "MATCH (i:Insurance) RETURN count(i) as count",
            "has_symptom_rels": "MATCH ()-[r:HAS_SYMPTOM]->() RETURN count(r) as count",
            "treated_by_rels": "MATCH ()-[r:TREATED_BY]->() RETURN count(r) as count",
            "covers_disease_rels": "MATCH ()-[r:COVERS_DISEASE]->() RETURN count(r) as count",
        }
        
        with self.driver.session(database=config.neo4j_db) as session:
            for key, query in queries.items():
                try:
                    result = session.run(query).single()
                    stats[key] = result["count"] if result else 0
                except Exception as e:
                    logger.warning(f"Failed to get stat {key}: {e}")
                    stats[key] = -1
        
        logger.info(f"Graph statistics: {stats}")
        return stats

    def export_cypher_samples(self, output_path: Path = None) -> None:
        """导出常用 Cypher 查询样例库，按意图分类。"""
        if output_path is None:
            output_path = self._project_root / "cypher_query_samples.md"
        
        samples = """# 常用 Cypher 查询样例库

## 1. 疾病查询（Disease Queries）

### 1.1 获取疾病基本信息与症状
```cypher
MATCH (d:Disease {name: '高血压'})
OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom)
OPTIONAL MATCH (d)-[:TREATED_BY]->(drug:Drug)
RETURN d, collect(DISTINCT s.name) as symptoms, collect(DISTINCT drug.name) as drugs
```

### 1.2 获取疾病并发症
```cypher
MATCH (d:Disease {name: '高血压'})-[:HAS_COMPLICATION]->(complication:Disease)
RETURN d.name as disease, complication.name as complication_name
```

### 1.3 查询所有疾病及其症状数
```cypher
MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom)
RETURN d.name, count(s) as symptom_count
ORDER BY symptom_count DESC
LIMIT 20
```

### 1.4 按科室查询疾病
```cypher
MATCH (d:Disease)-[:BELONGS_TO_DEPT]->(dept:Department {name: '内科'})
RETURN d.name, d.intro
LIMIT 10
```

## 2. 保险查询（Insurance Queries）

### 2.1 查询覆盖特定疾病的保险
```cypher
MATCH (i:Insurance)-[:COVERS_DISEASE]->(d:Disease {name: '高血压'})
RETURN i.name, i.category, i.age_limit, i.price_desc
```

### 2.2 查询老年人保险
```cypher
MATCH (i:Insurance)-[:TARGETS_POPULATION]->(p:Population {name: '老年人'})
RETURN i.name, i.company, i.duration
LIMIT 10
```

### 2.3 按年龄范围查询保险
```cypher
MATCH (i:Insurance)
WHERE i.age_limit CONTAINS '60' OR i.age_limit CONTAINS '老年'
RETURN i.name, i.age_limit, i.category
LIMIT 20
```

### 2.4 查询特定险种的产品
```cypher
MATCH (i:Insurance {category: '健康保险'})
RETURN i.name, i.company, i.price_desc, i.description
```

## 3. 药品查询（Drug Queries）

### 3.1 治疗特定疾病的常用药物
```cypher
MATCH (d:Disease {name: '糖尿病'})-[:TREATED_BY]->(drug:Drug)
RETURN drug.name, drug.category_code, drug.dosage
```

### 3.2 查询所有药品
```cypher
MATCH (drug:Drug)
RETURN drug.name, drug.category_code
LIMIT 50
```

## 4. 养老院查询（Nursing Home Queries）

### 4.1 查询特定城市的养老院
```cypher
MATCH (n:NursingHome {city: '北京'})
RETURN n.name, n.nature, n.beds, n.price, n.services
```

### 4.2 查询所有养老院及其信息
```cypher
MATCH (n:NursingHome)
RETURN n.name, n.city, n.beds, n.price
ORDER BY n.city
LIMIT 30
```

## 5. 综合查询（Cross-domain Queries）

### 5.1 用户年龄和疾病的综合查询
```cypher
MATCH (d:Disease {name: '高血压'})
OPTIONAL MATCH (d)-[:TREATED_BY]->(drug:Drug)
OPTIONAL MATCH (i:Insurance)-[:COVERS_DISEASE]->(d)
OPTIONAL MATCH (i)-[:TARGETS_POPULATION]->(p:Population)
RETURN d.name as disease, collect(DISTINCT drug.name) as drugs, 
       collect(DISTINCT i.name) as insurance_products
```

### 5.2 症状反推疾病和保险
```cypher
MATCH (s:Symptom {name: '高血压'})<-[:HAS_SYMPTOM]-(d:Disease)
OPTIONAL MATCH (i:Insurance)-[:COVERS_DISEASE]->(d)
RETURN d.name as disease, collect(DISTINCT i.name) as insurance_products
LIMIT 10
```

### 5.3 老年人综合查询（疾病+养老+保险）
```cypher
MATCH (p:Population {name: '老年人'})<-[:TARGETS_POPULATION]-(i:Insurance)
OPTIONAL MATCH (n:NursingHome {city: '北京'})
RETURN 
  collect(DISTINCT i.name) as insurance_options,
  collect(DISTINCT n.name) as nursing_homes,
  count(DISTINCT i) as insurance_count
"""
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(samples)
            logger.info(f"Cypher query samples exported to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export Cypher samples: {e}")
