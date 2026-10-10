# UI_DESIGN.md — 前端 UI 设计

> 技术栈：Vue3 + TypeScript + NaiveUI + vue-router + vue-i18n + axios。
> 多语言：中文(zh) / 日本語(ja) / English(en)。
> 目标：圆角化、多图标、现代柔和配色、自适应布局、完善 loading 反馈。

## 1. 设计系统（Design Token）

### 1.1 配色
- **主色 Primary**：`#6366F1`（靛蓝 Indigo）—— 传达 AI/科技感，柔和不刺眼。
- **辅助色**：
  - 成功 `#22C55E`，警告 `#F59E0B`，错误 `#EF4444`，信息 `#3B82F6`。
- **背景**：`#F5F7FA`（页面浅灰），卡片 `#FFFFFF`。
- **侧边栏**：深色渐变 `#1E1B4B → #312E81`（靛蓝深紫），白字菜单。
- **圆角**：全局 `border-radius: 10px`；卡片 12px；按钮 8px；输入框 8px。
- **阴影**：`0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(99,102,241,0.08)`。

通过 `NConfigProvider` 的 `themeOverrides` 统一注入圆角与主色。

### 1.2 字体与图标
- 字体：`vfonts`（已装，默认系统无衬线）。
- 图标：`@vicons/ionicons5`（已装），所有菜单项、按钮、空状态均配图标。
  - 首页/合成：`MicOutline` / `PlayCircleOutline`
  - 音色库：`PeopleOutline` / `VoiceOutline`
  - 克隆：`CopyOutline` / `CloudUploadOutline`
  - 设计：`ColorWandOutline` / `SparklesOutline`
  - 履历：`TimeOutline` / `ListOutline`
  - 语言：`LanguageOutline`
  - 删除/下载/播放：`TrashOutline` / `DownloadOutline` / `PlayOutline`

### 1.3 Loading 规范
- 提交合成：按钮 `:loading="true"` + 禁用，内容区 `NSpin`。
- 列表加载：`NDataTable` 内置 loading。
- 异步任务：任务卡片显示 `NProgress`（progress 0-100）+ 状态标签。
- 克隆/设计：卡片显示 `NProgress` + “生成中…”，完成后自动刷新。

## 2. 整体布局

```
┌──────────────────────────────────────────────────┐
│  Header: [Logo] Qwen3 TTS Studio    [语言切换][模型状态] │
├──────────┬───────────────────────────────────────┤
│ 侧边栏    │                                       │
│ ─ 合成台  │        主内容区（router-view）           │
│ ─ 音色库  │                                       │
│ ─ 音色克隆 │                                       │
│ ─ 音色设计 │                                       │
│ ─ 合成履历 │                                       │
│          │                                       │
├──────────┴───────────────────────────────────────┤
│  Footer: Copyright                                  │
└───────────────────────────────────────────────────┘
```

- 使用 `NLayout` + `NLayoutSider`（可折叠，`width: 220px`，移动端抽屉式）。
- 响应式：`NGrid` + `NGI`（cols=24），桌面双列、平板单列；窄屏 (<768px) 侧边栏默认折叠为抽屉。

## 3. 页面明细

### 3.1 合成台 `/`（Home / Studio）
- 左侧卡片：文本输入区
  - `NInput type=textarea`（rows=10，字数统计）
  - 音色选择 `NSelect`（分组：预设音色 / 我的音色）
  - 语言选择 `NRadioGroup`（zh/ja/en/auto，圆角按钮）
  - 可选语气指令 `NInput`（折叠面板“高级选项”）
  - 提交按钮 `NButton type=primary`（带 Mic 图标，loading 态）
- 右侧卡片：合成结果
  - 未提交：空状态（`NEmpty` + 图标）
  - 合成中：`NProgress` + 进度 + 状态标签
  - 完成：`NAudio`/自定义播放器 + 下载按钮 + “使用此音色的最近记录”

### 3.2 音色库 `/voices`
- 顶部：类型筛选 `NRadioGroup`（全部/预设/克隆/设计）+ 搜索框。
- 内容：`NGrid` 卡片列表，每张卡片：
  - 头像区（圆形图标，按类型着色：预设=靛蓝、克隆=绿、设计=紫）
  - 名称、类型标签 `NTag`、语言标签
  - 描述
  - 播放按钮（试听预览音频，无预览则禁用）
  - 删除按钮（仅自定义音色，`NPopconfirm` 确认）

### 3.3 音色克隆 `/clone`
- 表单卡片：
  - `NUpload`（drag 拖放区，限 wav/mp3/m4a，显示已上传文件名 + 试听）
  - 音色名称 `NInput`
  - 参考文本 `NInput type=textarea`
  - 提交按钮（CloudUpload 图标，loading 态）
- 提交后：结果卡片显示“生成中…”进度；完成后提示并提供“前往音色库查看”。

### 3.4 音色设计 `/design`
- 表单卡片：
  - 设计展示文本 `NInput type=textarea`（将朗读此文本生成预览）
  - 音色描述/instruct `NInput type=textarea`（如“温柔缓慢、充满关怀”）
  - 音色名称 `NInput`
  - 语言 `NSelect`
  - 提交按钮（Sparkles 图标，loading 态）
- 完成后：内嵌音频播放器试听新音色预览。

### 3.5 合成履历 `/history`
- `NDataTable` 列：
  - 状态（NTag：完成=绿、失败=红、进行中=蓝）
  - 音色（名称 + 类型标签）
  - 文本预览（省略，popover 显示全文）
  - 语言
  - 耗时（秒）
  - 时长（秒）
  - 创建时间 / 完成时间
  - 操作：播放、下载、删除
- 顶部：状态筛选 + 分页。

## 4. 国际化文案

- `web/public/locales/{zh,ja,en}.json` 维护。
- 命名空间：`nav.*`（菜单）、`studio.*`、`voices.*`、`clone.*`、`design.*`、`history.*`、`common.*`（按钮/状态/占位）。
- Header 语言切换 `NSelect`（zh/ja/en），写入 localStorage，切换后调用 `i18n.global.locale`。

## 5. 前端工程要点

- `vite.config.ts`：开发时代理 `/api` → `http://localhost:9001`；构建输出 `dist/`。
- `.env.production`：`VITE_API_BASE=/api`（同源部署，无需跨域）。
- axios 实例 baseURL 读 `VITE_API_BASE`。
- 路由：hash 模式；移除脚手架中无用的 Login/Chat 页与 eel.js 引用。
- 音频播放器：原生 `<audio controls>` 封装为小组件，避免引入额外依赖。
