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
