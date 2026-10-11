# Qwen3 TTS Studio — 第二轮迭代测试报告

测试时间：2026-10-11
环境：Windows / RTX 3080 20G / Python 3.12 (`.venv`) / 端口 9001

## 本轮需求（6 点反馈）与结果

| # | 需求 | 实现 | 验证 |
|---|------|------|------|
| 1 | 侧边栏收缩效果不对 | `n-menu` 显式绑定 `:collapsed`，收缩时只显示图标 | 收缩后菜单图标正常显示，不再出现空紫色块 |
| 2 | 履历布局：PC 右侧两列 / 移动单列 | 右侧任务列表改为 `n-grid :cols="2"`，`span-laptop=1 / span-mobile=2` | PC 两列卡片，移动端自动堆叠 |
| 3 | 日文汉字被误判为中文 | 重写 `split_language_segments` 为**按句判定**：句子含任意假名则整句判为日语（含汉字），无假名的 CJK 才判中文 | `彼女は東京大学で日本語を勉強しています。` → 整句 `ja`；`今日はいい天気` → `ja`，汉字不再误判 |
| 4 | 10 种小说音色，男女各 5 | 后端 `PRESET_VOICES` 重定义为 10 个：女（温柔姐姐/明亮少女/知性御姐/清冷仙子/深情女主），男（沉稳大叔/温暖青年/低沉磁性/冷峻男主/说书人），每个带 speaker + instruct + gender + 三语标签 | `/api/system/info` 返回 10 条，性别字段正确 |
| 5 | 所有音色预生成试听，播放不推理 | 启动时后台预热所有预设到 `data/audio/previews/preset_<id>.wav`；`system/info` 返回 `audio_url`，前端优先直接 `new Audio(audio_url)` 播放，仅缓存缺失时才调 preview 接口 | 10/10 预览文件生成，播放为本地缓存零推理 |
| 6 | 音色设计同时生成中/日/英三段 | `design_create` 对 zh/ja/en 各合成一段，存 `{voice_id}_zh/_ja/_en.wav`；设计页展示三个播放按钮 | 生成 `_zh.wav/_ja.wav/_en.wav` 三文件，三语试听可播 |

## 关键接口实测

```
GET /api/system/info
→ presets: 10
  preset:novel_f_gentle | 温柔姐姐 | female | audio:/audio/previews/preset_novel_f_gentle.wav
  ...（共 10 条，audio_url 全部非空）

POST /api/tts  body={text:"你好，这是一段测试。こんにちは、今日はいい天気ですね。",
                     voice_id:"preset:novel_m_uncle", language:"auto"}
→ status: completed
  segments: [('zh','你好，这是一段测试。'), ('ja','こんにちは、今日はいい天気ですね。')]
  audio: /audio/t_<id>.wav

POST /api/voices/design  body={name, instruct, text, language:"zh"}
→ voice ready
  audio_url_zh: /audio/v_design_<id>_zh.wav
  audio_url_ja: /audio/v_design_<id>_ja.wav
  audio_url_en: /audio/v_design_<id>_en.wav
```

## 语言分段回归用例

| 输入 | 输出 |
|------|------|
| `今天天气真不错。こんにちは、今日はいい天気ですね。` | `[('zh','今天天气真不错。'), ('ja','こんにちは、今日はいい天気ですね。')]` |
| `私は学生です。これは本です。` | `[('ja','私は学生です。これは本です。')]`（汉字 学生/本 不再误判） |
| `你好，世界。Hello world。` | `[('zh','你好，世界。'), ('en','Hello world。')]` |
| `彼女は東京大学で日本語を勉強しています。` | `[('ja',...)]` |

## 构建与联调

- 前端：`cd web && npm run build` → `dist/` 生成成功（vite 4.9s）
- 后端：`uvicorn app:app --port 9001`，静态目录绑定 `web/dist`，根路径返回 200 且含 `#app`
- 预热：首次启动后台串行合成 10 个预设预览（GPU RLock 串行化，与 worker 任务排队），约 1 分钟内全部完成，之后重启跳过已缓存文件

## 已知限制

- 预热占用 GPU 约 1 分钟；期间若发起合成会排队等待（设计如此，避免显存竞争）。
- 10 个小说音色复用少数 base speaker（Serena/Vivian/Uncle_Fu/Dylan），通过 `instruct` 区分性格，音色基底相同但语气有别。
- 旧版残留的 `preset_Vivian.wav` 等文件不影响功能，可忽略。

## 第三轮迭代（语言切换修复 + 分语言音色映射）

| 反馈 | 实现 | 验证 |
|------|------|------|
| 界面语言切换失效 | App.vue setup 只解构了 `t` 未解构 `locale`，导致 `onLangChange` 静默失败；补 `locale` 解构 | 顶栏语言下拉可切换 zh/en/ja |
| 去掉自动混合下拉，改必选中/日/英音色 | POST /api/tts 改为 `voice_map:{zh,ja,en}`（三者必选）；前端合成台三个独立必选选择器，后台按段语言分配音色 | `zh:沉稳大叔 / ja:温柔姐姐 / en:明亮少女` 三段分别用对应音色合成，21.67s 完成；缺 ja/en 返回 400 `missing voices: ja,en` |

实测分段：`你好…中文测试。`→zh 大叔；`こんにちは…`→ja 温柔姐姐；`Hello…`→en 明亮少女。
