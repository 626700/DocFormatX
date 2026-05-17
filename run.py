import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from core.renderer import render
render(Path("examples/test_style.yaml"), Path("examples/test_content.txt"), Path("output/test.docx"))
print("文档生成成功！请查看 output/test.docx")
