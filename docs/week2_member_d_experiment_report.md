# 第2周实验报告（成员D：前端与测试负责人）

## 一、阶段工作小结

本阶段围绕“知识图谱模块完整复写（数据 -> 图）”的团队目标，成员D主要承担了导入模块测试与验收文档建设工作，核心目标是确保图谱导入结果“可验证、可复现、可交接”。

### 1. 本阶段工作内容

#### 1.1 导入模块测试设计与实现

为满足“至少包含连接测试、导入后计数校验”的要求，本阶段新增测试文件：

- `tests/test_kg_import.py`

测试覆盖点如下：

- **连接测试（Connection Test）**
  - 用例：`test_neo4j_connection_flow`
  - 目标：验证 `Neo4jLoader.connect()` 与 `Neo4jLoader.close()` 的关键流程。
  - 方法：通过 monkeypatch 替换 `GraphDatabase.driver`，使用 Fake Driver 模拟连接与关闭行为，避免依赖真实 Neo4j 环境。
  - 验收点：
    - driver 被正确注入到 loader；
    - `verify_connectivity()` 被调用；
    - `close()` 可正常关闭连接。

- **导入后计数校验（Post-import Count Validation）**
  - 用例：`test_import_progress_count_validation`
  - 目标：验证导入主流程 `load_all()` 对四类数据（疾病、药品、养老院、保险）的计数结果正确。
  - 方法：
    - 在 `tmp_path` 下动态生成最小样本数据集（`DataCleaned/*`）；
    - 使用 Fake Driver + Fake Session 执行批量导入逻辑；
    - 校验 `import_logs/*_progress.json` 中 `total/imported/failed_batches` 字段。
  - 验收点：
    - 四类导入都写出进度文件；
    - 每类 `imported == total`；
    - 无失败批次（`failed_batches == []`）。

#### 1.2 抽样验收表设计

新增文档：

- `docs/week2_member_d_acceptance.md`

文档提供了可直接执行的验收模板，包含：

- 执行信息记录（日期、命令、数据版本、实例地址）；
- 节点数抽样（Disease/Drug/NursingHome/Insurance 等）；
- 关系数抽样（HAS_SYMPTOM/TREATED_BY/TARGETS_POPULATION/COVERS_DISEASE）；
- 关键样例验收（疾病-症状、疾病-药品、保险-人群、保险-疾病）；
- 最终结论与问题记录。

该文档的作用是将“导入是否成功”从主观判断转化为结构化检查单，便于组内协作和周验收留痕。

#### 1.3 与团队目标的对应关系

本阶段成果与第2周成员D任务要求对应如下：

- “编写导入模块测试（连接测试、导入后计数校验）” -> 已通过 `tests/test_kg_import.py` 完成；
- “准备抽样验收表（节点数、关系数、关键样例）” -> 已通过 `docs/week2_member_d_acceptance.md` 完成。

---

### 2. 遇到的问题以及解决思路

#### 问题1：测试环境依赖不完整，导致 pytest 无法直接运行

- **现象**：执行 `pytest tests/test_kg_import.py -q` 时，因 `tests/conftest.py` 依赖 `fastapi`，在当前环境触发 `ModuleNotFoundError: No module named 'fastapi'`。
- **影响**：即使本次新增测试本身不依赖 FastAPI，也会因全局 conftest 导入链路中断而无法执行。
- **解决思路**：
  - 短期：先补齐基础依赖（`pip install -r requirements.txt`），保证测试框架能跑；
  - 中期：将导入模块测试进一步解耦为“纯单元测试目录”，避免被 API conftest 牵连；
  - 长期：在 CI 中区分 test scope（api / kg import / integration），提升稳定性与定位效率。

#### 问题2：仓库未内置真实 DataCleaned 数据，真实导入测试难以稳定复现

- **现象**：当前仓库中未检出 `DataCleaned` 文件，直接做真数据导入验证存在阻塞。
- **影响**：无法在任意开发机上立即复现“导入完成并计数验证”的过程。
- **解决思路**：
  - 使用临时样本数据自动构建最小可用数据集；
  - 用 Fake Driver 模拟 Neo4j 交互，先验证导入流程与计数逻辑；
  - 将真实数据库联调放入“可选集成测试”，由具备环境的同学执行。

#### 问题3：导入验证容易停留在“脚本执行成功”，缺少定量验收标准

- **现象**：仅凭“无报错”无法确认关系构建是否完整，难发现“部分导入”或“关系缺失”问题。
- **影响**：周验收时结果不可比对，返工成本高。
- **解决思路**：
  - 建立统一抽样验收表；
  - 将节点数、关系数、关键查询样例标准化；
  - 要求每次导入都记录验收结果，形成可追溯基线。

---

### 3. 下一阶段计划

结合项目第3周“RAG 检索与问答链路深化”的推进，成员D下一阶段计划如下：

#### 3.1 测试体系增强

- 将 `test_kg_import.py` 拆分为：
  - **离线单元测试**：完全 mock，确保本地和 CI 可稳定执行；
  - **联机集成测试**：连接真实 Neo4j，验证节点/关系真实落库效果。
- 增加异常路径测试：
  - 数据文件缺失；
  - 字段为空或格式异常；
  - 批次失败日志输出完整性。

#### 3.2 验收流程固化

- 在 `docs/week2_member_d_acceptance.md` 基础上扩展“验收执行说明”；
- 形成固定验收步骤（导入 -> 查询 -> 记录 -> 结论）；
- 争取与成员B、成员C共同确定“关键查询最小集”，提高跨模块一致性。

#### 3.3 前后端联调与演示准备

- 配合成员A/C，在前端或演示脚本中加入“导入状态与样例查询结果展示”；
- 将导入验收结果用于第3周 RAG 查询准确性对照（例如疾病-症状、保险-人群是否可检索）；
- 准备阶段汇报材料：测试结论、风险项、后续改进项。

---

## 二、阶段产出清单

- 测试代码：`tests/test_kg_import.py`
- 验收文档：`docs/week2_member_d_acceptance.md`
- 本实验报告：`docs/week2_member_d_experiment_report.md`

## 三、阶段结论

成员D在第2周已完成职责范围内的关键交付：导入模块测试与验收模板建设。当前成果可支持团队对知识图谱导入过程进行标准化验证，并为下一阶段 RAG 链路联调提供可量化的数据质量保障。
