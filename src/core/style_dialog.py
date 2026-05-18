"""
对话式 YAML 生成器 - 分步对话，自然语言 → 样式文件。
"""
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from utils.ollama_manager import OllamaManager


SYSTEM_PROMPT = """你是一个文档格式抽取器。用户描述某个元素的格式，你只输出严格JSON，不含任何其他文字。
输出字段说明：
- font_name: 字体名称，如"黑体"、"宋体"、"仿宋"、"楷体"
- size_pt: 字号（磅值），二号=22, 三号=16, 四号=14, 小四=12, 五号=10.5
- bold: 是否加粗，true/false
- alignment: 对齐方式，left/center/right/justify
- space_before_pt: 段前间距（磅）
- space_after_pt: 段后间距（磅）
- line_spacing: 行距倍数，如1.5
- first_line_indent_chars: 首行缩进字符数，如2
"""

STEPS = [
    {
        "key": "title",
        "question": "请描述【文档大标题】的格式。例如：黑体二号居中加粗。",
        "schema": {
            "font_name": "字体名",
            "size_pt": "字号(pt)",
            "bold": "是否加粗",
            "alignment": "对齐",
        },
    },
    {
        "key": "heading_1",
        "question": "请描述【一级标题】的格式。",
        "schema": {
            "font_name": "字体名",
            "size_pt": "字号(pt)",
            "bold": "是否加粗",
            "alignment": "对齐",
            "space_before_pt": "段前间距(pt)",
        },
    },
    {
        "key": "heading_2",
        "question": "请描述【二级标题】的格式。（若无二级标题可回复“无”）",
        "schema": {
            "font_name": "字体名",
            "size_pt": "字号(pt)",
            "bold": "是否加粗",
        },
    },
    {
        "key": "body",
        "question": "请描述【正文】的格式。例如：仿宋小四，首行缩进2字符，1.5倍行距。",
        "schema": {
            "font_name": "字体名",
            "size_pt": "字号(pt)",
            "first_line_indent_chars": "首行缩进字符数",
            "line_spacing": "行距倍数",
        },
    },
]


class StyleDialogFSM:
    """样式对话状态机"""

    def __init__(self, ollama: OllamaManager):
        self.ollama = ollama
        self.step_index = 0
        self.collected: Dict[str, Any] = {}
        self.finished = False

    @property
    def current_question(self) -> Optional[str]:
        if self.finished:
            return None
        if self.step_index < len(STEPS):
            return STEPS[self.step_index]["question"]
        return None

    def submit(self, user_text: str) -> Dict[str, Any]:
        """处理用户输入，返回当前字段的解析结果"""
        if self.finished:
            return {}

        step = STEPS[self.step_index]
        key = step["key"]
        schema = step["schema"]

        # 构造 prompt
        schema_str = json.dumps(schema, ensure_ascii=False)
        prompt = f"用户描述：{user_text}\n请输出JSON，字段：{schema_str}"

        data = self.ollama.structured_chat(SYSTEM_PROMPT, prompt)

        if data:
            self.collected[key] = data
        else:
            self.collected[key] = {}

        self.step_index += 1
        if self.step_index >= len(STEPS):
            self.finished = True

        return data

    def generate_yaml(self, name: str = "AI生成样式") -> str:
        """将收集的样式合成为 YAML 字符串"""
        styles = {}
        for step in STEPS:
            key = step["key"]
            if key in self.collected and self.collected[key]:
                styles[key] = self.collected[key]

        doc = {
            "metadata": {"name": name},
            "styles": styles,
            "page_setup": {
                "sections": [
                    {"page": 1, "header_text": None},
                    {"page": 2, "header_text": None},
                    {"page": 3, "header_text": None},
                    {"page": 4, "header_text": None, "page_number_start": 1},
                ]
            },
            "table": {
                "default_style": "three_line",
                "alignment": "center",
                "header_bold": True,
                "borders": {
                    "top": {"visible": True, "weight_pt": 1.5, "color": "000000"},
                    "bottom": {"visible": True, "weight_pt": 1.5, "color": "000000"},
                    "insideH": {"visible": True, "weight_pt": 0.5, "color": "000000"},
                    "insideV": {"visible": False},
                    "left": {"visible": False},
                    "right": {"visible": False},
                },
            },
        }
        return yaml.dump(doc, allow_unicode=True, sort_keys=False)

    def save_yaml(self, path: Path, name: str = "AI生成样式"):
        """保存为 .style.yaml 文件"""
        yaml_str = self.generate_yaml(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_str, encoding="utf-8")
        return path