"""
内容解析器 - 读取 TXT 标记文本，返回结构化的内容块列表。
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ContentBlock:
    """单个内容块"""
    type: str           # title / heading_1 / heading_2 / body / image
    text: str = ""
    image_path: Optional[str] = None


def parse_content(path: Path) -> List[ContentBlock]:
    """
    解析标记文本文件。
    支持标记：[title]、[h1]、[h2]、![描述](路径)
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks: List[ContentBlock] = []
    body_lines: List[str] = []

    def flush_body():
        """将缓存的正文行合并为一个块"""
        nonlocal body_lines
        text = "".join(body_lines).strip()
        if text:
            blocks.append(ContentBlock(type="body", text=text))
        body_lines = []

    for line in lines:
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            if body_lines:
                body_lines.append(line)
            continue

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

        # 图片标记
        elif stripped.startswith("!["):
            flush_body()
            # 格式：![描述](路径)
            desc_end = stripped.index("]")
            path_start = stripped.index("(") + 1
            path_end = stripped.index(")")
            img_path = stripped[path_start:path_end]
            blocks.append(ContentBlock(type="image", image_path=img_path))

        # 普通正文
        else:
            body_lines.append(line)

    # 处理最后残留的正文
    flush_body()

    return blocks