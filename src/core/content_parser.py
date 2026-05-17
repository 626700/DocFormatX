"""
内容解析器 - 读取 TXT 标记文本，返回结构化的内容块列表。
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class ContentBlock:
    """单个内容块"""
    type: str           # title / heading_1 / heading_2 / body / image / table
    text: str = ""
    image_path: Optional[str] = None
    props: Dict[str, str] = field(default_factory=dict)


def parse_content(path: Path) -> List[ContentBlock]:
    """
    解析标记文本文件。
    支持标记：
      [title]、[h1]、[h2]
      [table] 或 [table:方向=竖, 样式=三线表]
      ![描述](路径)
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks: List[ContentBlock] = []
    body_lines: List[str] = []
    in_table = False
    table_lines: List[str] = []
    table_props: Dict[str, str] = {}

    def flush_body():
        nonlocal body_lines
        text = "".join(body_lines).strip()
        if text:
            blocks.append(ContentBlock(type="body", text=text))
        body_lines = []

    def flush_table():
        nonlocal table_lines, table_props
        if table_lines:
            blocks.append(ContentBlock(type="table", text="\n".join(table_lines), props=table_props))
            table_lines = []
            table_props = {}

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_table:
                flush_table()
                in_table = False
            else:
                if body_lines:
                    body_lines.append(line)
            continue

        # 表格标记
        if stripped.startswith("[table"):
            flush_body()
            in_table = True
            table_props = {}
            if stripped.startswith("[table:") and stripped.endswith("]"):
                attr_str = stripped[7:-1]
                for part in attr_str.split(","):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        table_props[k.strip()] = v.strip()
                    else:
                        if part == "vertical":
                            table_props["方向"] = "竖"
                        elif part == "三线表":
                            table_props["样式"] = "三线表"
            continue

        if in_table:
            if stripped.startswith("|") and stripped.endswith("|"):
                table_lines.append(stripped)
                continue
            else:
                flush_table()
                in_table = False

        # 标题标记
        if stripped.startswith("[title]"):
            flush_body()
            text = stripped.replace("[title]", "", 1).strip()
            blocks.append(ContentBlock(type="title", text=text))
        elif stripped.startswith("[h1]"):
            flush_body()
            text = stripped.replace("[h1]", "", 1).strip()
            blocks.append(ContentBlock(type="heading_1", text=text))
        elif stripped.startswith("[h2]"):
            flush_body()
            text = stripped.replace("[h2]", "", 1).strip()
            blocks.append(ContentBlock(type="heading_2", text=text))
        elif stripped.startswith("!["):
            flush_body()
            desc_end = stripped.index("]")
            path_start = stripped.index("(") + 1
            path_end = stripped.index(")")
            img_path = stripped[path_start:path_end]
            blocks.append(ContentBlock(type="image", image_path=img_path))
        else:
            body_lines.append(line)

    if in_table:
        flush_table()
    flush_body()

    return blocks