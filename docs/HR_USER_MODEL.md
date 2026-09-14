# 正式人员数据与系统用户映射

## 目的

本项目在 MySQL 中先建立可测试的正式人员数据架构，不连接正式库，也不导入真实数据。正式人员属性、人事管理职级和系统权限角色分开保存，避免把组织职级直接当成系统权限。

## 核心字段映射

| 正式数据含义 | 当前系统字段 | 规则 |
|---|---|---|
| 员工内部标识 | `users.id` | 保留 MySQL 自增数字主键，所有业务外键继续引用它 |
| 员工号 | `users.employee_no` | 唯一，同时作为登录账号；只允许英文、数字和英文符号 |
| 兼容登录名 | `users.username` | 系统自动写入，与 `employee_no` 强制相等，不再单独维护 |
| 部门 | `users.department_id` | 直接关联 `departments.id` |
| 组织 | `users.organization_id` | 直接关联 `organizations.id`，并校验属于所选部门 |
| 直属上级 | `users.supervisor_id` | 自关联 `users.id`，不能指向本人 |
| 岗位 | `employee_profiles.position_id` | 一名员工最多一个岗位编号，非空值全局唯一 |
| 人员属性 | `employee_profiles.*` | 保存姓名拆分、常用姓名、员工类型、职务、学历、地点、成本中心等 |
| 人事管理职级 | `employee_profiles.hr_management_level` | 与系统角色分离，只负责触发规则化自动授权 |

`employee_profiles.user_id` 唯一，因此一个系统用户只会有一条正式人员档案。

## 两套概念

### 人事管理职级

人事职级来自正式人员架构，当前允许三种测试值：

- `employee`：普通员工，不自动授予管理角色；
- `department_manager`：Department Manager 人事职级；
- `management_manager`：Management Manager 人事职级。

它们保存在 `employee_profiles`，不是权限判断的直接依据。

这里的 `hr_management_level` 是当前 MySQL 测试架构中的归一化结果，不要求正式库存在同名字段。后续接入正式数据时，应根据组织层级数据中 `department_manager`、`management_manager` 所指向的员工号找到对应 `users.employee_no`，再写入归一化职级并触发系统角色同步；本版本不实现这段正式库连接和导入逻辑。

### 系统功能角色

以下五类角色继续保存在 `roles`，功能和权限全部保留：

- `super_admin`：超级管理员；
- `department_manager`：系统 L3；
- `functional_manager`：系统 L4；
- `project_manager`：项目经理；
- `project_member`：项目成员。

鉴权仍读取系统角色和权限，不直接读取人事职级。

## 自动映射

| 人事管理职级 | 自动授予的系统角色 | 页面显示 |
|---|---|---|
| `employee` | 无 | 普通员工 |
| `department_manager` | `department_manager` | L3 |
| `management_manager` | `functional_manager` | L4 |

`user_roles.is_manual` 表示人工分配，`user_roles.is_hr_auto` 表示来自上述映射。同一关联的两个标记可以同时为 `true`：

- 人工分配项目经理、项目成员、超级管理员或 L3/L4，不受人事职级修改影响；
- 修改人事职级时，只增加或撤销对应的自动来源；
- 自动来源撤销后，如果人工来源仍存在，系统角色继续有效；
- 两个来源都不存在时，才删除该用户角色关联。

## 当前实施边界

- 数据库只使用 MySQL 8 和 Alembic 迁移 `20260914_0006`。
- 当前部门、组织、直属上级字段沿用现有外键，不新增第二套重复关系。
- 本版本没有离职同步逻辑。
- 本版本没有正式库连接器、定时同步任务或真实数据导入脚本。
- 用户 Excel 模板可用于人工创建测试数据，使用员工号关联直属上级、项目经理和任务负责人。
