"""测试对话式 YAML 生成器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from utils.ollama_manager import OllamaManager
from core.style_dialog import StyleDialogFSM

m = OllamaManager()
fsm = StyleDialogFSM(m)

print("=" * 50)
print("  样式对话生成器测试")
print("=" * 50)

for i in range(4):
    q = fsm.current_question
    if q is None:
        break
    print(f"\n🤖 AI: {q}")
    # 模拟用户输入
    if i == 0:
        user_input = "大标题用黑体二号居中加粗，段前段后各12磅"
    elif i == 1:
        user_input = "一级标题用黑体三号加粗，段前10磅"
    elif i == 2:
        user_input = "二级标题用楷体四号"
    else:
        user_input = "正文用仿宋小四，首行缩进2字符，1.5倍行距"

    print(f"👤 用户: {user_input}")
    result = fsm.submit(user_input)
    print(f"✅ 解析: {result}")

print("\n" + "=" * 50)
print("  生成的 YAML 样式：")
print("=" * 50)
print(fsm.generate_yaml("测试样式"))

# 保存到文件
output = Path("output/test_ai_style.yaml")
fsm.save_yaml(output, "AI测试样式")
print(f"\n📁 已保存到: {output}")