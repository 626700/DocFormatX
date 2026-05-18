"""
DocFormatX 主窗口 - PySide6 GUI
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFileDialog, QMessageBox, QProgressBar,
    QLineEdit, QGroupBox, QFormLayout, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal

# 导入核心模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.renderer import render
from core.style_dialog import StyleDialogFSM
from utils.ollama_manager import OllamaManager


class RenderWorker(QThread):
    """后台渲染线程，避免 UI 卡死"""
    finished = Signal(str)      # 成功时发送文件路径
    error = Signal(str)         # 失败时发送错误信息

    def __init__(self, style_path, content_path, output_path):
        super().__init__()
        self.style_path = style_path
        self.content_path = content_path
        self.output_path = output_path

    def run(self):
        try:
            render(Path(self.style_path), Path(self.content_path), Path(self.output_path))
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocFormatX - 离线智能文档排版引擎")
        self.setMinimumSize(800, 600)

        # 初始化 AI 管理器
        self.ollama = OllamaManager()

        # 中央选项卡
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 三个标签页
        self.tab_render = RenderTab()
        self.tab_dialog = StyleDialogTab(self.ollama)
        self.tab_about = AboutTab()

        self.tabs.addTab(self.tab_render, "📄 渲染文档")
        self.tabs.addTab(self.tab_dialog, "🤖 对话生成样式")
        self.tabs.addTab(self.tab_about, "ℹ️ 关于")


class RenderTab(QWidget):
    """渲染文档标签页"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # 样式文件选择
        group_style = QGroupBox("1. 选择样式文件 (.yaml)")
        form_style = QFormLayout()
        self.edit_style = QLineEdit()
        self.edit_style.setPlaceholderText("点击右侧按钮选择 YAML 样式文件...")
        btn_style = QPushButton("浏览...")
        btn_style.clicked.connect(self._browse_style)
        row_style = QHBoxLayout()
        row_style.addWidget(self.edit_style)
        row_style.addWidget(btn_style)
        form_style.addRow(row_style)
        group_style.setLayout(form_style)
        layout.addWidget(group_style)

        # 内容文件选择
        group_content = QGroupBox("2. 选择内容文件 (.txt)")
        form_content = QFormLayout()
        self.edit_content = QLineEdit()
        self.edit_content.setPlaceholderText("点击右侧按钮选择 TXT 内容文件...")
        btn_content = QPushButton("浏览...")
        btn_content.clicked.connect(self._browse_content)
        row_content = QHBoxLayout()
        row_content.addWidget(self.edit_content)
        row_content.addWidget(btn_content)
        form_content.addRow(row_content)
        group_content.setLayout(form_content)
        layout.addWidget(group_content)

        # 输出路径
        group_output = QGroupBox("3. 输出文件")
        form_output = QFormLayout()
        self.edit_output = QLineEdit("output/document.docx")
        btn_output = QPushButton("选择...")
        btn_output.clicked.connect(self._browse_output)
        row_output = QHBoxLayout()
        row_output.addWidget(self.edit_output)
        row_output.addWidget(btn_output)
        form_output.addRow(row_output)
        group_output.setLayout(form_output)
        layout.addWidget(group_output)

        # 渲染按钮
        self.btn_render = QPushButton("🚀 生成 Word 文档")
        self.btn_render.setMinimumHeight(40)
        self.btn_render.clicked.connect(self._render)
        layout.addWidget(self.btn_render)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 状态标签
        self.label_status = QLabel("就绪")
        layout.addWidget(self.label_status)

        layout.addStretch()

    def _browse_style(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择样式文件", "", "YAML 文件 (*.yaml *.yml)")
        if path:
            self.edit_style.setText(path)

    def _browse_content(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择内容文件", "", "文本文件 (*.txt)")
        if path:
            self.edit_content.setText(path)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 Word 文档", "output/document.docx", "Word 文档 (*.docx)")
        if path:
            self.edit_output.setText(path)

    def _render(self):
        style_path = self.edit_style.text().strip()
        content_path = self.edit_content.text().strip()
        output_path = self.edit_output.text().strip()

        if not style_path or not content_path:
            QMessageBox.warning(self, "缺少文件", "请选择样式文件和内容文件。")
            return

        self.btn_render.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度
        self.label_status.setText("正在生成文档...")

        self.worker = RenderWorker(style_path, content_path, output_path)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, path):
        self.progress.setVisible(False)
        self.btn_render.setEnabled(True)
        self.label_status.setText(f"✅ 文档已生成: {path}")
        QMessageBox.information(self, "完成", f"文档已成功生成！\n\n📁 {path}")

    def _on_error(self, err):
        self.progress.setVisible(False)
        self.btn_render.setEnabled(True)
        self.label_status.setText(f"❌ 错误: {err}")
        QMessageBox.critical(self, "渲染失败", err)


class StyleDialogTab(QWidget):
    """对话生成样式标签页"""
    def __init__(self, ollama: OllamaManager):
        super().__init__()
        self.ollama = ollama
        self.fsm: StyleDialogFSM = None

        layout = QVBoxLayout(self)

        # 对话区域
        splitter = QSplitter(Qt.Vertical)

        # 对话历史
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("对话记录将显示在这里...")
        splitter.addWidget(self.chat_history)

        # 用户输入区
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(80)
        self.input_field.setPlaceholderText("在此输入你的回答...")
        input_layout.addWidget(self.input_field)

        btn_layout = QHBoxLayout()
        self.btn_send = QPushButton("发送")
        self.btn_send.clicked.connect(self._send)
        self.btn_new = QPushButton("新建对话")
        self.btn_new.clicked.connect(self._new_dialog)
        self.btn_save = QPushButton("保存样式")
        self.btn_save.clicked.connect(self._save_style)
        self.btn_save.setEnabled(False)
        btn_layout.addWidget(self.btn_send)
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_save)
        input_layout.addLayout(btn_layout)

        splitter.addWidget(input_widget)
        layout.addWidget(splitter)

        # 状态
        self.label_status = QLabel("点击「新建对话」开始")
        layout.addWidget(self.label_status)

        # 初始新建对话
        self._new_dialog()

    def _new_dialog(self):
        self.fsm = StyleDialogFSM(self.ollama)
        self.chat_history.clear()
        self.btn_save.setEnabled(False)
        self._append_message("系统", "开始新对话。")
        q = self.fsm.current_question
        if q:
            self._append_message("AI", q)
            self.label_status.setText("等待你的回答...")

    def _send(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        if self.fsm is None or self.fsm.finished:
            self._append_message("系统", "对话已完成，请点击「新建对话」重新开始。")
            return

        self._append_message("你", text)
        self.input_field.clear()

        self.label_status.setText("AI 思考中...")
        self.btn_send.setEnabled(False)

        # 提交用户输入
        result = self.fsm.submit(text)
        self._append_message("解析", str(result) if result else "（未识别）")

        # 下一个问题
        q = self.fsm.current_question
        if q:
            self._append_message("AI", q)
            self.label_status.setText("等待你的回答...")
        else:
            self._append_message("系统", "✅ 对话完成！你可以点击「保存样式」导出 YAML 文件。")
            self.btn_save.setEnabled(True)
            self.label_status.setText("对话完成，可以保存样式")

        self.btn_send.setEnabled(True)

    def _save_style(self):
        if self.fsm is None or not self.fsm.finished:
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存样式文件", "output/ai_style.yaml", "YAML 文件 (*.yaml)")
        if path:
            self.fsm.save_yaml(Path(path), "AI生成样式")
            self._append_message("系统", f"样式已保存到: {path}")
            QMessageBox.information(self, "已保存", f"样式文件已保存到:\n{path}")

    def _append_message(self, role: str, text: str):
        self.chat_history.append(f"<b>[{role}]</b> {text}")


class AboutTab(QWidget):
    """关于标签页"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("DocFormatX")
        title.setStyleSheet("font-size: 24pt; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "离线智能文档排版引擎\n\n"
            "Formatting as Conversation\n"
            "一次对话定义格式，永久复用，一键生成完美 Word 文档。\n\n"
            "完全离线 · 本地 AI 驱动 · 开源免费"
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        version = QLabel("版本 0.2.0")
        version.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(version)
        layout.addStretch()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 跨平台一致风格
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()