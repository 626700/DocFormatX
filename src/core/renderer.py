"""
文档渲染器 - 将样式 + 内容块合成为 Word 文档。
"""
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import logging

from .style_parser import StyleDocument, TextStyle, ImageStyle
from .content_parser import ContentBlock, parse_content

log = logging.getLogger(__name__)

# 对齐方式映射
ALIGN_MAP = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _apply_text_style(paragraph, style: TextStyle):
    """将 TextStyle 应用到段落的每个 run"""
    for run in paragraph.runs:
        if style.font_name:
            run.font.name = style.font_name
            # 设置中文字体（必须操作 XML）
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(qn('w:rFonts'))
            if rFonts is None:
                from lxml import etree
                rFonts = etree.SubElement(rPr, qn('w:rFonts'))
            rFonts.set(qn('w:eastAsia'), style.font_name)

        if style.size_pt:
            run.font.size = Pt(style.size_pt)

        if style.bold is not None:
            run.bold = style.bold


def _apply_paragraph_style(paragraph, style: TextStyle):
    """将 TextStyle 应用到段落的段落属性"""
    pf = paragraph.paragraph_format

    if style.alignment and style.alignment in ALIGN_MAP:
        paragraph.alignment = ALIGN_MAP[style.alignment]

    if style.space_before_pt is not None:
        pf.space_before = Pt(style.space_before_pt)

    if style.space_after_pt is not None:
        pf.space_after = Pt(style.space_after_pt)

    if style.line_spacing is not None:
        pf.line_spacing = style.line_spacing

    if style.first_line_indent_chars is not None:
        # 两个字符 ≈ 当前字号的 2 倍
        indent_pt = (style.size_pt or 12) * style.first_line_indent_chars
        pf.first_line_indent = Pt(indent_pt)


def render(style_path: Path, content_path: Path, output_path: Path):
    """
    主渲染函数：
    1. 加载样式 YAML
    2. 解析内容 TXT
    3. 生成 Word 文档
    """
    # 1. 加载样式
    style_doc = StyleDocument.from_yaml(style_path)
    log.info("已加载样式: %s", style_doc.name)

    # 2. 解析内容
    blocks = parse_content(content_path)
    log.info("已解析 %d 个内容块", len(blocks))

    # 3. 创建 Word 文档
    doc = Document()

    # 设置默认正文字体（防止 Word 默认西文字体覆盖中文字体）
    default_font = style_doc.body.font_name or "宋体"
    style = doc.styles["Normal"]
    style.font.name = default_font
    style.element.rPr.rFonts.set(qn('w:eastAsia'), default_font)

    # 4. 逐块写入
    for block in blocks:
        if block.type == "title":
            p = doc.add_paragraph(block.text)
            _apply_paragraph_style(p, style_doc.title)
            _apply_text_style(p, style_doc.title)

        elif block.type == "heading_1":
            p = doc.add_paragraph(block.text)
            _apply_paragraph_style(p, style_doc.heading_1)
            _apply_text_style(p, style_doc.heading_1)

        elif block.type == "heading_2":
            p = doc.add_paragraph(block.text)
            _apply_paragraph_style(p, style_doc.heading_2)
            _apply_text_style(p, style_doc.heading_2)

        elif block.type == "body":
            p = doc.add_paragraph(block.text)
            _apply_paragraph_style(p, style_doc.body)
            _apply_text_style(p, style_doc.body)

        elif block.type == "image":
            img_path = Path(block.image_path)
            if img_path.exists():
                p = doc.add_paragraph()
                if style_doc.inline_image.alignment in ALIGN_MAP:
                    p.alignment = ALIGN_MAP[style_doc.inline_image.alignment]
                run = p.add_run()
                run.add_picture(str(img_path), width=Cm(style_doc.inline_image.width_cm))
            else:
                log.warning("图片不存在: %s", img_path)
                p = doc.add_paragraph(f"[图片缺失: {img_path.name}]")

    # 5. 处理分节和页眉页脚
    section_rules = style_doc.sections
    if section_rules:
        # 确保节数足够
        while len(doc.sections) < len(section_rules):
            doc.add_section()

        for i, rule in enumerate(section_rules):
            section = doc.sections[i]
            # 断开与前一节的链接
            section.header.is_linked_to_previous = False
            section.footer.is_linked_to_previous = False

            # 设置页眉
            if rule.header_text:
                header = section.header
                if header.paragraphs:
                    hp = header.paragraphs[0]
                else:
                    hp = header.add_paragraph()
                hp.text = rule.header_text

            # 设置页脚页码
            if rule.page_number_start is not None:
                footer = section.footer
                if footer.paragraphs:
                    fp = footer.paragraphs[0]
                else:
                    fp = footer.add_paragraph()
                fp.alignment = WD_ALIGN_PARAGRAPH.CENTER

                # 添加页码域
                run = fp.add_run()
                fldChar1 = run._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'begin'})
                run._element.append(fldChar1)

                instrText = run._element.makeelement(qn('w:instrText'), {})
                instrText.text = " PAGE "
                run._element.append(instrText)

                fldChar2 = run._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'end'})
                run._element.append(fldChar2)

                # 设置起始页码
                sectPr = section._sectPr
                pgNumType = sectPr.find(qn('w:pgNumType'))
                if pgNumType is None:
                    from lxml import etree
                    pgNumType = etree.SubElement(sectPr, qn('w:pgNumType'))
                pgNumType.set(qn('w:start'), str(rule.page_number_start))

    # 6. 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    log.info("文档已生成: %s", output_path)
    return output_path