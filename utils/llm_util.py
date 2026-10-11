from __future__ import annotations

import json
import re

from utils.model_util import MODEL

# Novel dubbing script-analysis prompt. The LLM reads a chunk of a novel and
# returns STRICT JSON describing characters + per-line dubbing instructions.
SYSTEM_PROMPT = (
    "你是一个小说配音脚本分析专家。用户会给你一段小说原文，你要把它拆成适合配音的句子，并标注每个句子由哪个角色朗读、语气如何。\n"
    "要求：\n"
    "1. 找出文中所有会说话的角色，哪怕只说一句话的次要角色也要列出，并务必包含旁白（旁白固定叫“旁白”）。只提取真正会说话或叙述的角色，不要把动作/景物当角色。\n"
    "2. 把原文按配音句子切分，每句对应一句台词或一段叙述。不要合并太多，也不要切碎。保留原文用词，不要改写。\n"
    "3. 每句标注：text(原文句子)、speaker(说话角色名，旁白用“旁白”)、type(narration=旁白/叙述, dialogue=对话, sfx=环境音/拟声如敲门声沙沙声)、instruct(简短语气提示词，如“平静地说”“略带惊讶”，没有则留空)。\n"
    "4. 环境音/拟声句 type 标为 sfx，speaker 用“旁白”。\n"
    "5. 只输出 JSON，不要任何解释或 markdown 代码块。格式：\n"
    '{"characters":[{"name":"角色名","gender":"male|female","note":"简短描述"}],'
    '"lines":[{"text":"...","speaker":"...","type":"narration|dialogue|sfx","instruct":""}]}\n'
)


def _extract_json(text: str) -> dict:
    """Robustly parse JSON from an LLM reply, tolerating ``` fences and prose."""
    text = text.strip()
    # strip code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # find first { ... last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def llm_analyze_chunk(user_text: str, known_characters: list[str] | None = None) -> dict:
    """Call the LLM on one chunk; returns {characters:[...], lines:[...]}."""
    sys = SYSTEM_PROMPT
    if known_characters:
        sys += f"\n已知角色列表：{known_characters}。新句子尽量归到这些角色名下；如出现新角色再加入。"
    resp = MODEL.invoke([
        {"role": "system", "content": sys},
        {"role": "user", "content": user_text},
    ])
    content = resp.content if hasattr(resp, "content") else str(resp)
    return _extract_json(content)
