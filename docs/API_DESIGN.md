# API_DESIGN.md — 后端 API 设计

> 技术栈：FastAPI + Uvicorn，默认端口 **9001**，RESTful 风格。
> 数据存储：MooFile BSON（`data/db/*.bson`），音频产物：`data/audio/*.wav`。
> 统一前缀：`/api`。

## 1. 通用约定

### 1.1 统一响应结构

成功：
```json
{ "code": 0, "message": "ok", "data": { ... } }
```
失败：
```json
{ "code": 40001, "message": "voice not found", "data": null }
```
HTTP 状态码仍遵循语义（200/201/400/404/500），`code` 为业务码。

### 1.2 数据集合（MooFile）

| 集合文件 | 用途 |
|----------|------|
| `data/db/voices.bson` | 音色库（预设/克隆/设计） |
| `data/db/tasks.bson` | 合成任务 + 履历（任务完成后即履历记录） |

音频文件统一存放 `data/audio/`，通过 `/audio/<file>.wav` 静态访问。

### 1.3 枚举

- `voice.type`: `preset` | `clone` | `design`
- `task.language`: `zh` | `ja` | `en` | `auto`
- `task.status`: `pending` | `running` | `completed` | `failed`
- `voice.status`(克隆/设计生成中): `processing` | `ready` | `failed`

---

## 2. 系统与预设 ` /api/system`

### GET `/api/system/info`
返回运行时信息，供前端初始化。

**响应 data：**
```json
{
  "app_name": "Qwen3 TTS Studio",
  "version": "1.0.0",
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 3080",
  "models_loaded": { "custom_voice": false, "voice_design": false, "base": false },
  "preset_voices": [
    { "speaker": "Vivian", "label_zh": "明亮年轻女声", "language": "zh" },
    { "speaker": "Serena", "label_zh": "温暖柔和女声", "language": "zh" },
    { "speaker": "Uncle_Fu", "label_zh": "沉稳男声", "language": "zh" },
    { "speaker": "Dylan", "label_zh": "北京口音男声", "language": "zh" },
    { "speaker": "Eric", "label_zh": "四川口音男声", "language": "zh" },
    { "speaker": "Ryan", "label_zh": "动态英语男声", "language": "en" },
    { "speaker": "Aiden", "label_zh": "美式英语男声", "language": "en" },
    { "speaker": "Ono_Anna", "label_zh": "日语女声", "language": "ja" }
  ],
  "supported_languages": ["zh", "ja", "en", "auto"]
}
```

### POST `/api/system/preload`
可选：预热模型（后台加载，避免首次请求卡顿）。
**响应：** `{ "code": 0, "data": "loading started" }`

---

## 3. 音色管理 `/api/voices`

### GET `/api/voices`
列出全部音色。可按类型过滤。

**Query：** `type`(可选: preset/clone/design)、`keyword`(可选)
**响应 data：** `Voice[]`

```json
{
  "id": "v_xxx",
  "name": "Serena",
  "type": "preset",
  "speaker": "Serena",
  "language": "zh",
  "description": "温暖柔和的女性声音",
  "instruct": null,
  "ref_audio": null,
  "ref_text": null,
  "audio_url": null,
  "status": "ready",
  "created_at": "2026-10-11T10:00:00"
}
```
> 预设音色在内存中提供（不写入 BSON）；克隆/设计音色写入 `voices.bson`。

### GET `/api/voices/{voice_id}`
获取单个音色详情。

### DELETE `/api/voices/{voice_id}`
删除自定义音色（仅允许 `clone`/`design`，预设返回 400）。同时删除其预览音频文件。

---

## 4. 音色克隆 `/api/voices/clone`

### POST `/api/voices/clone`（multipart/form-data）
上传参考音频 + 参考文本，后台提取克隆声纹 prompt，生成可复用音色。

**表单字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `file` | file | 参考音频（wav/m4a/mp3） |
| `name` | string | 音色名称 |
| `ref_text` | string | 参考音频对应的文本 |

**响应 data：**
```json
{ "id": "v_clone_xxx", "name": "我的克隆音", "status": "processing" }
```
后台：保存参考音频 → 加载 base 模型 → `create_voice_clone_prompt` → 写入 voices.bson（status=ready）。前端轮询 `GET /api/voices/{id}` 直到 `ready`。

---

## 5. 音色设计 `/api/voices/design`

### POST `/api/voices/design`（application/json）
通过文字描述设计新音色，并生成一段预览音频。

**请求体：**
```json
{
  "name": "温柔姐姐",
  "instruct": "用温柔、缓慢、充满关怀的语气说话",
  "text": "大家好，欢迎来到我的电台。",
  "language": "zh"
}
```
**响应 data：**
```json
{ "id": "v_design_xxx", "name": "温柔姐姐", "status": "processing", "audio_url": null }
```
后台：加载 voice_design 模型 → `generate_voice_design` → 保存预览音频 → 写入 voices.bson（status=ready, audio_url=/audio/xxx.wav）。

---

## 6. 文本转语音 `/api/tts`

### POST `/api/tts`（application/json）
提交异步合成任务。**基本方针：长句拆分 → 逐段合成 → 合并输出。**

**请求体：**
```json
{
  "text": "要合成的长文本……",
  "voice_id": "v_xxx",
  "language": "auto",
  "instruct": null
}
```
- `voice_id`：音色 ID（预设音色使用系统预设 ID，如 `preset:Serena`）。
- `language`：`zh/ja/en/auto`。`auto` 时按语言分段（参考 edge_tts 的 `split_language_segments`），每段用对应语言合成。
- `instruct`：可选，临时语气指令（仅 preset/custom voice 支持）。

**响应 data（202）：**
```json
{ "id": "t_xxx", "status": "pending", "progress": 0 }
```

### GET `/api/tts/tasks`
任务列表 + 履历。

**Query：** `page`(默认1)、`page_size`(默认20)、`status`(可选)、`voice_id`(可选)
**响应 data：**
```json
{
  "total": 35,
  "page": 1,
  "page_size": 20,
  "items": [ Task ]
}
```

**Task 对象：**
```json
{
  "id": "t_xxx",
  "text": "要合成的长文本……",
  "voice_id": "v_xxx",
  "voice_name": "Serena",
  "voice_type": "preset",
  "language": "auto",
  "instruct": null,
  "status": "completed",
  "progress": 100,
  "error": null,
  "audio_url": "/audio/t_xxx.wav",
  "duration_sec": 12.4,
  "elapsed_sec": 3.1,
  "segments": [
    { "index": 0, "lang": "zh", "text": "其实我真的有发现。" }
  ],
  "created_at": "2026-10-11T10:00:00",
  "started_at": "2026-10-11T10:00:01",
  "completed_at": "2026-10-11T10:00:04"
}
```

### GET `/api/tts/tasks/{task_id}`
获取任务详情（轮询状态用）。

### GET `/api/tts/tasks/{task_id}/audio`
返回合成音频文件（`audio/wav`），支持浏览器播放与下载。

### DELETE `/api/tts/tasks/{task_id}`
删除任务记录及其音频文件。

---

## 7. 静态资源

- `/audio/**` → `data/audio/`（生成的音频、预览音频）
- `/` → `web/dist/`（前端 SPA，history fallback 到 index.html）

---

## 8. 错误码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 40001 | 参数错误 |
| 40401 | 资源不存在（音色/任务） |
| 40003 | 不允许删除预设音色 |
| 50001 | 模型未加载/推理失败 |
| 50002 | 音频文件读写失败 |
