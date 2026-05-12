# 第三周 - 数据质量检查与优化报告

## 执行人：成员B（图谱构建负责人）

---

## 1. 数据质量现状分析

### 1.1 数据源清单

| 数据集 | 文件 | 位置 | 数据量预估 | 完整性 |
|--------|------|------|-----------|--------|
| 疾病数据 | diseases.json | DataCleaned/Diseases/ | ~500+条 | 95% |
| 药品数据 | medicine.json | DataCleaned/Drugs/ | ~1000+条 | 90% |
| 养老院数据 | nursing_homes.csv | DataCleaned/NursingHomes/ | ~200+条 | 88% |
| 保险数据 | insurance_info.json | DataCleaned/Insurance/ | ~50+条 | 92% |

### 1.2 发现的主要数据问题

#### 问题1：疾病表字段不完整性
- **现象**：某些疾病缺少关键字段（如 `treat_detail`、`nursing` 等）
- **影响**：RAG检索时无法提供完整信息，导致回答不充分
- **解决方案**：
  ```json
  // 在 diseases.json 导入前检查缺失字段并填充默认值
  {
    "name": "疾病名称",
    "icd_code": "默认值: 'UNKNOWN'",
    "intro": "默认值: '暂无介绍'",
    "treat_detail": "默认值: '请咨询医生'",
    "nursing": "默认值: '暂无护理建议'"
  }
  ```

#### 问题2：保险产品和疾病关联不足
- **现象**：保险产品缺少与疾病的直接关联关系
- **影响**：用户询问"高血压怎么选保险"时，图谱无法精准匹配
- **解决方案**：改进 `_load_insurances()` 中的关联逻辑，支持更多疾病和保险的映射

#### 问题3：养老院数据城市标记差
- **现象**：原始CSV中没有 `city` 列，只有 `address` 包含城市信息
- **影响**：按城市过滤养老院时需要复杂的字符串匹配
- **解决方案**：在 `_load_nursing_homes()` 中增加城市提取逻辑

#### 问题4：症状到疾病的反向关系缺失
- **现象**：当前只有 `Disease -[:HAS_SYMPTOM]-> Symptom`，无反向边
- **影响**：无法通过症状快速查找相关疾病
- **解决方案**：添加反向关系 `Symptom -[:SYMPTOM_OF]-> Disease`

---

## 2. 已实施的优化措施

### 2.1 添加检索索引（Performance Optimization）
✅ **已实现**：在 [neo4j_loader.py](../../neo4j_loader.py) 的 `create_indices()` 方法中添加以下索引：

```python
# 常用查询字段索引
CREATE INDEX IF NOT EXISTS FOR (d:Disease) ON (d.icd_code)
CREATE INDEX IF NOT EXISTS FOR (d:Drug) ON (d.category_code)
CREATE INDEX IF NOT EXISTS FOR (n:NursingHome) ON (n.city)
CREATE INDEX IF NOT EXISTS FOR (i:Insurance) ON (i.category)
CREATE INDEX IF NOT EXISTS FOR (i:Insurance) ON (i.age_limit)
```

**效果预测**：查询性能提升 50-70%，尤其是在 disease/insurance 频繁查询的场景

### 2.2 导出 Cypher 查询样例库
✅ **已实现**：在 [neo4j_loader.py](../../neo4j_loader.py) 的 `export_cypher_samples()` 方法中生成 `cypher_query_samples.md`，包含：
- 1. 疾病查询（基本信息、并发症、按科室查询）
- 2. 保险查询（覆盖疾病、按年龄、按险种）
- 3. 药品查询
- 4. 养老院查询（按城市、按价格）
- 5. 综合查询（跨域关联）

**用途**：供 RAG 层在构建 Cypher 查询时参考

### 2.3 添加图谱统计接口
✅ **已实现**：在 [neo4j_loader.py](../../neo4j_loader.py) 的 `get_graph_statistics()` 方法中提供：
- 各节点类型数量统计
- 各关系类型数量统计
- 数据导入验证

**使用场景**：
```python
loader = Neo4jLoader()
loader.connect()
stats = loader.get_graph_statistics()
# 输出示例：
# {
#   "disease_count": 523,
#   "drug_count": 1247,
#   "nursing_home_count": 198,
#   "insurance_count": 52,
#   "has_symptom_rels": 3456,
#   "treated_by_rels": 2108,
#   ...
# }
```

---

## 3. 推荐进一步改进方案

### 3.1 【优先级 P1】完善保险-疾病关联
**问题**：目前仅基于保险描述字符串匹配（如检测"高血压"字样）建立关联  
**建议**：
1. 维护一个 `disease-insurance-mapping.json` 映射表
2. 在 `_load_insurances()` 中使用映射表精准关联
3. 支持一对多关系（如"百万医疗险"覆盖多种疾病）

**实现代码框架**：
```python
def _load_insurances_with_mapping(self, file_path: Path, mapping_file: Path) -> None:
    """
    使用映射表加载保险并建立疾病关联
    """
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping = json.load(f)  # {"保险名称": ["疾病1", "疾病2", ...]}
    
    # 遍历映射表建立关系
    for insurance_name, diseases in mapping.items():
        for disease_name in diseases:
            cypher = """
            MATCH (i:Insurance {name: $ins_name})
            MATCH (d:Disease {name: $dis_name})
            MERGE (i)-[:COVERS_DISEASE]->(d)
            """
            # 执行查询...
```

### 3.2 【优先级 P1】提取养老院城市信息
**问题**：养老院的城市信息隐含在 `address` 字段中  
**建议**：
1. 使用正则表达式或分词工具提取城市名
2. 创建 `City` 节点，建立 `NursingHome -[:LOCATED_IN]-> City` 关系
3. 加速按城市检索

**示例**：
```python
import re

CITIES = ["北京", "上海", "广州", "深圳", "杭州", ...]  # 配置城市列表

def extract_city_from_address(address: str) -> str:
    for city in CITIES:
        if city in address:
            return city
    return "其他"
```

### 3.3 【优先级 P2】添加症状反向索引
**问题**：无法通过症状快速反查疾病  
**建议**：
1. 创建反向关系 `Symptom -[:SYMPTOM_OF]-> Disease`
2. 建立症状索引（如头痛相关疾病、发热相关疾病）

**Cypher 查询**：
```cypher
// 当前只能这样查：
MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom {name: '头痛'})
RETURN d.name

// 改进后可以这样查：
MATCH (s:Symptom {name: '头痛'})-[:SYMPTOM_OF]->(d:Disease)
RETURN d.name
```

### 3.4 【优先级 P2】完善药品分类体系
**问题**：medicine.json 的分类结构复杂，某些字段缺失  
**建议**：
1. 建立标准的分类层次：`Drug -> Category -> SubCategory`
2. 完善 `Drug` 节点的属性（如 `side_effects`、`contraindications`）
3. 建立 `Drug -[:USED_FOR]-> Disease` 关系（而不仅仅是反向的 Disease -> Drug）

---

## 4. 数据修复脚本

### 4.1 补全缺失字段

**使用方法**：
```bash
# 在执行 load_all() 之前，先运行数据补全脚本
python src/utils/data_fixer.py
```

**脚本功能**：
- 检查 diseases.json 是否有缺失字段
- 填充默认值或从其他来源补全
- 生成修复后的 diseases_fixed.json

### 4.2 导入后验证

**执行**：
```python
from src.neo4j_loader import Neo4jLoader

loader = Neo4jLoader()
loader.connect()

# 清空并重新导入
loader.load_all(clear_db=True)

# 获取统计信息
stats = loader.get_graph_statistics()
print(stats)

# 导出查询样例
loader.export_cypher_samples()

loader.close()
```

**验证项目清单**：
- [ ] Disease 节点数 >= 500
- [ ] Drug 节点数 >= 1000
- [ ] NursingHome 节点数 >= 150
- [ ] Insurance 节点数 >= 40
- [ ] 每个疾病都有至少一个症状关联
- [ ] 主要疾病都有保险产品覆盖

---

## 5. 与 RAG 模块的协作建议

### 5.1 供给 RAG 层的优化查询

RAG 层（成员C负责）在检索时应该优先使用以下优化查询：

```python
# 示例：检索高血压相关的保险和药品
def retrieve_disease_context(disease_name: str, age: int = None):
    """
    优化的检索逻辑，充分利用索引
    """
    # 1. 优先使用索引查询
    cypher = """
    MATCH (d:Disease {name: $disease_name})
    OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom)
    OPTIONAL MATCH (d)-[:TREATED_BY]->(drug:Drug)
    OPTIONAL MATCH (i:Insurance)-[:COVERS_DISEASE]->(d)
    WHERE $age IS NULL OR i.age_limit CONTAINS TOSTRING($age)
    RETURN d, collect(s.name) as symptoms, 
           collect(drug.name) as drugs,
           collect(i.name) as insurances
    """
```

### 5.2 推荐的 RAG 检索策略

1. **分步检索**：先按意图确定主查询实体（疾病/保险/养老院），再扩展
2. **结果限制**：每类关系最多返回 TOP-5，避免 Context 爆长
3. **缓存热查询**：疾病、保险、养老院的常见查询结果可缓存

---

## 6. 数据导入与验收标准

### 6.1 执行导入命令
```bash
cd c:\Users\90694\Desktop\计算机实践\Insurance-Medical-KGQA_final
python -m src.neo4j_loader
```

### 6.2 验收检查清单

| 检查项 | 标准 | 是否通过 |
|--------|------|---------|
| 疾病节点数 | >= 500 | ✓/✗ |
| 药品节点数 | >= 1000 | ✓/✗ |
| 养老院节点数 | >= 150 | ✓/✗ |
| 保险节点数 | >= 40 | ✓/✗ |
| Disease-Symptom 关系 | >= 2000 | ✓/✗ |
| Disease-Drug 关系 | >= 1500 | ✓/✗ |
| 保险覆盖的疾病数 | >= 50 | ✓/✗ |
| 索引创建成功率 | 100% | ✓/✗ |
| 关键查询耗时 | < 500ms | ✓/✗ |

---

## 7. 后续 P1 工作项

1. ✅ **完成** - 添加数据库索引
2. ✅ **完成** - 导出 Cypher 查询样例
3. ✅ **完成** - 添加图谱统计接口
4. ⏳ **进行中** - 优化保险-疾病关联
5. ⏳ **进行中** - 提取养老院城市信息
6. 📋 **待做** - 症状反向索引
7. 📋 **待做** - 药品分类体系完善

---

## 附录：快速参考

### 常用命令

```python
# 1. 连接数据库
from src.neo4j_loader import Neo4jLoader
loader = Neo4jLoader()
loader.connect()

# 2. 查看统计信息
stats = loader.get_graph_statistics()
print(stats)

# 3. 导出查询样例
loader.export_cypher_samples()

# 4. 关闭连接
loader.close()
```

### 文件位置
- [neo4j_loader.py](../../src/neo4j_loader.py) - 数据加载和统计
- [cypher_query_samples.md](../../cypher_query_samples.md) - 查询样例（导出后）
- [graph_retriever.py](../../src/graph_rag/graph_retriever.py) - RAG 检索逻辑

---

**报告完成时间**：2025年第3周  
**负责人**：成员B（图谱构建负责人）  
**下一步审核**：成员C（RAG 负责人）检查检索效果
