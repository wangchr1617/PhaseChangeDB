# 前端协作规范

- 本目录采用 React、TypeScript、Vite 和 pnpm，禁止混用 npm/yarn 锁文件。
- 用户界面、无障碍标签、注释及说明默认使用简体中文。
- API 类型应集中定义，公共接口发生变化时同步更新；不得建立第二套后端契约。
- 页面必须具备加载、空数据、错误和窄屏状态。
- 提交前至少运行 `pnpm lint`、`pnpm typecheck` 和 `pnpm build`。
