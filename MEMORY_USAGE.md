# Memory System

3 lớp: Working (context tạm giữa agents), Short-term (workflow/execution log), Long-term (cache + chat history). Lưu ở PostgreSQL.

## Setup

1. Thêm vào `.env`:
```env
POSTGRES_DSN=postgresql://user:pass@host:5432/dbname
```
2. Khởi tạo schema: `python scripts/init_database.py`
3. Test: `python -m src.main --task "Hello" --session-id user123`

## Sử dụng

**Chat có context** — truyền `session_id`, agent tự load 5 tin nhắn gần nhất:
```python
agent.execute(task="How do I install it?", context={"session_id": "user123"})
```

**Multi-agent chia sẻ context** — dùng chung `workflow_id`:
```python
workflow_id = str(uuid.uuid4())
research_agent.execute(task="...", workflow_id=workflow_id)
data_agent.execute(task="...", workflow_id=workflow_id)  # tự có access research_result
```

**Cache** — tự động cache nếu confidence ≥ 0.7, cùng task description, chưa hết hạn (default 24h). Không cache hội thoại chat.

## Scripts quản lý

| Script | Chức năng |
|---|---|
| `scripts/view_memory_stats.py` | Xem thống kê cache, agent performance |
| `scripts/view_session.py <session_id>` | Xem lịch sử chat |
| `scripts/cleanup_memory.py` | Dọn dữ liệu cũ (chat, cache hết hạn, workflow xong) |

## Config (.env)

```env
CACHE_DEFAULT_TTL_HOURS=24
CHAT_HISTORY_MAX_MESSAGES=10
CHAT_HISTORY_RETENTION_DAYS=30
AUTO_CLEANUP_ENABLED=true
```

## Lưu ý khi dùng

- Luôn truyền `session_id` cho chat, nếu không sẽ mất context.
- `workflow_id` phải unique (dùng `uuid.uuid4()`), không hardcode.
- Nhớ `memory.clear_context(workflow_id)` sau khi workflow xong — tránh leak.
- TTL cache theo loại dữ liệu: tin tức 1h, docs 1 tuần, kiến thức chung 1 tháng.

## Troubleshooting

- **"Database not available"** → kiểm tra `POSTGRES_DSN` trong `.env`, test bằng `get_postgres_client().is_available()`.
- **"Table does not exist"** → chạy lại `python scripts/init_database.py`.
- **Cache không hoạt động** → check `result.get("cached")` để biết có phải cache hit không.
- **Working memory không share giữa agents** → đảm bảo cả 2 agent dùng đúng cùng `workflow_id`.

## API chính

```python
memory = get_memory_manager()

# Working Memory
memory.set_context(workflow_id, key, value)
memory.get_context(workflow_id, key)
memory.get_all_context(workflow_id)
memory.clear_context(workflow_id)

# Cache
memory.get_cached_result(agent_name, task, params, max_age_hours)
memory.save_cached_result(agent_name, task, result, confidence, params, ttl_hours)

# Chat History
memory.add_chat_message(ChatMessage(...))
memory.get_chat_history(session_id, limit)

# Management
memory.get_statistics()
memory.cleanup_old_data(retention_days)
```