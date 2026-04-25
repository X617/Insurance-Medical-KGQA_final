# 知识图谱导入说明

本文档说明如何在本项目中运行知识图谱导入（Neo4j）。包括准备数据、配置、运行命令、以及常见问题处理。

## 目录结构（关键）
- `DataCleaned/`：清洗后的数据，应包含子目录 `Diseases/`、`Drugs/`、`NursingHomes/`、`Insurance/` 等。
- `src/neo4j_loader.py`：导入脚本（包含批量导入、进度与失败记录）。
- `import_logs/`：导入时会在项目根目录下生成此目录，包含每个 label 的进度文件和失败批次文件。

## 运行前准备

1. 确保 Neo4j 实例已启动并可访问。
2. 在项目根目录（与 `config.yaml` 同级）设置环境变量：

   - `NEO4J_URI`（例如：`bolt://localhost:7687`）
   - `NEO4J_USER`（默认 `neo4j`）
   - `NEO4J_PASSWORD`（Neo4j 密码）

   可以在系统环境变量中设置，或在运行前通过 PowerShell/CMD 导出。

3. 确认 `DataCleaned` 目录中存在以下文件：
   - `DataCleaned/Diseases/diseases.json`
   - `DataCleaned/Drugs/medicine.json`
   - `DataCleaned/NursingHomes/nursing_homes.csv`
   - `DataCleaned/Insurance/insurance_info.json`

## 运行导入

在项目根目录下运行：

```powershell
python -m src.neo4j_loader
```

脚本会：

- 连接 Neo4j（使用环境变量或 `config.yaml` 中的配置）。
- （可选）清空数据库并创建常用的唯一性约束。
- 执行疾病/药品/养老院/保险的数据批量导入。
- 在 `import_logs/` 中输出每个 label 的进度文件（`{label}_progress.json`）以及失败批次文件（`{label}_failed/failed_batch_*.json`）。

如果你只想验证连接与约束，可以临时执行脚本内的 `connect()` 与 `create_constraints()`。

## 日志与失败排查

- 导入过程中会在项目根目录下创建 `import_logs/`：
  - `{label}_progress.json`：包含 `total`、`imported`、`failed_batches` 等信息。
  - `{label}_failed/failed_batch_*.json`：保存失败的批次数据，便于重试或排查异常记录。

- 常见问题：
  - 连接失败：检查 `NEO4J_URI`、用户名/密码以及 Neo4j 是否允许 Bolt 连接。
  - 约束创建失败：可能是 Neo4j 版本差异或权限问题，查看日志中的完整异常。
  - 批量导入失败：查看对应的失败批次 JSON 文件，尝试在本地构造最小可复现样本并在 REPL 中执行相同的 Cypher。

## 可配置项

- `src/neo4j_loader.py` 中 `_batch_run` 的 `batch_size` 参数可调整以平衡内存与性能。
- `DataCollector`（`src/kg_construction/data_collection.py`）提供了读取数据的工具函数，可通过传入 `config` 覆盖默认文件路径。

## 下一步建议

- 在导入前对 `DataCleaned` 中的关键字段（`name`、`drug`、`symptom` 等）做抽样检查，保证字段格式一致。
- 若数据量很大，建议先在小样本上试跑，确认 Cypher 及关系模型无误。

如需我代为运行一次导入（房间内 Neo4j 可访问时），可以授权我执行或提供 Neo4j 连接信息（仅在你信任的环境中）。
