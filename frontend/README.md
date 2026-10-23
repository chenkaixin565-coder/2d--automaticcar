# 智能巡检机器人二维仿真系统 - 前端

## 技术栈

- Vue 3 + Vite
- Tailwind CSS v3
- 原生 Canvas
- Vitest + jsdom
- Playwright

## 常用命令

```bash
npm install       # 安装依赖
npm run dev       # 启动开发服务器
npm run build     # 构建生产产物到 dist/
npm run preview   # 预览生产构建
npm test          # 运行单元测试
npm run lint      # 运行 ESLint
npm run deploy    # 构建并部署到 GitHub Pages
```

## 数据服务层

`src/services/robotService.js` 定义统一接口；`src/services/simulatedService.js` 为本地仿真器实现。下一阶段接入 FastAPI 后端时，只需替换服务实现，界面组件无需改动。

## 截图脚本

```bash
npm run build
npm run preview -- --host 0.0.0.0 --port 4173
node scripts/screenshots.mjs
```

## 部署到 GitHub Pages

```bash
npm run deploy
```

运行前请确保本地已关联 GitHub 仓库，脚本会自动构建并推送到 `gh-pages` 分支。
