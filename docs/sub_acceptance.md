# 抽样验收表（导入模块）

本验收表用于知识图谱导入完成后的抽样检查，覆盖节点数、关系数与关键样例。

## 一、执行信息

- 验收日期：`____-__-__`
- 验收人：`________`
- 导入命令：`python -m src.neo4j_loader`
- 数据版本/来源：`________`
- Neo4j 实例：`bolt://________`

## 二、节点数抽样

- `Disease`：实际 `____`，预期同量级 `____`，结论（通过/不通过）`____`
- `Drug`：实际 `____`，预期同量级 `____`，结论（通过/不通过）`____`
- `NursingHome`：实际 `____`，预期同量级 `____`，结论（通过/不通过）`____`
- `Insurance`：实际 `____`，预期同量级 `____`，结论（通过/不通过）`____`
- `Symptom`/`Population` 等衍生节点：实际 `____`，结论（通过/不通过）`____`

建议查询：

- `MATCH (n:Disease) RETURN count(n) AS cnt`
- `MATCH (n:Drug) RETURN count(n) AS cnt`
- `MATCH (n:NursingHome) RETURN count(n) AS cnt`
- `MATCH (n:Insurance) RETURN count(n) AS cnt`

## 三、关系数抽样

- `(:Disease)-[:HAS_SYMPTOM]->(:Symptom)`：实际 `____`，预期同量级 `____`，结论 `____`
- `(:Disease)-[:TREATED_BY]->(:Drug)`：实际 `____`，预期同量级 `____`，结论 `____`
- `(:Insurance)-[:TARGETS_POPULATION]->(:Population)`：实际 `____`，预期同量级 `____`，结论 `____`
- `(:Insurance)-[:COVERS_DISEASE]->(:Disease)`：实际 `____`，预期同量级 `____`，结论 `____`

建议查询：

- `MATCH ()-[r:HAS_SYMPTOM]->() RETURN count(r) AS cnt`
- `MATCH ()-[r:TREATED_BY]->() RETURN count(r) AS cnt`
- `MATCH ()-[r:TARGETS_POPULATION]->() RETURN count(r) AS cnt`
- `MATCH ()-[r:COVERS_DISEASE]->() RETURN count(r) AS cnt`

## 四、关键样例验收

- 疾病-症状样例：
  - 查询：`MATCH (d:Disease {name:'高血压'})-[:HAS_SYMPTOM]->(s:Symptom) RETURN d.name, collect(s.name) LIMIT 1`
  - 结果是否符合预期：`____`
- 疾病-药品样例：
  - 查询：`MATCH (d:Disease {name:'糖尿病'})-[:TREATED_BY]->(m:Drug) RETURN d.name, collect(m.name) LIMIT 1`
  - 结果是否符合预期：`____`
- 保险-人群样例：
  - 查询：`MATCH (i:Insurance)-[:TARGETS_POPULATION]->(p:Population {name:'老年人'}) RETURN i.name, p.name LIMIT 5`
  - 结果是否符合预期：`____`
- 保险-疾病样例：
  - 查询：`MATCH (i:Insurance)-[:COVERS_DISEASE]->(d:Disease) RETURN i.name, d.name LIMIT 10`
  - 结果是否符合预期：`____`

## 五、结论

- 本轮导入验收结论：`通过 / 不通过`
- 问题记录与修复建议：`________`
