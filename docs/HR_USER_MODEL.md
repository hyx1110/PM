# 简化用户模型

## 当前口径

当前版本只使用 MySQL。用户模型不再承载人员档案、岗位、人事职级或 HR 角色映射，员工号就是唯一登录账号。

## 用户字段

| 含义 | 数据库字段 | 规则 |
|---|---|---|
| 内部主键 | `users.id` | 自增数字主键，所有业务外键继续引用它 |
| 员工号/登录账号 | `users.employee_no` | 唯一；只允许英文字母、数字和英文符号 |
| 姓名 | `users.name` | 必填，语言不限 |
| 邮箱 | `users.email` | 可空，非空时唯一 |
| 部门 | `users.department_id` | 可空，关联 `departments.id` |
| 组织 | `users.organization_id` | 可空，关联 `organizations.id`，非空时须属于所选部门 |
| 直属主管 | `users.supervisor_id` | 可空，自关联 `users.id`，不能指向本人 |
| 系统角色 | `user_roles` | 用户与 `roles` 的多对多直接关联 |

以下字段属于系统运行所需，不作为人员业务资料展示：`password_hash`、`status`、`is_deleted`、`created_at`、`updated_at`。

当前用户表不再包含：

- `username` 兼容登录字段；
- 手机号；
- 岗位编号、员工类型、姓名拆分、职务、学历、地点、成本中心等人员档案；
- 人事职级；
- HRDB 人员来源和同步时间。

## 系统角色

系统固定保留五类角色：

| 角色代码 | 页面名称 |
|---|---|
| `super_admin` | 超级管理员 |
| `department_manager` | L3 |
| `functional_manager` | L4 |
| `project_manager` | 项目经理 |
| `project_member` | 项目成员 |

系统角色由项目管理系统直接分配。`user_roles` 不再包含 `is_manual`、`is_hr_auto`，也不再根据人事职级自动授予 L3/L4。用户没有选择任何角色时，系统自动授予 `project_member`。

## 登录与删除

- 登录接口只接收 `employee_no` 和密码。
- 员工号创建后不可在用户页面修改，软删除后也继续保留，避免历史身份被新账号复用。
- 用户删除采用软删除；存在活动项目、任务、排期或项目成员关系时必须先完成移交。
- 当前账号不能删除自己，最后一个有效超级管理员不能删除。

## 数据库迁移

`20260916_0009_simplify_user_schema.py` 在历史迁移基础上执行以下收敛：

- 删除 `users.username`、`users.phone`；
- 删除 `employee_profiles`；
- 删除 `user_roles.is_manual`、`user_roles.is_hr_auto`；
- 保留现有用户数字主键、员工号、组织关系、直属主管和五类系统角色关联。

升级会永久移除旧人员档案数据，维护者执行迁移前应自行备份数据库。
