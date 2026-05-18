"""启动 DocFormatX GUI"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from gui.main_window import main
main()