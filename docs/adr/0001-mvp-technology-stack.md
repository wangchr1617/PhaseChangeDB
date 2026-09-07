# ADR-0001：MVP 技术栈与脚手架

- 状态：已采用
- 日期：2026-09-03

## 背景

仓库已有 FastAPI/Pydantic 契约、MySQL 模式、Elasticsearch 模板和 Neo4j 图模式，但缺少可安装、可启动、可测试的全栈工程框架。

## 决策

- 使用 uv 初始化 Python 项目、管理依赖并生成 `uv.lock`；
- 使用 Vite 官方脚手架生成 React + TypeScript 前端；
- 使用 pnpm 管理前端依赖并提交锁文件；
- 使用 SQLAlchemy Async + asyncmy 连接 MySQL 8.4；
- 使用 Docker Compose 编排 MySQL、API 和 Web；
- MVP 只注册已经实现的 API，未完成契约不以占位错误形式对外暴露；
- Elasticsearch、Neo4j、对象存储与 AI 提取在后续纵向切片中接入。

## 理由

该组合与现有 Python 契约兼容，前后端启动路径清晰，依赖可锁定，且能够在不破坏 MySQL 唯一事实源与事务性 Outbox 原则的前提下快速形成可运行闭环。

## 影响

- 开发者需要 Python 3.11+、uv、Node.js 22+ 和 Corepack/pnpm；
- 完整本地部署需要 Docker Compose；
- 前端以 OpenAPI 为接口事实来源，后续应引入自动生成客户端，避免重复维护类型；
- 数据库模式进入实际部署后，后续变化必须采用有序迁移，而不是覆盖 `mysql/001_schema.sql`。
