"""测试小米AI robust_json 与 OllamaManager 集成"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.robust_json import safe_parse_json

# 模拟 Ollama 真实输出（含有裸换行）
raw = '{"title": {"font_name": "宋体", "size_pt": 24, "bold": true, "alignment":\n"center"}}'

print("原始输出:", repr(raw))
print()

# 直接用 safe_parse_json 解析
try:
    result = safe_parse_json(raw)
    print("✅ 解析成功!")
    print("结果:", result)
    print("alignment 值:", result["title"]["alignment"])
except ValueError as e:
    print("❌ 解析失败:", e)