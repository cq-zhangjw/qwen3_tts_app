# 最终测试报告 — Qwen3 TTS Studio

> 测试时间：2026-10-11
> 环境：Windows / Python 3.12.9 / RTX 3080 20G / Node 20 / Vite 6
> 后端：Uvicorn on `http://localhost:9001`；前端：`web/dist` 由后端静态托管。

## 1. 测试环境

| 项 | 值 |
|----|----|
| 操作系统 | Windows（PowerShell） |
| Python | 3.12.9（`.venv`） |
| GPU | NVIDIA GeForce RTX 3080（CUDA 可用） |
| 模型 | custom_voice / voice_design / base（均已就位） |
| 后端框架 | FastAPI 0.141 + Uvicorn 0.54 |
| 前端 | Vue3 + TS + NaiveUI，`npm run build` 通过 |
| 端口 | 9001 |

## 2. 测试范围与结果

| # | 测试项 | 方法 | 结果 |
|---|--------|------|------|
| 1 | 后端启动 | `uvicorn app:app --port 9001` | ✅ 正常启动，worker 线程启动 |
| 2 | `GET /api/system/info` | HTTP 调用 | ✅ 返回 GPU 信息、8 个预设音色、支持语言 |
| 3 | 前端首页托管 | `GET /` | ✅ 200，返回 dist/index.html（1230B） |
| 4 | `GET /api/voices` | HTTP 调用 | ✅ 空列表（初始无自定义音色） |
| 5 | 提交 TTS 任务（混合中英） | `POST /api/tts` | ✅ 返回 task_id，进入 pending→running |
| 6 | 长文本拆分→合成→合并 | 自动执行 | ✅ 自动拆为 zh 段 + en 段，分别合成后拼接 |
| 7 | 任务完成与音频产物 | 轮询 + 文件检查 | ✅ status=completed，生成 wav（153KB） |
| 8 | 音频下载端点 | `GET /api/tts/tasks/{id}/audio` | ✅ 200，`audio/wav`，字节数一致 |
| 9 | 模型缓存后速度 | 第二次任务 | ✅ 首次 55.6s（含加载），缓存后 4.65s |
| 10 | 日语合成 | `preset:Ono_Anna` | ✅ 正常完成 |
| 11 | 音色设计创建 | `POST /api/voices/design` | ✅ 后台加载设计模型，20s 生成预览 |
| 12 | 设计音色列表 | `GET /api/voices` | ✅ 设计音色出现，status=ready |
| 13 | 用设计音色合成 | `POST /api/tts` | ✅ 7.27s 完成，音频正常 |
| 14 | 错误处理（缺文本） | 参数校验 | ✅ FastAPI 返回 422/400 |

## 3. 实测数据记录

| 任务 | 音色 | 语言 | 状态 | 音频时长 | 合成耗时 |
|------|------|------|------|----------|----------|
| t_6b76a1fd0f | Serena（预设） | auto（中英混合） | completed | 3.2s | 55.6s（首载模型） |
| t_885a159624 | Ono_Anna（预设） | ja | completed | ~2.8s | 4.65s（模型缓存） |
| t_c3fd6e2878 | 温柔测试（设计音色） | zh | completed | ~4.5s | 7.27s |
| v_design_629595e617 | 温柔测试（设计预览） | zh | ready | — | ~20s（含模型加载） |

**语言分段验证**：输入 `"你好，这是一段合成测试。Hello world。"`，后端自动拆分为：
- `{lang: zh, text: "你好，这是一段合成测试。"}`
- `{lang: en, text: "Hello world。"}`

两段以各自语言合成后拼接，符合“长句拆分→转语音→合并输出”的方针。

## 4. 功能矩阵

| 功能 | 状态 | 说明 |
|------|------|------|
| 音色管理（列表/试听/删除） | ✅ | 预设 + 自定义；预设不可删 |
| 音色克隆 | ✅ 代码就绪 | multipart 上传参考音频，后台提取声纹（pickle 持久化） |
| 音色设计 | ✅ 已实测 | instruct 描述生成新音色 + 预览 |
| 文本转语音（异步任务） | ✅ 已实测 | 后台 worker 串行处理，进度回写 |
| 语音下载 | ✅ 已实测 | `/audio/*.wav` + 任务音频端点 |
| 合成履历 | ✅ 已实测 | 记录音色/文本/时间/耗时/状态 |
| 中/日/英/自动混合 | ✅ 已实测 | auto 模式按语言分段 |
| i18n（zh/ja/en） | ✅ | locales 三语文案齐全 |

## 5. 已知限制与说明

1. **首次模型加载较慢**（~50s）：三个 1.7B 模型按需懒加载，加载后驻留显存；后续任务秒级完成。
2. **GPU 任务串行**：单 worker 线程串行推理，避免 20G 显存竞争；高并发时任务排队。
3. **音色克隆未做端到端音频实测**：代码路径与设计音色一致（上传→后台提取→入库），依赖 base 模型的 `create_voice_clone_prompt`；实际效果需上传真实参考音频验证。
4. **chunk 体积警告**：前端主包 ~860KB（gzip 258KB），为 NaiveUI 全量组件所致，不影响功能。
5. **中文乱码仅出现在 PowerShell 控制台**：API 返回为标准 UTF-8 JSON，浏览器/前端渲染正常。

## 6. 结论

系统达到交付预期：FastAPI 后端（端口 9001）+ Vue3/NaiveUI 前端完整打通，支持音色管理、克隆、设计、异步 TTS、下载与履历；中/日/英自动混合合成的拆分→合并方针已验证。测试通过，可交付。
