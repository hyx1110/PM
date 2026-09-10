# V1.0 前端

前端使用 Vue 3 Composition API、TypeScript、Vite、Vue Router、Pinia、Axios、Element Plus、Tailwind CSS 和 Day.js。

## 环境变量

复制 `.env.example` 为 `.env`：

```text
VITE_API_BASE_URL=/api/v1
VITE_APP_TITLE=项目任务与人力协同管理系统
```

## 维护者执行命令

```powershell
npm install
npm run dev
```

类型检查和生产构建：

```powershell
npm run type-check
npm run build
```

本次交付没有执行上述命令。

## 目录约定

- `src/api`：统一 Axios 客户端和领域 API。
- `src/types`：与后端请求、响应对应的 TypeScript 类型。
- `src/stores`：登录态、当前用户与权限判断。
- `src/router`：路由、登录守卫和页面权限。
- `src/components/schedule`：共享看板时间轴、人员行、预约和冲突组件。
- `src/views`：按业务领域划分页面。

401 响应会清理本地 Token 并跳转登录；其他普通接口错误统一提示；409 排期冲突由共享看板展示结构化冲突详情。

