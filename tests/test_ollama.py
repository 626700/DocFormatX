"""测试 OllamaManager 结构化对话"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from utils.ollama_manager import OllamaManager

m = OllamaManager()
d = m.structured_chat(
    "你是一个文档格式抽取器。只输出严格的JSON，不要任何额外文字。",
    '标题用黑体二号居中，一级标题用黑体三号加粗。输出格式：{"title": {"font_name": "...", "size_pt": ..., "bold": ..., "alignment": "..."}}'
)
print("修复后:", d)