"""
safe_parse_json - 稳健解析 LLM/Ollama 返回的 JSON
仅依赖标准库，处理控制字符、markdown 包裹、截断等全部常见问题。
"""

import json
import re
from typing import Any


def safe_parse_json(raw: str) -> Any:
    """
    将 LLM 返回的原始字符串稳健地解析为 Python 对象。

    处理链（每步成功即返回，不执行后续步骤）：
      ① 去除 markdown 代码块
      ② 提取最外层 JSON 载荷
      ③ 单遍状态机：字符串内转义控制字符 + 字符串外折叠空白
      ④ 尝试解析
      ⑤ 去除尾部多余逗号后解析
      ⑥ 补全截断括号后解析
    """
    if not raw or not raw.strip():
        raise ValueError("输入为空")

    # ① 去 markdown 包裹
    text = _strip_markdown_fences(raw.strip())

    # ② 提取 JSON 载荷
    text = _extract_json_payload(text) or text

    # ③ 单遍状态机清洗
    text = _normalize(text)

    # ④ 直接解析
    result = _loads(text)
    if result is not None:
        return result

    # ⑤ 去尾部逗号
    no_comma = re.sub(r",\s*([}\]])", r"\1", text)
    result = _loads(no_comma)
    if result is not None:
        return result

    # ⑥ 补全截断
    repaired = _repair_truncated(no_comma)
    result = _loads(repaired)
    if result is not None:
        return result

    raise ValueError(f"无法解析 JSON。清洗后前 300 字符: {text[:300]!r}")


# ═══════════════════════════════════════════════════════════
#  内部实现
# ═══════════════════════════════════════════════════════════

def _loads(text: str) -> Any | None:
    """尝试 json.loads，失败返回 None。"""
    try:
        return json.loads(text, strict=False)
    except (json.JSONDecodeError, ValueError):
        return None


def _strip_markdown_fences(text: str) -> str:
    """去除 ```json ... ``` 包裹（含只有开头没有结尾的情况）。"""
    m = re.search(r'^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'^\s*```(?:json|JSON)?\s*\n?(.*)', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


def _extract_json_payload(text: str) -> str | None:
    """
    用括号配对状态机从混杂文本中提取最外层 {} 或 []。
    正确跳过字符串内容中的括号。
    """
    for open_ch, close_ch in [('{', '}'), ('[', ']')]:
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            c = text[i]
            if esc:
                esc = False
                continue
            if c == '\\' and in_str:
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def _normalize(text: str) -> str:
    """
    单遍状态机，一次遍历完成所有清洗：

    字符串内部：
      - \\n \\r \\t → 转义为 \\\\n \\\\r \\\\t（保留语义）
      - \\x85 \\u2028 \\u2029 → 转义为 \\\\n（Unicode 换行当换行处理）
      - 其余 C0 控制字符 / \\u200b 零宽字符 / BOM → 删除

    字符串外部：
      - 连续空白折叠为单个空格
      - 所有控制字符 / 零宽字符 → 删除

    这是解决 Ollama "alignment":\\n"center" 问题的核心函数。
    原因：裸换行出现在两个 JSON token 之间（字符串外部），
    必须在这里折叠掉，否则 json.loads 会报 Invalid control character。
    """
    out = []
    in_str = False
    esc = False

    for c in text:
        if esc:
            if in_str:
                out.append(c)
            esc = False
            continue

        if c == '\\' and in_str:
            out.append(c)
            esc = True
            continue

        if c == '"':
            in_str = not in_str
            out.append(c)
            continue

        if in_str:
            # ── 字符串内部 ──
            if c == '\n':
                out.append('\\n')
            elif c == '\r':
                out.append('\\r')
            elif c == '\t':
                out.append('\\t')
            elif c in '\x85\u2028\u2029':
                out.append('\\n')           # Unicode 换行 → 转义换行
            elif c == '\ufeff' or c in '\u200b\u200c\u200d\u200e\u200f':
                pass                        # BOM / 零宽 → 删除
            elif ord(c) < 0x20 or c == '\x7f':
                pass                        # C0 控制字符 → 删除
            else:
                out.append(c)
        else:
            # ── 字符串外部（token 之间）──
            if c in ' \t\n\r':
                if out and out[-1] != ' ':
                    out.append(' ')         # 连续空白折叠
            elif ord(c) < 0x20 or c == '\x7f' or c in '\x85\u2028\u2029\ufeff\u200b\u200c\u200d':
                pass                        # 控制 / 零宽 → 删除
            else:
                out.append(c)

    return ''.join(out)


def _repair_truncated(text: str) -> str:
    """
    尝试补全被截断的 JSON：
      1. 统计未闭合的 { [（状态机，正确跳过字符串内括号）
      2. 如果字符串中途被截断（引号数为奇数），先闭合字符串
      3. 补全缺失的 ] 和 }

    用状态机而非 .count() 的原因：
      .count('{') 会把字符串内的 { 也算进去，例如
      '{"msg": "missing {"}' 会被误判为多了一个未闭合的 {。
    """
    s = text.rstrip()
    open_b = 0      # { 计数
    open_s = 0      # [ 计数
    in_str = False
    esc = False
    quote_count = 0

    for c in s:
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            quote_count += 1
            continue
        if in_str:
            continue
        if c == '{':
            open_b += 1
        elif c == '}':
            open_b -= 1
        elif c == '[':
            open_s += 1
        elif c == ']':
            open_s -= 1

    # 修复尾部逗号
    s = re.sub(r',\s*$', '', s)

    # 闭合未终止的字符串
    if quote_count % 2 != 0:
        s += '"'

    # 补全括号（先内层后外层）
    s += ']' * max(open_s, 0)
    s += '}' * max(open_b, 0)

    return s


# ═══════════════════════════════════════════════════════════
#  测试
# ═══════════════════════════════════════════════════════════

def run_tests():
    cases = [
        # (输入, 期望输出, 描述)

        # ── 基本 ─────────────────────────────────────────
        (
            '{"a": 1}',
            {"a": 1},
            "正常 JSON"
        ),
        (
            '[1, 2, 3]',
            [1, 2, 3],
            "数组根类型"
        ),

        # ── Markdown 包裹 ────────────────────────────────
        (
            '```json\n{"ok": true}\n```',
            {"ok": True},
            "markdown json 包裹"
        ),
        (
            '```\n{"ok": true}\n```',
            {"ok": True},
            "markdown 无语言标记"
        ),

        # ── 混杂文本 ────────────────────────────────────
        (
            '好的，这是你要的：\n{"result": "success"}\n希望有帮助！',
            {"result": "success"},
            "前后混有普通文本"
        ),
        (
            'The answer is: [1, 2, 3] which is correct.',
            [1, 2, 3],
            "文本中的数组"
        ),

        # ── ★ 真实案例：键值对之间的裸换行 ──────────────
        (
            '{"title": {"font_name": "宋体", "size_pt": 24, "bold": true, "alignment":\n"center"}}',
            {"title": {"font_name": "宋体", "size_pt": 24, "bold": True, "alignment": "center"}},
            "★ 真实案例：alignment:\\ncenter"
        ),

        # ── 裸 \\r\\n / \\t ──────────────────────────────
        (
            '{"a":\r\n1, "b":\t2}',
            {"a": 1, "b": 2},
            "裸 \\r\\n 和 \\t"
        ),
        (
            '{"key":\r"value"}',
            {"key": "value"},
            "裸 \\r"
        ),

        # ── 字符串内部控制字符 ──────────────────────────
        (
            '{"msg": "line1\\nline2"}',
            {"msg": "line1\\nline2"},
            "字符串内已转义的 \\n（应保留原样）"
        ),

        # ── 截断 ────────────────────────────────────────
        (
            '{"name": "test", "items": [1, 2, 3',
            {"name": "test", "items": [1, 2, 3]},
            "截断：缺 ] 和 }"
        ),
        (
            '{"a": {"b": {"c": "deep"',
            {"a": {"b": {"c": "deep"}}},
            "截断：三层嵌套未闭合"
        ),
        (
            '{"msg": "hello wor',
            {"msg": "hello wor"},
            "截断：字符串中途断开"
        ),

        # ── 尾部多余逗号 ────────────────────────────────
        (
            '{"a": 1, "b": 2,}',
            {"a": 1, "b": 2},
            "尾部多余逗号"
        ),
        (
            '[1, 2, 3,]',
            [1, 2, 3],
            "数组尾部多余逗号"
        ),

        # ── 组合拳：markdown + 控制字符 + 截断 ─────────
        (
            '```json\n{"font": "宋体", "size":\n24, "bold": tru',
            {"font": "宋体", "size": 24, "bold": "tru"},
            "markdown + 控制字符 + 截断"
        ),

        # ── BOM / 零宽字符 ──────────────────────────────
        (
            '\ufeff{"ok": true}',
            {"ok": True},
            "BOM 头"
        ),
        (
            '{"key":\u200b"value"}',
            {"key": "value"},
            "零宽空格 U+200B"
        ),

        # ── Unicode 换行符 ──────────────────────────────
        (
            '{"a":\u20281}',
            {"a": 1},
            "行分隔符 U+2028"
        ),
    ]

    passed = failed = 0
    for i, (raw, expected, desc) in enumerate(cases, 1):
        try:
            result = safe_parse_json(raw)
            if result == expected:
                print(f"  ✅  {i:02d}  {desc}")
                passed += 1
            else:
                print(f"  ❌  {i:02d}  {desc}")
                print(f"       期望: {expected!r}")
                print(f"       实际: {result!r}")
                failed += 1
        except Exception as e:
            print(f"  ❌  {i:02d}  {desc}")
            print(f"       异常: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"  结果: {passed}/{len(cases)} 通过, {failed} 失败")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    run_tests()
