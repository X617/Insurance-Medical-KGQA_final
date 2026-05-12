# Insurance Medical KGQA

## Quick Start

```bash
cd insurance_medical_kgqa
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

## API

- `GET /health`
- `POST /chat`

接口详细说明见 `docs/api_contract.md`。

## 前端联调

```bash
# 可先设置后端地址（可选）
set INSURANCE_KGQA_API_BASE=http://127.0.0.1:8000
streamlit run frontend/streamlit_app.py
```

回归问答样例见 `tests/data/week3_regression_cases.json`，批跑脚本见 `scripts/regression_runner.py`，失败样例记录模板见 `docs/failed_samples_for_members.md`。
