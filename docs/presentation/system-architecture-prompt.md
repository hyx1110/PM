# 系统架构图生成说明

用途：PPT 展示；16:9 横版。

最终图片：`system-architecture-v2.png`（实际输出 1672 × 941 px，白底 PNG）。PPT 中建议按原始比例插入，避免拉伸。生成工具的实际输出尺寸以文件为准。

核对依据：frontend/package.json、backend/requirements.txt、docker-compose.yml、backend/app/api/v1/router.py、backend/app/tasks/celery_app.py、README.md。

生成方式：内置 image_gen 工具。只展示当前已实现能力；邮件标注为可选，Redis 表示 Celery 消息代理及结果存储。

修订记录：清除右上功能区域重复叠影，整理为两列四行；保留原有技术栈、功能文案及业务流程。最终图片已人工查看。

## 完整生成提示词

```text
Use case: infographic-diagram.
Asset type: one polished Chinese system architecture infographic for a PowerPoint presentation.
Create a HIGH RESOLUTION 16:9 landscape image, preferably 3840×2160. This is a finished presentation slide, not a photo of a slide. Make every Chinese character and technology name crisp and accurate. White background, restrained dark navy and muted teal palette with pale blue panels, flat editorial vector-like rendering, fine connectors, generous consistent margins, meticulous typography, no 3D, no gradients, no watermark. Use a modern Chinese sans-serif, large readable labels. No fake logos.

MAIN TITLE at top-left: "项目任务与人力协同管理系统"
Subtitle: "系统架构与核心功能"
Top-right small tag: "V2.0"
Below the title, two clearly organized columns: left about 58% width "01  技术架构", right about 39% width "02  核心功能". Equal-height well-aligned panels. Leave enough whitespace between them. Bottom a slim full-width business workflow ribbon.

LEFT COLUMN — show a genuine logical architecture, TOP TO BOTTOM:
1. Slim user roles strip headed "用户角色". Five equally spaced labeled chips:
"超级管理员", "部门主管", "职能主管", "项目经理", "项目成员".
Downward connector to frontend.
2. Frontend card headed "Web 前端". Strong main label "Vue 3 · TypeScript · Vite".
Secondary line "Element Plus · Pinia · Vue Router · Axios".
Small browser-outline icon.
Downward arrow to gateway.
3. Narrow gateway bar "Nginx" and "静态资源托管 · /api 反向代理".
Downward arrow labeled "REST API / JSON".
4. Strong central backend card with navy header "Python · FastAPI".
Main content label "接口层 → 业务服务层 → 数据访问层".
Small capability chips "Pydantic 数据校验" and "JWT 认证 · RBAC 权限".
Secondary small label "Gunicorn + Uvicorn".
This is a layered backend application, NOT independent microservices.
5. BELOW backend show TWO BRANCHES, clearly connected:
LEFT DATA BRANCH: backend arrow to small label "SQLAlchemy 2 · Alembic", then database-cylinder-style card "MySQL 8.4" with subtitle "业务数据持久化".
RIGHT ASYNC BRANCH: card headed "后台任务". Inside a clean three-node directed chain exactly "Celery Beat → Redis 7.4 → Celery Worker". It is the timer to broker to worker sequence. Under Redis label "任务队列 / 结果存储", NOT cache. Beneath the chain a readable line "状态同步 · 风险扫描 · 临期提醒 · 通知投递". A thin connector from Celery Worker to MySQL shows database access; avoid crossing other boxes and text. A small dotted outgoing arrow from Worker to "SMTP 邮件（可选）".
Below both branches, a slim neutral platform strip: "Docker Compose 容器化部署".
Arrange the lower data and task cards so text fits at presentation size. Redis and Celery labels MUST not be squeezed or abbreviated incorrectly. Do not invent an API-to-Redis task publishing flow. The scheduled work is triggered by Beat.

RIGHT COLUMN — a clean 2 columns × 4 rows grid of eight concise feature cards. Each gets one simple thin-line icon, a prominent dark title and TWO smaller lines, exactly:
CARD 1:
"管理驾驶舱"
"项目甘特 · 待办汇总"
"计划与实际对比"
CARD 2:
"项目管理"
"立项审批 · 成员维护"
"项目资源申请"
CARD 3:
"任务管理"
"多级任务 · 多人协作"
"工时约束 · 状态联动"
CARD 4:
"任务共享看板"
"人力预约 · 个人日程"
"确认撤回 · 拖动改期"
CARD 5:
"任务执行"
"执行记录 · 实际工时"
"任务状态同步"
CARD 6:
"项目过程报表"
"计划与实际对比"
"项目完成后评价"
CARD 7:
"组织与权限"
"用户 · 部门 · 组织树"
"五类角色 · 数据范围"
CARD 8:
"通知与数据"
"站内通知 · Excel 导入导出"
"操作日志"
Right feature cards are capability groupings, not microservices. No connector arrows between these eight cards.

BOTTOM WORKFLOW RIBBON spans width beneath both columns:
Label "业务闭环", then a restrained left-to-right five-step flow:
"项目审批" → "任务拆分" → "人力预约与确认" → "执行填报" → "项目完成与评价".

ACCURACY CONSTRAINTS: This diagram reflects existing code. Do not show HRDB integration, AI scheduling, AI predictions, overtime application, WebSocket, Kafka, Kubernetes, ECharts, business analytics, notification preferences, mobile app, or unimplemented monitoring/caching features. SMTP is optional and configured externally. Do not add certification claims, benchmarks, availability percentages, company brands, or fictional data. No extra copy beyond specified titles and necessary connectors. Prioritize readable Chinese typography and technical correctness over decorative elements. All content contained inside safe slide margins.
```
