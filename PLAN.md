# Plan: World Cup Football News Website（实时方案）

## Context
用户需要一个展示世界杯足球新闻的网站：
- 已部署上线，无需本地运行
- 实时获取（用户刷新即最新，无需定时任务）
- AInvest 品牌风格
- 数据来源：免费 RSS（BBC Sport、ESPN、Goal.com）

## 架构

```
浏览器 ──> Vercel 前端 (index.html)
              └──> Vercel Function (api/fetch.js) ──> RSS 源
```

- **前端**：纯静态 `index.html` + JS，通过 `fetch('/api/fetch')` 拉取新闻后动态渲染
- **云函数**：`api/fetch.js`，运行在 Vercel Edge，负责抓取 RSS 并返回 JSON（解决跨域）
- **部署**：Vercel 关联 GitHub 仓库，push 即自动部署，无需任何 CI/CD 配置

## 项目结构

```
world-cup-news/
├── api/
│   └── fetch.js        ← Vercel Serverless Function（Node.js）
├── index.html          ← 前端页面（静态）
├── vercel.json         ← 可选配置（缓存策略等）
└── .gitignore
```

## 实现步骤

### Step 1：创建项目目录
在 `c:\cc-workspace\projects\world-cup-news\` 建立文件结构。

### Step 2：Vercel 云函数 (`api/fetch.js`)
- 使用 Node.js `https` 模块抓取多个 RSS（无需额外依赖）
- 解析 XML 提取：标题、链接、摘要、发布时间、来源
- 关键词过滤：`world cup / 2026 / FIFA / Copa`（兜底保留普通足球新闻）
- 返回 JSON，设置 `Cache-Control: s-maxage=300`（Vercel CDN 缓存5分钟，避免频繁打源站）

RSS 来源：
- BBC Sport Football: `https://feeds.bbci.co.uk/sport/football/rss.xml`
- ESPN Soccer: `https://www.espn.com/espn/rss/soccer/news`
- Goal.com: `https://www.goal.com/feeds/en/news`

### Step 3：前端 (`index.html`)
- 页面加载时调用 `fetch('/api/fetch')` 获取新闻数据
- AInvest 品牌风格：深色背景 `#0A0E1A`，绿色主色 `#00C37C`
  - 先读取 `C:\cc-workspace\_design-system\ainvest-design\` 确认 token
- 布局：顶部 Bar（Logo + 标题 + 更新时间）→ 新闻卡片 Grid
- 每张卡片：来源 Chip / 标题 / 摘要 / 时间 / 跳转链接
- 加载态：骨架屏（避免白屏感）
- 响应式，适配移动端

### Step 4：部署到 Vercel
1. `git init` + push 到 GitHub（新建 public 仓库）
2. vercel.com → New Project → 关联该 GitHub 仓库 → Deploy
3. 得到 `https://world-cup-news-xxx.vercel.app` 访问地址

## 用户需要做的事（一次性）
1. 在 GitHub 新建一个空 public 仓库（如 `world-cup-news`），告诉我 URL
2. 注册 / 登录 vercel.com，关联 GitHub 账号
3. 我完成所有代码推送后，在 Vercel 点 "Import" 部署即可

## 关键文件

| 文件 | 作用 |
|------|------|
| `api/fetch.js` | 抓取 RSS + 解析 + 返回 JSON |
| `index.html` | 前端页面，动态渲染新闻 |

## 验证方式
- `vercel dev` 本地预览（可选）
- 推送后访问 Vercel 提供的 URL，查看新闻是否正常加载
- F5 刷新验证实时性
- 打开 DevTools Network 确认 `/api/fetch` 返回 200 + JSON

## 权衡说明
- 优点：GitHub 仓库干净，无自动提交；实时最新；Vercel 比 GitHub Pages 更快（全球 CDN）
- 缺点：首次加载有约 1-2 秒请求延迟（用骨架屏掩盖）；Vercel 免费额度：函数调用 100k/月，完全够用
