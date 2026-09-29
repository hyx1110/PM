# 公司内网邮件通知接入指南

## 功能和边界

系统保留站内通知，并可将同一条业务通知通过公司 SMTP 邮件服务器发送到用户档案中的邮箱。包括预约、项目与资源审批、任务变更、加班申请/审批/撤回等已接入站内通知的事件。邮件是提醒，不通过邮件直接完成审批；用户须登录系统操作。

本次仅交付代码、数据库迁移和文档，未连接公司邮件服务器、未发送邮件、未执行安装或测试。公司实际 SMTP 参数须由 IT 提供，不能根据邮箱域名自行猜测。

## 1. 向公司 IT 获取的信息

| 配置 | 需要确认的内容 |
|---|---|
| SMTP 地址、端口 | 部署服务器能够访问的内网地址，而不是网页版邮箱地址 |
| 加密模式 | STARTTLS、隐式 TLS，或公司批准的内网中继 |
| 发件身份 | 专用系统通知邮箱、允许使用的发件人地址 |
| 认证方式 | SMTP 用户名/专用密码，或基于服务器 IP 白名单的免认证中继 |
| 网络限制 | 防火墙端口、来源 IP 白名单、每日额度、发送频率和收件人范围 |
| 证书 | 使用公司私有 CA 时，提供可信根证书/中间证书 PEM 文件 |
| 系统访问地址 | 收件人能访问的系统前端地址，例如 `https://project.corp.example` |

当前实现支持 SMTP 用户名/密码与 IP 白名单中继，不包含 Exchange/Graph API、OAuth2 或 NTLM。如果公司只开放这些认证方式，应请 IT 提供受控 SMTP 中继，或另行扩展认证实现。不要关闭证书验证来绕过公司 CA 问题。

## 2. 先升级数据库

维护者先备份数据库，然后在 `backend` 目录自行执行：

```powershell
alembic upgrade head
```

新版本为 `20260928_0017`。它增加加班表、执行记录关联列和邮件投递状态列。应用代码依赖这些列，须先迁移，再重启新版 API/Worker/Beat。此次没有新增角色权限码，不需要为了本功能重新初始化角色。

历史通知统一标为 `skipped`，不会在启用邮件后把历史通知全部补发。

## 3. 配置环境文件

本地部署编辑 `backend/.env`；Docker Compose 编辑项目根目录 `.env`。API 和 Worker 必须使用一致的配置。仓库提供的是 `.env.example` 示例，不会自动覆盖真实环境文件。

### 方案 A：STARTTLS

以下域名和账号仅为占位示例，不可直接用于生产：

```dotenv
SMTP_ENABLED=true
SMTP_HOST=smtp.corp.example
SMTP_PORT=587
SMTP_FROM=project-notify@corp.example
SMTP_USERNAME=project-notify@corp.example
SMTP_PASSWORD=替换为IT提供的专用SMTP密码
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_CA_FILE=
SMTP_TIMEOUT_SECONDS=10
SMTP_MAX_ATTEMPTS=5
SMTP_SUBJECT_PREFIX="[项目协同] "
PUBLIC_APP_URL=https://project.corp.example
```

### 方案 B：隐式 TLS

在方案 A 基础上按 IT 要求调整：

```dotenv
SMTP_PORT=465
SMTP_USE_TLS=false
SMTP_USE_SSL=true
```

`SMTP_USE_TLS` 与 `SMTP_USE_SSL` 不能同时为 `true`。STARTTLS 和隐式 TLS 均验证服务器证书。

### 方案 C：公司内网 SMTP 中继

仅在 IT 明确批准免认证中继、配置来源 IP 白名单后使用；端口以 IT 指定为准：

```dotenv
SMTP_PORT=25
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=false
SMTP_USE_SSL=false
```

若中继支持 STARTTLS，应优先开启。未加密中继仅适用于经公司批准的受控网络，不能直接开放到公网。

### 私有 CA 和容器

设置 `SMTP_CA_FILE` 为 Worker 进程可读取的 PEM 文件路径。本地 Windows 可使用 `D:/certificates/corp-ca.pem`。容器内必须使用容器路径，例如 `/run/certs/corp-ca.pem`；请维护者将证书以只读卷挂载到 Worker：

```yaml
services:
  worker:
    volumes:
      - ./certificates/corp-ca.pem:/run/certs/corp-ca.pem:ro
```

将配置设为 `SMTP_CA_FILE=/run/certs/corp-ca.pem`。不要把私钥或 SMTP 密码提交到 Git；CA 文件只需包含公开的信任证书。配置修改后由维护者重新启动相关进程；本次交付未执行这些操作。

## 4. 后台投递如何运行

业务操作先在同一数据库事务中保存业务数据和站内通知，提交成功后才可能发送邮件。邮件发送不在 Web 请求中进行，因此邮箱服务器故障不会导致预约、审批或加班提交失败。

沿用现有 Redis、Celery Worker、Celery Beat。维护者在 `backend` 目录自行运行现有命令：

```powershell
celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
celery -A app.tasks.celery_app:celery_app beat --loglevel=INFO
```

Beat 每 5 分钟派发通知投递任务，Worker 执行发送。未启动 Worker/Beat 或 Redis 不可用时，站内通知和加班业务仍可使用，但邮件不会自动投递。不要为同一环境启动多个 Beat 调度实例。

单次扫描最多处理 100 条邮件。失败后按 5、10、20、40…分钟退避（最长间隔 60 分钟），最多尝试 `SMTP_MAX_ATTEMPTS` 次，默认 5 次。重试受 5 分钟调度粒度影响。并发 Worker 使用数据库行锁领取邮件。

SMTP 不提供严格的“恰好一次”事务：极端情况下，服务器已接收但 Worker 未记录成功即崩溃，重试可能重复投递。系统为同一通知使用固定 `Message-ID` 辅助追踪，但不承诺收件服务器必然去重。

## 5. 开关和状态

`SMTP_ENABLED=false` 为默认值。关闭后不发送邮件，新通知记录为 `disabled`；此前已经排队的 `pending` 邮件暂停，重新开启后继续发送。关闭期间的通知、历史通知和无邮箱时跳过的通知不会自动补发。开关是管理员环境配置，不恢复用户“通知偏好”功能。

| 数据状态 | 通知中心展示/含义 |
|---|---|
| `disabled` | 创建通知时未启用邮件 |
| `pending` | 等待发送或等待重试 |
| `sent` | SMTP 服务器已接收，不等于收件人已阅读或一定进入收件箱 |
| `failed` | 达到重试上限，请联系管理员处理 |
| `skipped` | 历史通知、无邮箱或收件人已停用，不发送 |

右上角通知中心可看到本人通知的邮件状态、尝试次数和脱敏错误类型。站内“标为已读”不会取消邮件；在发送前删除通知会阻止该通知后续投递，但不能召回已经被 SMTP 接收的邮件。

## 6. 维护者自行验收与排障

1. 配置真实收件人邮箱，优先使用专用测试账户。开启邮件前核对域名和收件范围。
2. 在系统触发一次真实站内业务通知，例如提交加班申请，确认审批人收到站内消息。
3. 由维护者等待一个调度周期，检查通知中心状态与 Worker 日志，核对邮箱收件箱/垃圾箱。
4. `SMTPAuthenticationError`：核对专用密码、发件授权和服务器认证方式。
5. `SSLCertVerificationError`：核对内网证书链、CA 文件和主机名，不要禁用证书验证。
6. 超时/连接失败：核对服务器出站端口、DNS、路由及 IT 白名单。
7. `SMTPSenderRefused` / `SMTPRecipientsRefused`：核对允许的发件人、收件人范围、邮箱地址或中继策略。
8. 长期 `pending`：检查开关、Worker、Beat、Redis，以及下一次重试时间。

达到重试上限后不会无限重试。修复配置后，如需补发特定失败通知，由 DBA **核对通知 ID、收件人和状态后**，仅对确认需要补发的记录执行：

```sql
-- 示例 ID 123 必须替换为已核对的具体通知 ID；这不会补发全部历史通知。
UPDATE notifications
SET email_status = 'pending', email_attempts = 0,
    email_last_error = NULL, email_next_attempt_at = NULL
WHERE id = 123 AND email_status = 'failed' AND is_deleted = 0;
```

本指南中的安装环境、迁移、进程启动、业务验证和 SQL 操作均由维护者自行执行，本次未执行。
