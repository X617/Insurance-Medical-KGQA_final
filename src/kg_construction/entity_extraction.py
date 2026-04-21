# 实体抽取：规则/占位实现（用于第二周导入阶段）
from typing import List, Dict, Any, Tuple, Optional
import json
import csv
from pathlib import Path

from src.utils.config_loader import get_project_root


# 三元组：(头实体, 关系, 尾实体) 或 (头实体名, 关系类型, 尾实体名)
Triple = Tuple[str, str, str]


class EntityExtractor:
    """实体与关系抽取器（规则占位实现）。

    特性：
    - 支持从项目 DataCleaned 中自动加载简单词表（疾病/药品/养老院/保险）。
    - 基于子串匹配抽取实体（轻量、可替换为 NER 模型）。
    - 支持从结构化记录生成简单三元组（例如 name -> TREATED_BY -> drug）。
    """

    def __init__(self, model_name: Optional[str] = None, vocab: Optional[Dict[str, List[str]]] = None, **kwargs: Any):
        self.model_name = model_name
        self._model = None
        self.vocab: Dict[str, List[str]] = vocab or {}
        if not self.vocab:
            self._load_default_vocab()

    def _load_default_vocab(self) -> None:
        root = Path(get_project_root())
        # Diseases
        try:
            df = root / "DataCleaned" / "Diseases" / "diseases.json"
            if df.exists():
                with open(df, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.vocab.setdefault("Disease", [])
                for item in data:
                    name = item.get("name")
                    if name and name not in self.vocab["Disease"]:
                        self.vocab["Disease"].append(name)
        except Exception:
            pass

        # Drugs
        try:
            mf = root / "DataCleaned" / "Drugs" / "medicine.json"
            if mf.exists():
                with open(mf, "r", encoding="utf-8") as f:
                    mdata = json.load(f)
                self.vocab.setdefault("Drug", [])
                if isinstance(mdata, dict):
                    for cat, content in mdata.items():
                        meds = content.get("medicines") if isinstance(content, dict) else []
                        for med in meds or []:
                            mname = med.get("name")
                            if mname and mname not in self.vocab["Drug"]:
                                self.vocab["Drug"].append(mname)
        except Exception:
            pass

        # Nursing homes
        try:
            nh = root / "DataCleaned" / "NursingHomes" / "nursing_homes.csv"
            if nh.exists():
                with open(nh, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    self.vocab.setdefault("NursingHome", [])
                    for row in reader:
                        name = row.get("名称") or row.get("name")
                        if name and name not in self.vocab["NursingHome"]:
                            self.vocab["NursingHome"].append(name)
        except Exception:
            pass

        # Insurance products
        try:
            insf = root / "DataCleaned" / "Insurance" / "insurance_info.json"
            if insf.exists():
                with open(insf, "r", encoding="utf-8") as f:
                    ins = json.load(f)
                self.vocab.setdefault("Insurance", [])
                for it in ins or []:
                    n = it.get("产品名称") or it.get("name")
                    if n and n not in self.vocab["Insurance"]:
                        self.vocab["Insurance"].append(n)
        except Exception:
            pass

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """基于词表的子串匹配抽取实体，返回包含 `type,name,start,end` 的字典列表。"""
        out: List[Dict[str, Any]] = []
        if not text:
            return out
        for etype, names in self.vocab.items():
            for name in names:
                try:
                    idx = text.find(name)
                except Exception:
                    idx = -1
                if idx != -1:
                    out.append({"type": etype, "name": name, "start": idx, "end": idx + len(name)})
        return out

    def extract_entities_batch(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        return [self.extract_entities(t) for t in texts]

    def extract_triples_from_text(self, text: str) -> List[Triple]:
        """简单启发式：如果文本同时包含疾病与药品名，则产生 `(disease, TREATED_BY, drug)` 三元组。"""
        triples: List[Triple] = []
        diseases = self.vocab.get("Disease", [])
        drugs = self.vocab.get("Drug", [])
        for d in diseases:
            if d in text:
                for dg in drugs:
                    if dg in text:
                        triples.append((d, "TREATED_BY", dg))
        return triples

    def extract_triples_from_records(
        self, records: List[Dict[str, Any]], schema: Optional[Dict[str, List[Tuple[str, str, str]]]] = None
    ) -> List[Triple]:
        """从结构化记录生成三元组：根据常见字段（drug/symptom）产出 `TREATED_BY` / `HAS_SYMPTOM` 等三元组。

        如果传入 `schema`，优先按 schema 生成（schema 格式为字段名->(head_type, rel, tail_type)）。
        """
        triples: List[Triple] = []
        for rec in records or []:
            # 名称字段优先识别
            name = rec.get("name") or rec.get("疾病") or rec.get("产品名称") or rec.get("名称")
            if not name:
                continue

            # 按 schema 生成（如果有）
            if schema:
                for field, rules in schema.items():
                    val = rec.get(field)
                    if not val:
                        continue
                    values = val if isinstance(val, list) else [s.strip() for s in str(val).split(",") if s.strip()]
                    for v in values:
                        for head_type, rel, tail_type in rules:
                            triples.append((name, rel, v))
                continue

            # 常见逻辑：drug(s) -> TREATED_BY
            for k in ("drug", "drugs", "药品"):
                if k in rec and rec[k]:
                    vals = rec[k] if isinstance(rec[k], list) else [s.strip() for s in str(rec[k]).split(",") if s.strip()]
                    for v in vals:
                        triples.append((name, "TREATED_BY", v))

            # symptom(s) -> HAS_SYMPTOM
            for k in ("symptom", "symptoms", "症状"):
                if k in rec and rec[k]:
                    vals = rec[k] if isinstance(rec[k], list) else [s.strip() for s in str(rec[k]).split(",") if s.strip()]
                    for v in vals:
                        triples.append((name, "HAS_SYMPTOM", v))

            # 简单基于描述的保险覆盖关系示例
            desc = rec.get("description") or rec.get("产品描述") or rec.get("简介")
            if desc and "高血压" in desc:
                triples.append((name, "COVERS_DISEASE", "高血压"))

        return triples
