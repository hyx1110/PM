# V1.0 后端

FastAPI 后端按照 `Router → Service → Repository → Model` 分层。Router 只负责 HTTP 参数与依赖注入，Service 管理业务规则和事务，Repository 封装查询，Pydantic Schema 与 SQLAlchemy Model 分离。

## 配置

复制 `.env.example` 为 `.env`，重点配置：

- `DATABASE_URL`：MySQL SQLAlchemy 连接字符串。
- `SECRET_KEY`：JWT 签名密钥。
- `ACCESS_TOKEN_EXPIRE_MINUTES`：访问令牌有效期。
- `CORS_ORIGINS`：逗号分隔的前端来源。
- `STANDARD_WORK_HOURS`：每日标准可用工时。
- `INITIAL_ADMIN_*`：首次初始化管理员信息。

## 维护者执行命令

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m scripts.init_data
uvicorn app.main:app --reload
```

生产环境建议从 `backend` 目录运行：

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --workers 2
```

## 数据库迁移

首版迁移位于 `alembic/versions/20260909_0001_initial_schema.py`。后续修改模型后创建新的 revision：

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

不要重写已经进入共享环境的迁移文件。

## 测试

测试文件已经归档在 `tests/`，本次交付未执行。维护者可在配置好独立测试数据库后运行 `pytest`。排期冲突公式的边界样例位于 `tests/test_schedule_overlap_rules.py`。

