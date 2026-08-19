# Silly Teamwork

Silly Teamwork 是一个面向大学课程小组协作的任务管理系统。系统以 Team（小组）、
Project（前端产品文案为“科目”）和 Task（任务）组织课程协作内容，支持：

- 小组管理
- 科目（Project）管理
- 任务管理
- 文件中心
- 基于系统角色和协作关系的权限控制
- 用户资料管理

当前项目已经包含可运行的 FastAPI 后端、React 前端、数据库迁移、自动化测试和 Docker
Compose 部署环境。

## V1.1 新增功能

### 文件中心

V1.1 建立了统一、展开式的文件索引体验，包含：

- 全局文件池：集中查看当前用户有权限访问的文件
- 科目文件池：聚合科目共享文件及其任务附件
- 任务附件索引：在任务详情中查看和搜索附件
- 按文件名搜索
- 按上传时间倒序展示
- 由后端统一计算的文件查看、上传、修改和删除权限
- 文件删除时的数据库事务、物理文件清理与失败恢复

文件系统继续复用统一的 `File` 模型，通过 `project_id` 表示科目共享文件，通过
`task_id` 表示任务附件；没有新增独立的文件索引表。

### 资源生命周期管理

V1.1 增加了任务、科目和小组的永久删除能力：

- 删除任务
- 删除科目
- 删除小组

Team leader 可以删除所属小组及其科目、任务，super_admin 可以执行全局资源删除；
Project owner 还可以删除所属科目中的任务。普通成员和 Task owner 不会因此获得额外的
永久删除权限。删除流程包含数据库事务、关联数据级联、物理文件清理以及失败恢复，避免
数据库记录与本地文件系统不一致。科目的归档能力继续保留，与永久删除互不替代。

### 用户功能

- 用户可以维护昵称、头像和个人简介（bio）
- 支持头像上传、读取和删除
- 支持验证原密码后修改密码

### UI/UX

- 文件中心采用 Collapse、List、Card 等展开式组件，减少多层页面跳转
- 支持手机浏览器使用的 Drawer 导航和响应式布局
- 使用 Ant Design 响应式组件，保持桌面端与移动端一致的业务体验

## 技术架构

### Backend

- Python 3.12+
- FastAPI + RESTful API
- PostgreSQL + SQLAlchemy 2.x Async ORM + asyncpg
- Alembic 数据库迁移
- JWT（PyJWT）+ Argon2 密码哈希（pwdlib）
- Pydantic Settings 环境配置
- pytest、Ruff、mypy、pre-commit

### Frontend

- React
- TypeScript
- Vite
- Ant Design
- TanStack Query
- Zustand
- openapi-fetch 与 FastAPI OpenAPI 类型

### Deployment

- Docker / Docker Compose
- Ubuntu Server

## 项目结构

```text
.
├── migrations/                    # Alembic 数据库迁移环境
│   ├── versions/                  # 自动生成的版本迁移脚本
│   ├── env.py                     # 连接异步数据库并加载 ORM metadata
│   └── script.py.mako             # 新迁移文件模板
├── src/silly_teamwork/            # 应用源码（src layout）
│   ├── api/
│   │   ├── dependencies.py        # FastAPI 通用依赖，如请求级 DB Session
│   │   ├── router.py              # API 总路由
│   │   └── v1/
│   │       ├── endpoints/         # 按 REST 资源拆分的路由模块
│   │       └── router.py          # v1 路由聚合与 URL 前缀
│   ├── core/
│   │   ├── config.py              # 类型安全的环境变量配置
│   │   └── security.py            # 密码哈希与 JWT 基础工具
│   ├── db/
│   │   ├── base.py                # ORM Base、命名规范及通用 mixin
│   │   └── session.py             # AsyncEngine 与请求级 AsyncSession
│   ├── models/                    # SQLAlchemy 实体模型
│   ├── repositories/              # 查询及持久化逻辑，不放业务规则
│   ├── schemas/                   # Pydantic 请求/响应 DTO
│   ├── services/                  # 用例、权限规则和事务编排
│   ├── utils/                     # 无业务状态的通用小工具
│   └── main.py                    # 应用工厂、中间件、生命周期和入口
├── tests/                         # 与源码结构对应的自动化测试
├── frontend/                      # React + TypeScript + Vite 前端
│   ├── src/api/                   # openapi-fetch 客户端与生成类型
│   ├── src/features/              # 按业务域组织的 API、hooks 与组件
│   ├── src/pages/                 # 页面组件
│   └── src/layouts/               # 桌面端与移动端公共布局
├── .env.example                   # 可提交的环境变量示例（不含真实密钥）
├── .pre-commit-config.yaml        # 提交前自动检查
├── alembic.ini                    # Alembic 主配置
├── docker-compose.yml             # 本地 API + PostgreSQL 环境
├── Dockerfile                     # API 生产风格镜像
├── Makefile                       # 常用开发命令快捷入口
└── pyproject.toml                 # 依赖、打包及工具统一配置
```

## 文件职责说明

| 文件或目录 | 作用 |
| --- | --- |
| `src/silly_teamwork/__init__.py` | 声明 Python 包和当前应用版本。 |
| `src/silly_teamwork/main.py` | 创建 FastAPI 实例，注册 CORS、总路由与应用生命周期。 |
| `src/silly_teamwork/api/__init__.py` | 声明 API 层 Python 包。 |
| `src/silly_teamwork/api/dependencies.py` | 定义可复用的 FastAPI 依赖类型，目前提供请求级数据库会话。 |
| `src/silly_teamwork/api/router.py` | 聚合各 API 版本，供应用入口一次性挂载。 |
| `src/silly_teamwork/api/v1/__init__.py` | 声明 v1 API 包。 |
| `src/silly_teamwork/api/v1/router.py` | 统一注册 v1 资源路由、URL 前缀及 OpenAPI 标签。 |
| `src/silly_teamwork/api/v1/endpoints/__init__.py` | 声明 v1 路由模块包。 |
| `src/silly_teamwork/api/v1/endpoints/health.py` | 提供无需数据库的存活检查。 |
| `src/silly_teamwork/api/v1/endpoints/auth.py` | 邀请码注册和 JWT 登录接口。 |
| `src/silly_teamwork/api/v1/endpoints/users.py` | 当前用户查询、资料更新、密码修改和头像管理接口。 |
| `src/silly_teamwork/api/v1/endpoints/teams.py` | 小组、小组成员、邀请和小组删除接口。 |
| `src/silly_teamwork/api/v1/endpoints/projects.py` | 科目、科目成员、科目文件索引和科目删除接口。 |
| `src/silly_teamwork/api/v1/endpoints/tasks.py` | 任务、任务成员、截止查询和任务删除接口。 |
| `src/silly_teamwork/api/v1/endpoints/files.py` | 文件上传、索引、元数据、下载和删除接口。 |
| `src/silly_teamwork/core/__init__.py` | 声明跨领域基础设施包。 |
| `src/silly_teamwork/core/config.py` | 从环境变量和 `.env` 加载、校验并缓存配置。 |
| `src/silly_teamwork/core/security.py` | 提供 Argon2 密码哈希和 JWT 签发/解析基础函数。 |
| `src/silly_teamwork/db/__init__.py` | 声明数据库基础设施包。 |
| `src/silly_teamwork/db/base.py` | 定义 Declarative Base、约束命名规范、UUID 主键和时间戳 mixin。 |
| `src/silly_teamwork/db/session.py` | 创建异步引擎、会话工厂以及每请求独立的会话依赖。 |
| `src/silly_teamwork/models/__init__.py` | ORM 模型统一导入点，让 Alembic 能发现全部表。 |
| `src/silly_teamwork/repositories/__init__.py` | 数据访问层入口，后续按聚合封装 SQLAlchemy 查询。 |
| `src/silly_teamwork/repositories/users.py` | 用户的按 ID、用户名、邮箱查询和新增操作。 |
| `src/silly_teamwork/repositories/invitation_codes.py` | 使用行锁读取待兑换的邀请码。 |
| `src/silly_teamwork/repositories/team_members.py` | 新增小组成员关系。 |
| `src/silly_teamwork/schemas/__init__.py` | Pydantic DTO 包入口。 |
| `src/silly_teamwork/schemas/common.py` | 定义通用消息响应与泛型分页响应。 |
| `src/silly_teamwork/schemas/auth.py` | 注册、登录请求与 JWT 响应模型。 |
| `src/silly_teamwork/schemas/user.py` | 安全的用户公开响应模型，不暴露密码哈希。 |
| `src/silly_teamwork/services/__init__.py` | 业务服务层入口，承载用例、授权规则和事务边界。 |
| `src/silly_teamwork/services/auth.py` | 注册事务、邀请码兑换、密码校验和 JWT 签发。 |
| `src/silly_teamwork/services/exceptions.py` | 可预期的认证业务异常。 |
| `src/silly_teamwork/utils/__init__.py` | 通用、无状态辅助函数包入口。 |
| `migrations/env.py` | 用异步引擎运行 Alembic，并加载配置与 ORM metadata。 |
| `migrations/script.py.mako` | Alembic 生成新 revision 时使用的 Python 模板。 |
| `migrations/versions/` | 存放有顺序、可审计的数据库版本迁移。 |
| `migrations/README` | 标识迁移目录用途。 |
| `tests/conftest.py` | pytest 公共 fixture，目前提供 FastAPI 测试客户端。 |
| `tests/test_health.py` | 验证应用装配和 v1 健康检查路由。 |
| `tests/__init__.py` | 声明测试包。 |
| `.env.example` | 本地环境变量模板，不包含真实 Secret。 |
| `.gitignore` | 排除 Secret、虚拟环境、缓存、上传文件和构建产物。 |
| `.editorconfig` | 统一编辑器的缩进、编码和换行规则。 |
| `.pre-commit-config.yaml` | 在提交前自动执行 Ruff 检查与格式化。 |
| `pyproject.toml` | 集中管理项目元数据、运行/开发依赖及工具规则。 |
| `alembic.ini` | 指定迁移目录和 Alembic 日志行为；数据库地址由应用配置注入。 |
| `Dockerfile` | 构建非 root 用户运行的 API 镜像。 |
| `docker-compose.yml` | 编排本地 API、PostgreSQL、健康检查和数据卷。 |
| `Makefile` | 封装安装、启动、测试、格式化和迁移等常用命令。 |
| `README.md` | 项目架构、启动方式、配置和开发约定（本文件）。 |

### 分层职责

请求从 `api/endpoints` 进入，路由只负责 HTTP 参数、状态码和响应；`services` 负责业务
流程与授权；`repositories` 封装 SQLAlchemy 查询；`models` 表达数据库结构；`schemas`
定义对外数据契约。这样可以避免把所有逻辑堆进路由或 ORM 模型，也便于单元测试。

当前已实现的实体如下：

- `User`
- `Team`、`TeamMember`（含 role）
- `Project`、`ProjectMember`
- `Task`、`TaskMember`
- `File`
- `InvitationCode`
- `SystemAdmin`
- `Notification`

## 本地启动

### 方式一：本机 Python + Docker PostgreSQL

```bash
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
make install
docker compose up -d db
alembic upgrade head
make dev
```

打开：

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- 健康检查: <http://127.0.0.1:8000/api/v1/health>

### 方式二：全部使用 Docker Compose

```bash
docker compose up --build
```

Compose 会等待 PostgreSQL 健康、执行已有迁移，然后启动 API。

本地 Compose 的 `api` 服务使用 Dockerfile 的 `development` target，包含测试和静态
检查依赖。可以直接在容器中运行：

```bash
docker compose exec api pytest
docker compose exec api ruff check .
docker compose exec api mypy src
```

Dockerfile 的默认最终 target 仍为 `production`，只安装运行时依赖；生产构建也可以显式
执行 `docker build --target production .`。

## 开发环境初始化

迁移数据库后执行幂等 seed：

```bash
make seed
# 等价命令：python -m silly_teamwork.cli.seed
```

默认创建：

- 管理员用户名：`admin`
- 管理员密码：`admin123456`
- 昵称：`Administrator`
- 默认团队：`Silly Teamwork Development Team`
- 测试邀请码：`ST-DEV-2026`

管理员是默认团队的 `owner`（对应产品语义中的 leader），没有使用 `User.is_superuser`
获得永久平台管理员权限。数据库只保存邀请码的 SHA-256 摘要，seed 运行时会把明文邀请码
输出到终端。重复运行不会重复创建记录，也不会重置已存在管理员的密码。

这些默认值可通过 `.env` 中的 `SEED_ADMIN_USERNAME`、`SEED_ADMIN_PASSWORD`、
`SEED_ADMIN_NICKNAME`、`SEED_TEAM_NAME`、`SEED_INVITE_CODE` 覆盖。为避免弱默认密码
进入真实环境，seed 仅在 `ENVIRONMENT=development` 时允许运行。

Docker Compose 环境可执行：

```bash
docker compose exec api python -m silly_teamwork.cli.seed
```

## 常用命令

```bash
make test                  # 运行测试
make lint                  # Ruff + mypy
make format                # 自动修复并格式化
make migration m="init"   # 根据 ORM 模型生成迁移
make upgrade               # 升级到最新数据库版本
make downgrade             # 回退一个数据库版本
```

启用 Git 提交前检查：

```bash
pre-commit install
```

## 配置说明

应用配置全部来自环境变量，开发时由根目录 `.env` 自动加载。`.env` 已被 Git 忽略；
只提交 `.env.example`。部署前至少要替换 `SECRET_KEY`、数据库密码、CORS 来源，并通过
平台的 Secret 管理功能注入。生产环境设置 `ENVIRONMENT=production` 后，交互式 API
文档默认关闭。

## 用户认证 API

### 邀请码注册

`POST /api/v1/auth/register`

```json
{
  "username": "alice_chen",
  "password": "a-strong-password",
  "nickname": "Alice",
  "email": "alice@example.edu",
  "invite_code": "received-invitation-code"
}
```

`email` 为可选字段。用户名和已填写的邮箱入库前统一转换为小写；密码使用 Argon2
哈希存储。邀请码只以 SHA-256
摘要查询，并在同一数据库事务内通过行锁完成用户创建、可选的小组加入和邀请码消费。

### 登录

`POST /api/v1/auth/login`

```json
{
  "username": "alice_chen",
  "password": "a-strong-password"
}
```

响应包含 `access_token`、`token_type` 和 `expires_in`。

### 当前用户

`GET /api/v1/users/me`

```http
Authorization: Bearer <access_token>
```

Swagger UI 会根据路由模型自动显示字段、响应状态以及 HTTP Bearer 认证按钮。

## API 功能概览

以下业务接口均位于 `/api/v1`，受保护接口需要携带 Bearer JWT。完整请求字段、响应模型和
错误状态以 Swagger UI 或 OpenAPI 文档为准。

### 认证与用户

- `POST /api/v1/auth/register`：使用全局或团队邀请码注册
- `POST /api/v1/auth/login`：登录并获取 JWT access token
- `GET /api/v1/users/me`：获取当前用户
- `PATCH /api/v1/users/me`：更新昵称和个人简介
- `PATCH /api/v1/users/me/password`：验证原密码并修改密码
- `POST /api/v1/users/me/avatar`：上传当前用户头像
- `DELETE /api/v1/users/me/avatar`：删除当前用户头像
- `GET /api/v1/users/{user_id}/avatar`：读取用户头像

### 文件索引

- `GET /api/v1/files/index`：查询当前用户可访问的全局文件索引
- `GET /api/v1/projects/{project_id}/file-index`：查询科目共享文件和任务附件索引

现有文件上传、列表、下载、元数据修改和删除接口保持不变。索引接口只聚合已有 `File`
记录，不复制文件，也不创建额外索引数据。

### 资源删除

- `DELETE /api/v1/tasks/{task_id}`：永久删除任务及其关联数据和附件
- `DELETE /api/v1/projects/{project_id}`：永久删除科目及其任务、成员关系和文件
- `DELETE /api/v1/teams/{team_id}`：永久删除小组下的科目、任务、成员关系和文件

## Team API

所有 Team 接口都需要：

```http
Authorization: Bearer <access_token>
```

接口列表：

- `POST /api/v1/teams`：创建团队，创建者自动成为 leader
- `GET /api/v1/teams`：查询当前用户加入的全部团队及其角色
- `GET /api/v1/teams/{team_id}`：查询团队详情与成员列表
- `POST /api/v1/teams/{team_id}/invite`：leader 创建单次邀请码
- `POST /api/v1/teams/join`：当前用户使用邀请码加入团队
- `GET /api/v1/teams/{team_id}/members`：查询团队成员及角色
- `DELETE /api/v1/teams/{team_id}`：永久删除小组及其关联资源

创建团队示例：

```json
{
  "name": "Database Course Group",
  "description": "Semester group project",
  "course_name": "Database Systems"
}
```

创建邀请码示例：

```json
{
  "role": "member"
}
```

`role` 可选 `member` 或 `leader`，默认为 `member`。对外 API 使用 `leader`，数据库沿用
已有 `team_role.owner` 表示同一语义；所有 Team 权限均来自 `team_members`，不使用全局
管理员字段。邀请码明文只返回一次，数据库只保存 SHA-256，并在成功加入后标记为 `used`。

## 系统超级管理员 API

系统权限独立保存在 `system_admins`，与 Team 的 leader/member 角色无关。开发 seed 会为
默认 `admin` 创建 `super_admin` 授权；团队 leader 如果没有 `system_admins` 记录，访问
以下接口仍会得到 `403 Forbidden`：

- `GET /api/v1/admin/users`：查看所有用户
- `POST /api/v1/admin/users/{user_id}/ban`：封禁用户但保留历史数据
- `POST /api/v1/admin/users/{user_id}/unban`：解除封禁
- `DELETE /api/v1/admin/teams/{team_id}/members/{user_id}`：踢出团队
- `POST /api/v1/admin/invites`：生成一次性全局注册邀请码
- `GET /api/v1/admin/teams`：查看所有团队

所有接口都需要 Bearer JWT。封禁通过设置 `users.is_active=false` 实现，因此用户不能重新
登录，已经签发的 token 也无法继续通过当前用户校验；用户本身及其历史关联数据不会删除。
全局邀请码的 `team_id` 为 `NULL`，注册成功后不会自动加入特定团队，数据库仍只保存
SHA-256 摘要。

文件上传目录默认是 `uploads/`，该目录不进入 Git。数据库保存文件元数据和受控存储路径，
二进制内容保存在本地受控目录。上传时使用随机存储文件名并安全处理客户端文件名，文件
访问权限由 TeamMember、ProjectMember、TaskMember 和 SystemAdmin 关系动态计算。

## 后续推荐顺序

1. 增加刷新令牌、密码重置和邮箱验证流程。
2. 引入可选的异步提醒渠道和定时任务 worker。
3. 持续补充正常、越权、无效输入及并发场景测试。

## 设计依据

- [FastAPI 官方多文件应用指南](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [SQLAlchemy 官方 asyncio 文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic 官方 asyncio 配置说明](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)
- [Pydantic Settings 官方文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
