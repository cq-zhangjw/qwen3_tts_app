# 小说配音（Novel Dubbing）设计文档

> 版本 v1.0 · 2026-10-11
> 目标：上传一本小说 → 自动分析角色 → 为角色分配音色 → 拆句并标注角色/语气 → 后台逐句配音 → 拼接成完整音频下载。

## 1. 流程概览

```
上传 .txt 文件
   │
   ▼
① 角色分析（自动）
   ├─ 旁白（Narrator）默认存在
   ├─ 提取对话引号内的台词 + 前文"XX说/道/问"中的角色名
   └─ 产出角色清单（可编辑、可增删）
   │
   ▼
② 为每个角色选择音色（从预设/克隆/设计音色中选）
   │
   ▼
③ 一键拆句
   ├─ 按句切分全文
   ├─ 引号内句子 → 对话 → 归属最近角色
   ├─ 环境/拟声（敲门声、沙沙声）→ type=sfx，默认用旁白话术朗读或跳过
   └─ 其余 → 旁白
   │
   ▼
④ 句子级编辑（可改角色、改文本、改语气提示词、删句、加句）
   │
   ▼
⑤ 一键配音（后台队列，进度 = 已合成句数 / 总句数）
   ├─ 每句用该角色音色 + 该句语气提示词
   ├─ 支持单句重配、单句删除、试听
   └─ 失败句标红可重试
   │
   ▼
⑥ 一键合成（按顺序拼接所有已完成句子，句间 0.3s 静音）
   │
   ▼
下载完整音频（wav）
```

## 2. 补充的考虑点（用户未明确处）

| 点 | 决策 |
|----|------|
| LLM 依赖 | 提供可插拔 OpenAI 兼容客户端（.env 配置 `NOVEL_LLM_BASE_URL/API_KEY/MODEL`）；未配置时用内置规则法（引号+说话人模式），开箱即用 |
| 环境音（敲门声） | 归为 `type=sfx`，默认用旁白话术朗读（"砰砰砰，三长两短的敲门声"），用户可在编辑时改为跳过该句 |
| 旁白音色 | 作为一个特殊角色，同样从音色库选，默认用沉稳大叔 |
| 多语言 | 句子级按语言自动检测（复用现有 text_split），角色音色对 zh/ja/en 通用 |
| 进度粒度 | 项目级进度 = done/total；每句有 pending/running/done/failed |
| 断点续配 | 已完成句子不重复合成；点"配音"只跑 pending/failed |
| 历史分组 | 项目列表按文件名分组，展开看每句状态；后台执行不阻塞 |

## 3. 数据模型（MooFile，存 data/db/）

### NovelProject
```json
{
  "id": "np_<hex>",
  "filename": "sample_novel.txt",
  "raw_text": "...",
  "characters": [
    {"id": "c_narrator", "name": "旁白", "color": "#64748b",
     "voice_id": "preset:novel_m_uncle", "instruct": "用平稳舒缓的叙述语气朗读"}
  ],
  "lines": [
    {"id": "L0001", "text": "暮春的午后……", "character_id": "c_narrator",
     "type": "narration", "instruct": null, "language": "zh",
     "status": "pending", "audio_url": null, "duration_sec": null, "error": null}
  ],
  "status": "idle",          // idle / dubbing / assembling / done / failed
  "done_count": 0,
  "total_count": 0,
  "final_audio_url": null,
  "created_at": "...", "updated_at": "..."
}
```

- `type`: `narration`（旁白）/ `dialogue`（对话）/ `sfx`（环境音）
- 每句音频存 `data/audio/novel/{project_id}/line_{line_id}.wav`
- 合成音频存 `data/audio/novel/{project_id}/final.wav`

## 4. API 设计（RESTful，前缀 /api/novel）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/novel/projects` | multipart 上传 txt，自动建项目+分析角色+拆句 |
| GET | `/api/novel/projects` | 项目列表（含进度） |
| GET | `/api/novel/projects/{id}` | 项目详情（角色+句子） |
| PATCH | `/api/novel/projects/{id}` | 更新角色音色/语气（body: characters） |
| POST | `/api/novel/projects/{id}/split` | 重新拆句（清空旧句子后重切） |
| POST | `/api/novel/projects/{id}/lines` | 手动加一句 |
| PATCH | `/api/novel/projects/{id}/lines/{lid}` | 编辑句子（text/character_id/type/instruct） |
| DELETE | `/api/novel/projects/{id}/lines/{lid}` | 删除一句 |
| POST | `/api/novel/projects/{id}/dub` | 开始配音（后台跑 pending/failed 句） |
| POST | `/api/novel/projects/{id}/lines/{lid}/redub` | 重配单句 |
| POST | `/api/novel/projects/{id}/assemble` | 拼接所有已完成句子 |
| GET | `/api/novel/projects/{id}/lines/{lid}/audio` | 单句音频 |
| GET | `/api/novel/projects/{id}/final` | 下载合成音频 |
| DELETE | `/api/novel/projects/{id}` | 删除项目 |

### 关键请求/响应

`POST /api/novel/projects` 响应：
```json
{"code":0,"data":{"id":"np_abc123","filename":"sample_novel.txt",
  "characters":[...],"lines":[...],"total_count":18,"done_count":0,"status":"idle"}}
```

`POST /api/novel/projects/{id}/dub` 响应：
```json
{"code":0,"data":{"status":"dubbing","total":18,"done":0}}
```

## 5. 前端 UI（Vue3 + NaiveUI，新增路由 novel）

### 布局
- 左侧：项目列表（文件名、进度条、创建时间，可展开看句子摘要）
- 右侧：当前项目工作台

### 工作台分区
1. **角色音色表**：每行 = 角色名（带色点）+ 音色下拉（分组：预设/克隆/设计）+ 默认语气输入框
2. **句子表**：
   - 列：序号 | 类型标签（旁白/对话/环境）| 文本（可编辑）| 角色下拉 | 语气提示词 | 状态 | 操作（试听/重配/删除）
   - PC 宽表，移动端卡片堆叠
3. **操作栏**：
   - 「开始配音」按钮 → 显示进度 `已合成 5/18`，进度条
   - 「重新拆句」「合成音频」「下载」
4. **试听**：每行播放直接 `new Audio('/api/novel/projects/{id}/lines/{lid}/audio')`，不重复推理

### 视觉规范
- 主色 `#6366F1`，圆角 10px，与现有风格一致
- 角色色点：旁白灰、角色按出现顺序自动配色（靛蓝/玫红/翠绿/琥珀…）
- Loading：配音时按钮 loading + 进度条 + 句子行 running 状态脉冲
- 三语 i18n（zh/ja/en）

## 6. 后端模块

- `core/novel.py`：
  - `analyze_characters(text)` — 提取角色（规则法；若配了 LLM 则用 LLM）
  - `split_lines(text, characters)` — 拆句、分类、归属角色
  - `dub_line(project, line)` — 单句合成（按 character.voice_id + line.instruct，按段语言）
  - `assemble(project)` — 拼接 wav（句间 0.3s 静音）
- `api/novel.py`：路由
- worker 新增 job kind：`novel_line`、`novel_assemble`（复用现有 GPU 串行队列）

## 7. 测试样例

使用 `tests/sample_novel.txt`（多角色古风短文，含旁白/对话/环境音敲门声）。
预期识别角色：旁白、先生、林清之、苏婉儿；句子数约 18。
