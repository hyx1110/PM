# V2.0 前端

前端使用 Vue 3 Composition API、TypeScript、Vite、Vue Router、Pinia、Axios、Element Plus、Tailwind CSS 和 Day.js。V2.0 不新增图表依赖，驾驶舱和分析页使用原生 CSS 图形，避免扩大前端依赖面。

## V2 页面

- `views/dashboard`：管理驾驶舱。
- `views/schedule`：日/周/月共享看板、拖动、批量排期、复制上周。
- `views/workload`：人员负载与项目占比。
- `views/risk`：风险筛选、扫描和处理。
- `views/notification`：站内通知与多渠道偏好。
- `views/data-exchange`：Excel 模板、导入任务、错误明细和报表导出。
- `views/analytics`：经营分析报表。

## 维护者执行

```powershell
npm install
npm run dev
```

维护者自行检查和构建：

```powershell
npm run type-check
npm run build
```

本次 V2.0 文件交付没有运行上述命令。

## 交互约定

- 共享看板拖动排期时提交当前 `version`；服务端发现并发变更返回 `40903`，前端提示刷新。
- 排期冲突沿用 `40901` 和结构化 `conflicts`，批量排期保持原子冲突检查，复制周排期则跳过冲突项并返回明细。
- 文件下载使用 Blob；上传只接受 `.xlsx`。
- 通知角标在主框架加载时读取未读数，完整阅读和偏好设置在通知中心完成。
