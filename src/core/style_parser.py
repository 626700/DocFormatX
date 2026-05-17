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
class BorderRule:
    """单条边框规则"""
    visible: bool = True
    weight_pt: float = 1.0
    color: str = "000000"


@dataclass
class TableBorders:
    """表格所有边框规则"""
    top: BorderRule = field(default_factory=BorderRule)
    bottom: BorderRule = field(default_factory=BorderRule)
    insideH: BorderRule = field(default_factory=BorderRule)
    insideV: BorderRule = field(default_factory=BorderRule)
    left: BorderRule = field(default_factory=BorderRule)
    right: BorderRule = field(default_factory=BorderRule)


@dataclass
class TableStyle:
    """表格样式定义"""
    default_style: str = "full_grid"
    alignment: str = "center"
    header_bold: bool = True
    borders: TableBorders = field(default_factory=TableBorders)


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
    table_style: TableStyle = field(default_factory=TableStyle)

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

        # 解析表格样式
        table_cfg = data.get("table", {})
        if table_cfg:
            ts = doc.table_style
            ts.default_style = table_cfg.get("default_style", "full_grid")
            ts.alignment = table_cfg.get("alignment", "center")
            ts.header_bold = table_cfg.get("header_bold", True)

            borders = table_cfg.get("borders", {})
            for side in ["top", "bottom", "insideH", "insideV", "left", "right"]:
                b = borders.get(side, {})
                setattr(ts.borders, side, BorderRule(
                    visible=b.get("visible", True),
                    weight_pt=b.get("weight_pt", 1.0),
                    color=b.get("color", "000000"),
                ))

        return doc