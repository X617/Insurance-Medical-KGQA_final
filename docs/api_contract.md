# API Contract (Week 1 Freeze)

## Base

- Local: `http://127.0.0.1:8000`
- Header: 可选 `x-trace-id`

## GET `/health`

### Response 200

```json
{
  "status": "ok",
  "neo4j_connected": false
}
```

## POST `/chat`

### Request Body

```json
{
  "query": "北京有哪些养老院？",
  "history": [
    {
      "role": "user",
      "content": "你好"
    },
    {
      "role": "assistant",
      "content": "你好，我可以帮你查询保险和医养信息。"
    }
  ]
}
```

### Response 200

```json
{
  "answer": "【Mock回答】已收到问题：北京有哪些养老院？",
  "context": "week1-mock-context",
  "intent": {
    "type": "unknown",
    "entities": [],
    "history_len": 2
  },
  "rewritten_query": "北京有哪些养老院？"
}
```

### Error Response (Unified)

```json
{
  "code": "HTTP_ERROR",
  "message": "query cannot be empty",
  "trace_id": "4f6de39f-9b5f-4ce7-bf6d-7400d2f95f6a"
}
```

## Error Codes

- `HTTP_ERROR`: 主动抛出的业务/参数错误
- `VALIDATION_ERROR`: 请求体结构校验失败
- `INTERNAL_ERROR`: 未处理异常

## Week 1 Signature Freeze

- `chat(query, history)` 签名冻结
- `/chat` 返回字段冻结：
  - `answer`
  - `context`
  - `intent`
  - `rewritten_query`
