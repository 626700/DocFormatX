"""
样式解析器 - 读取 YAML 样式文件，返回结构化的 StyleDocument 对象。
"""
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class TextStyle:
    """单个文本样式定义"""
    font_name: Optional[str] = None
    size_pt: Optional[float] = None
    bold: Optional[bool] = None
    alignment: Optional[str] = None
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None
    first_line_indent_chars: Optional[float] = None
    line_spacing: Optional[float] = None


@dataclass
class ImageStyle:
    """图片样式定义"""
    width_cm: float = 12
    alignment: str = "center"


@dataclass
class HeaderRule:
    """单节页眉规则"""
    text: Optional[str] = None
    image_path: Optional[str] = None


@dataclass
class SectionRule:
    """单节页面规则"""
    page: int = 1
    header_text: Optional[str] = None
    header_image: Optional[str] = None
    page_number_start: Optional[int] = None


@dataclass
class StyleDocument:
    """完整的样式文档"""
    name: str = "未命名样式"
    title: TextStyle = field(default_factory=TextStyle)
    heading_1: TextStyle = field(default_factory=TextStyle)
    heading_2: TextStyle = field(default_factory=TextStyle)
    body: TextStyle = field(default_factory=TextStyle)
    inline_image: ImageStyle = field(default_factory=ImageStyle)
    sections: List[SectionRule] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "StyleDocument":
        """从 YAML 文件加载样式"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"样式文件为空: {path}")

        doc = cls()
        meta = data.get("metadata", {})
        doc.name = meta.get("name", "未命名样式")

        styles = data.get("styles", {})

        # 解析各级样式
        for key, target in [
            ("title", doc.title),
            ("heading_1", doc.heading_1),
            ("heading_2", doc.heading_2),
            ("body", doc.body),
        ]:
            if key in styles:
                s = styles[key]
                target.font_name = s.get("font_name")
                target.size_pt = s.get("size_pt")
                target.bold = s.get("bold")
                target.alignment = s.get("alignment")
                target.space_before_pt = s.get("space_before_pt")
                target.space_after_pt = s.get("space_after_pt")
                target.first_line_indent_chars = s.get("first_line_indent_chars")
                target.line_spacing = s.get("line_spacing")

        # 图片样式
        img = styles.get("inline_image", {})
        doc.inline_image = ImageStyle(
            width_cm=img.get("width_cm", 12),
            alignment=img.get("alignment", "center"),
        )

        # 页面设置
        page_setup = data.get("page_setup", {})
        for sec in page_setup.get("sections", []):
            doc.sections.append(SectionRule(
                page=sec.get("page", 1),
                header_text=sec.get("header_text"),
                header_image=sec.get("header_image"),
                page_number_start=sec.get("page_number_start"),
            ))

        return doc