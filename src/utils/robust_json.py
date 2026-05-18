"""
safe_parse_json — 稳健解析 Ollama/LLM 返回的 JSON
纯标准库，处理 ANSI 转义、控制字符、markdown 包裹、截断等。
"""

import json
import re
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
#  公开接口
# ═══════════════════════════════════════════════════════════════

# ANSI CSI: ESC [ <params> <final>  覆盖 \x1b[1D \x1b[K \x1b[?25l 等
_ANSI_RE = re.compile(r"\x1b\[[\d;?]*[A-Za-z]")


def safe_parse_json(raw: str) -> Any:
    """
    将 LLM 返回的原始字符串稳健解析为 Python 对象。

    处理链（成功即返回，不执行后续步骤）：
      ① 移除 ANSI 转义序列（必须最先——否则其中的 [ ] 等字符干扰括号配对）
      ② 去除 markdown 代码块包裹
      ③ 提取最外层 JSON 载荷
      ④ 单遍状态机清洗
      ⑤ 直接解析 → ⑥ 去尾逗号 → ⑦ 补全截断
    """
    if not raw or not raw.strip():
        raise ValueError("输入为空")

    text = raw.strip()

    # ① ANSI 必须最先移除——\x1b[1D 中的 [ 会被误判为 JSON 数组括号
    text = _ANSI_RE.sub("", text)

    # ② 去除 markdown 代码块
    text = _strip_markdown_fences(text)

    # ③ 提取 JSON 载荷
    text = _extract_json_payload(text) or text

    # ④ 核心：单遍状态机
    text = _normalize(text)

    # ⑤ 直接解析
    result = _loads(text)
    if result is not None:
        return result

    # ⑥ 去除尾部逗号（状态机实现，不误伤字符串内逗号）
    text = _remove_trailing_commas(text)
    result = _loads(text)
    if result is not None:
        return result

    # ⑦ 补全截断括号
    text = _repair_truncated(text)
    result = _loads(text)
    if result is not None:
        return result

    raise ValueError(f"无法解析 JSON。清洗后前 300 字符: {text[:300]!r}")


# ═══════════════════════════════════════════════════════════════
#  内部实现
# ═══════════════════════════════════════════════════════════════

def _loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text, strict=False)
    except (json.JSONDecodeError, ValueError):
        return None


def _strip_markdown_fences(text: str) -> str:
    m = re.search(r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"^\s*```(?:json|JSON)?\s*\n?(.*)", text, re.DOTALL)
    return m.group(1).strip() if m else text


def _extract_json_payload(text: str) -> Optional[str]:
    """括号配对状态机，提取最外层 {} 或 []，正确跳过字符串内容。"""
    for open_ch, close_ch in [("{", "}"), ("[", "]")]:
        start = text.find(open_ch)
        if start == -1:
            continue
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if esc:
                esc = False
                continue
            if c == "\\" and in_str:
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
                    return text[start : i + 1]
    return None


def _normalize(text: str) -> str:
    # 0. 去除 ANSI 转义序列（必须最先处理）
    text = _ANSI_RE.sub("", text)
    
    # 0.5 修复 Ollama 特有畸形："alignment": "...\n"center"}} → 合并
    text = re.sub(r'":\s*"\s*\n\s*"([^"]*)"', r'": "\1"', text)

    # 以下为原状态机，保持不变
    out: list[str] = []
    in_str = False
    esc = False

    for c in text:
        # 转义状态
        if esc:
            if in_str:
                out.append(c)
            esc = False
            continue

        if c == "\\" and in_str:
            out.append(c)
            esc = True
            continue

        if c == '"':
            in_str = not in_str
            out.append(c)
            continue

        cp = ord(c)

        if in_str:
            if c == "\n":
                out.append("\\n")
            elif c == "\r":
                out.append("\\r")
            elif c == "\t":
                out.append("\\t")
            elif c in "\x85\u2028\u2029":
                out.append("\\n")
            elif c in "\ufeff\u200b\u200c\u200d\u200e\u200f":
                pass
            elif cp < 0x20 or c == "\x7f":
                pass
            else:
                out.append(c)
        else:
            if c in " \t\n\r":
                if not out or out[-1] != " ":
                    out.append(" ")
            elif (
                cp < 0x20
                or c == "\x7f"
                or c in "\x85\u2028\u2029\ufeff\u200b\u200c\u200d\u200e\u200f"
            ):
                pass
            else:
                out.append(c)

    return "".join(out)


def _remove_trailing_commas(text: str) -> str:
    """
    去除 } 或 ] 前的多余逗号。
    状态机实现——不误伤字符串内部的逗号。

    为什么不用 re.sub(r',\s*([}\]$$])', ...) ？
    因为正则不区分字符串内外，会误删 {"pattern": "[a-z],"} 中的逗号。
    """
    out: list[str] = []
    in_str = esc = False
    i = 0

    while i < len(text):
        c = text[i]
        if esc:
            out.append(c)
            esc = False
            i += 1
            continue
        if c == "\\" and in_str:
            out.append(c)
            esc = True
            i += 1
            continue
        if c == '"':
            in_str = not in_str
            out.append(c)
            i += 1
            continue

        if not in_str and c == ",":
            j = i + 1
            while j < len(text) and text[j] in " \t\n\r":
                j += 1
            if j < len(text) and text[j] in "}]":
                i = j  # 跳过逗号和中间空白，保留 } 或 ]
                continue

        out.append(c)
        i += 1

    return "".join(out)


def _repair_truncated(text: str) -> str:
    """
    补全被截断的 JSON。
    状态机统计未闭合括号（正确跳过字符串内容）。

    为什么不用 str.count('{') - str.count('}') ？
    因为 count 不区分引号内外：{"msg": "missing {"} 会被误判为多一个 {。
    """
    s = text.rstrip()
    open_b = open_s = 0
    in_str = esc = False
    quote_count = 0

    for c in s:
        if esc:
            esc = False
            continue
        if c == "\\" and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            quote_count += 1
            continue
        if in_str:
            continue
        if c == "{":
            open_b += 1
        elif c == "}":
            open_b -= 1
        elif c == "[":
            open_s += 1
        elif c == "]":
            open_s -= 1

    if quote_count % 2 != 0:
        s += '"'                          # 闭合未终止的字符串
    s += "]" * max(open_s, 0)             # 先补内层
    s += "}" * max(open_b, 0)             # 再补外层
    return s


# ═══════════════════════════════════════════════════════════════
#  测试
# ═══════════════════════════════════════════════════════════════

def run_tests():
    # 用 json.loads 生成期望值，确保"合法 JSON 不被破坏"的断言与标准库一致
    def expect(raw_json: str):
        return json.loads(raw_json, strict=False)

    cases = [
        # (输入原始字符串, 期望值, 描述)

        # ── 基础 ──────────────────────────────────────────
        ('{"a": 1}', expect('{"a": 1}'), "正常 JSON"),
        ("[1, 2, 3]", expect("[1, 2, 3]"), "数组根类型"),

        # ── Markdown 包裹 ─────────────────────────────────
        ('```json\n{"x": 1}\n```', {"x": 1}, "markdown json 包裹"),
        ('```\n{"x": 1}\n```', {"x": 1}, "markdown 无语言标记"),

        # ── 前后混杂文字 ──────────────────────────────────
        ('好的：\n{"r": "ok"}\n完毕', {"r": "ok"}, "前后混杂文字"),

        # ── ★ 真实案例：键值间裸换行 ─────────────────────
        (
            '{"title": {"font_name": "宋体", "size_pt": 24, "bold": true, "alignment":\n"center"}}',
            {"title": {"font_name": "宋体", "size_pt": 24, "bold": True, "alignment": "center"}},
            "★ 真实案例: alignment:\\ncenter"
        ),

        # ── ★ 真实案例：ANSI + 裸换行 ───────────────────
        (
            '{"title": {"font_name": "宋体", "size_pt": 24, "bold": true, "alignment":\x1b[1D\x1b[K"center"}}',
            {"title": {"font_name": "宋体", "size_pt": 24, "bold": True, "alignment": "center"}},
            "★ ANSI [1D][K] + 裸换行"
        ),
        (
            '{"key":\x1b[0m"value"}',
            {"key": "value"},
            "ANSI reset [0m] 在冒号后"
        ),
        (
            '\x1b[?25l{"data": 42}\x1b[?25h',
            {"data": 42},
            "ANSI cursor hide/show 包裹 JSON"
        ),
        (
            '\x1b[1m```json\n{"x":\x1b[K\n"y", "z": 1}\n```\x1b[0m',
            {"x": "y", "z": 1},
            "ANSI + markdown + 裸换行 全组合"
        ),

        # ── 合法转义不被破坏 ──────────────────────────────
        (
            '{"msg": "hello\\nworld"}',
            expect('{"msg": "hello\\nworld"}'),
            "字符串内 \\n（两字符）不被修改"
        ),
        (
            '{"path": "C:\\\\Users\\\\test"}',
            expect('{"path": "C:\\\\Users\\\\test"}'),
            "字符串内 \\\\（反斜杠）不被修改"
        ),
        (
            '{"q": "say \\"hi\\""}',
            expect('{"q": "say \\"hi\\""}'),
            "字符串内转义引号不被破坏"
        ),

        # ── 各种控制字符 ──────────────────────────────────
        (
            '{"a":\r\n1, "b":\t2}',
            {"a": 1, "b": 2},
            "裸 \\r\\n 和 \\t"
        ),
        (
            '{"k":\x85"v"}',
            {"k": "v"},
            "C1 控制字符 \\x85 (NEL)"
        ),
        (
            '\ufeff{"ok": true}',
            {"ok": True},
            "BOM 头"
        ),
        (
            '{"k":\u200b"v"}',
            {"k": "v"},
            "零宽空格 U+200B"
        ),
        (
            '{"a":\u20281}',
            {"a": 1},
            "行分隔符 U+2028"
        ),

        # ── 截断 ──────────────────────────────────────────
        (
            '{"name": "x", "arr": [1, 2',
            {"name": "x", "arr": [1, 2]},
            "截断：缺 ] 和 }"
        ),
        (
            '{"a": {"b": {"c": "deep"',
            {"a": {"b": {"c": "deep"}}},
            "截断：三层嵌套"
        ),
        (
            '{"msg": "hello',
            {"msg": "hello"},
            "截断：字符串中途断开"
        ),

        # ── 尾部逗号 ──────────────────────────────────────
        (
            '{"a": 1, "b": 2,}',
            {"a": 1, "b": 2},
            "尾部多余逗号"
        ),
        (
            '{"a": [1, 2,], "b": 3}',
            {"a": [1, 2], "b": 3},
            "数组内尾逗号"
        ),

        # ── 边界：字符串内含 JSON 分隔符（确保不去错逗号）─
        (
            '{"pattern": "[a,b]"}',
            expect('{"pattern": "[a,b]"}'),
            "字符串内的逗号不被误删"
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

    print(f"\n{'=' * 60}")
    print(f"  {passed}/{len(cases)} 通过, {failed} 失败")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_tests()
