# Qwen3 TTS Studio

基于 **Qwen3-TTS** 的自托管配音管理网站：集音色管理、音色克隆、音色设计、异步文本转语音、语音下载与合成履历于一体，支持中文 / 日语 / 英语及混合自动检测。

## 项目特色

- 🎙️ **全流程配音工作台**：合成台（含内嵌履历）、音色库、音色克隆、音色设计四大模块。
- 🌍 **中 / 日 / 英 + 自动混合**：按句判定语言（含假名整句为日语，日文汉字不再误判），混合文本自动切分、逐段合成、拼接输出。
- ✂️ **长文本拆分→合成→合并**：按句子边界切分长句，逐段推理后拼接，避免单次输入过长。
- 🎭 **10 种内置小说音色**：男女各 5 种（温柔姐姐/明亮少女/知性御姐/清冷仙子/深情女主；沉稳大叔/温暖青年/低沉磁性/冷峻男主/说书人），每种带语气指令。
- 🔊 **预生成试听**：启动时后台预热所有预设音色试听，播放为本地缓存、零临时推理。
- 🌐 **三语一致音色设计**：设计音色时同时生成中/日/英三段预览，混合合成保持同一音色。
- 🧬 **三种音色来源**：预设音色、参考音频克隆、文字描述设计，统一存入音色库。
- ⚡ **异步任务队列**：GPU 推理 RLock 串行化后台执行，前端轮询进度，不阻塞交互。
- 🎨 **现代 UI**：Vue3 + TypeScript + NaiveUI，圆角卡片、图标化可收缩菜单、三语切换、PC 两列 / 移动单列自适应。
- 🗂️ **零外部数据库**：使用 MooFile（BSON 文件库），数据统一落盘 `data/`。

## 架构图

```
┌──────────────────────────── Browser (SPA) ───────────────────────────┐
│  Vue3 + TS + NaiveUI  (hash router, vue-i18n zh/ja/en, axios)        │
│  合成台 / 音色库 / 克隆 / 设计 / 履历                                  │
└──────────────────────────────┬───────────────────────────────────────┘
                                │  /api/*  /audio/*
┌──────────────────────────────▼───────────────────────────────────────┐
│  FastAPI (uvicorn, :9001)                                           │
│  /system   /voices   /tts   static dist                               │
│       │          │          │                                         │
│  core/config   core/database (MooFile BSON: voices/tasks)           │
│  core/tts_engine (lazy 3 models)   core/worker (serial GPU queue)  │
│       │                                                             │
│  Qwen3TTSModel: custom_voice / voice_design / base (CUDA, bf16)     │
└──────────────────────────────────────────────────────────────────────┘
                                │
                       data/db/*.bson , data/audio/*.wav
```

## 功能概要

| 模块 | 说明 |
|------|------|
| 合成台 | 输入文本、选音色、选语言模式，提交异步任务；右侧两列任务卡片（PC）/ 单列（移动），含进度、播放、下载、删除 |
| 音色库 | 卡片展示全部音色（10 预设/克隆/设计），试听直接播放缓存、按性别/类型筛选、删除 |
| 音色克隆 | 上传参考音频 + 参考文本，后台提取声纹生成可复用音色 |
| 音色设计 | 用自然语言描述音色（instruct），一次生成中/日/英三段预览 |

## API 概要（RESTful，前缀 `/api`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/system/info` | 系统信息、GPU、预设音色、模型加载状态 |
| GET | `/api/voices` | 音色列表（可按 type/keyword 过滤） |
| GET | `/api/voices/{id}` | 音色详情 |
| DELETE | `/api/voices/{id}` | 删除自定义音色 |
| POST | `/api/voices/clone` | multipart 上传参考音频创建克隆音色 |
| POST | `/api/voices/design` | JSON 创建设计音色 |
| POST | `/api/tts` | 提交异步合成任务 |
| GET | `/api/tts/tasks` | 任务/履历列表（分页） |
| GET | `/api/tts/tasks/{id}` | 任务详情（轮询状态） |
| GET | `/api/tts/tasks/{id}/audio` | 下载合成音频 |
| DELETE | `/api/tts/tasks/{id}` | 删除任务与音频 |

详细设计见 [`docs/API_DESIGN.md`](docs/API_DESIGN.md)。

## UI 概要

- 布局：深色渐变侧边栏（图标菜单）+ 顶栏（页面标题、模型状态、语言切换）+ 自适应内容区。
- 主色 `#6366F1`（靛蓝），圆角 10px，卡片悬浮阴影。
- 三语：简体中文 / English / 日本語，切换写入 localStorage。
- Loading：按钮 loading、`NSpin`、任务进度条、表格 loading。
- 详细设计见 [`docs/UI_DESIGN.md`](docs/UI_DESIGN.md)。

## 环境构筑

### 依赖

- Python 3.12 + CUDA GPU
- Node.js 18+
- Qwen3-TTS 模型（默认路径见 `.env`）：
  - `qwen3-tts-12hz-1.7b-custom_voice`
  - `qwen3-tts-12hz-1.7b-voice_design`
  - `qwen3-tts-12hz-1.7b-base`

### 后端

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# 配置 .env（端口、模型路径、数据目录）
python app.py            # 或 uvicorn app:app --port 9001
```

### 前端

```powershell
cd web
npm install
npm run build            # 产物输出到 web/dist，由后端托管
# 开发模式：npm run dev（已配置 /api 代理到 :9001）
```

构建后访问 `http://localhost:9001`。

## 目录结构

```
qwen3_tts/
├── app.py                # FastAPI 入口
├── api/                  # 子路由：system / voices / tts
├── core/                 # config, database, tts_engine, worker, text_split
├── utils/                # moofile_util, qwen3_tts_util, sound_util
├── data/                 # 运行时数据（gitignore）：db/*.bson, audio/*.wav
├── web/                  # Vue3 + TS + NaiveUI 前端
│   ├── src/
│   │   ├── pages/        # Studio / Voices / Clone / Design / History
│   │   ├── api/          # axios 封装
│   │   ├── router/ i18n.ts main.ts App.vue
│   └── public/locales/    # zh / ja / en
├── docs/                 # RD / API_DESIGN / UI_DESIGN
└── tests/final_report.md
```

## 文档索引

- 原始需求：[`docs/RD.md`](docs/RD.md)
- API 设计：[`docs/API_DESIGN.md`](docs/API_DESIGN.md)
- UI 设计：[`docs/UI_DESIGN.md`](docs/UI_DESIGN.md)
- 测试报告：[`tests/final_report.md`](tests/final_report.md)
