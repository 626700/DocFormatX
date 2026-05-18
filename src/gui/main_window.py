"""
DocFormatX 主窗口 - PySide6 GUI
支持文件拖拽、渲染进度条、样式对话、最近文件记忆。
"""
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFileDialog, QMessageBox, QProgressBar,
    QLineEdit, QGroupBox, QFormLayout, QSplitter, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QSettings

# 导入核心模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.renderer import render
from core.style_dialog import StyleDialogFSM
from utils.ollama_manager import OllamaManager

CONFIG_FILE = Path(__file__).parent.parent.parent / "config.json"


class RenderWorker(QThread):
    """后台渲染线程"""
    progress = Signal(int, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, style_path, content_path, output_path):
        super().__init__()
        self.style_path = style_path
        self.content_path = content_path
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit(20, "正在生成文档...")
            render(Path(self.style_path), Path(self.content_path), Path(self.output_path))
            self.progress.emit(100, "完成")
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocFormatX - 离线智能文档排版引擎")
        self.setMinimumSize(820, 620)
        self.settings = QSettings("DocFormatX", "GUI")

        self.ollama = OllamaManager()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_render = RenderTab(self.settings)
        self.tab_dialog = StyleDialogTab(self.ollama)
        self.tab_about = AboutTab()

        self.tabs.addTab(self.tab_render, "📄 渲染文档")
        self.tabs.addTab(self.tab_dialog, "🤖 对话生成样式")
        self.tabs.addTab(self.tab_about, "ℹ️ 关于")


class RenderTab(QWidget):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.settings = settings
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)

        # ── 样式文件 ──
        g1 = QGroupBox("1. 样式文件 (.yaml)")
        f1 = QFormLayout()
        self.edit_style = QLineEdit()
        self.edit_style.setPlaceholderText("拖拽 YAML 文件到窗口，或点击浏览...")
        btn_style = QPushButton("浏览...")
        btn_style.clicked.connect(lambda: self._browse("yaml", self.edit_style))
        row = QHBoxLayout(); row.addWidget(self.edit_style); row.addWidget(btn_style)
        f1.addRow(row)

        # 最近使用的样式
        self.combo_style = QComboBox()
        self.combo_style.addItem("（历史记录）")
        self._load_recent("recent_styles", self.combo_style)
        self.combo_style.currentTextChanged.connect(lambda t: self._on_recent(t, self.edit_style))
        f1.addRow("最近:", self.combo_style)
        g1.setLayout(f1)
        layout.addWidget(g1)

        # ── 内容文件 ──
        g2 = QGroupBox("2. 内容文件 (.txt)")
        f2 = QFormLayout()
        self.edit_content = QLineEdit()
        self.edit_content.setPlaceholderText("拖拽 TXT 文件到窗口，或点击浏览...")
        btn_content = QPushButton("浏览...")
        btn_content.clicked.connect(lambda: self._browse("txt", self.edit_content))
        row2 = QHBoxLayout(); row2.addWidget(self.edit_content); row2.addWidget(btn_content)
        f2.addRow(row2)

        self.combo_content = QComboBox()
        self.combo_content.addItem("（历史记录）")
        self._load_recent("recent_contents", self.combo_content)
        self.combo_content.currentTextChanged.connect(lambda t: self._on_recent(t, self.edit_content))
        f2.addRow("最近:", self.combo_content)
        g2.setLayout(f2)
        layout.addWidget(g2)

        # ── 输出 ──
        g3 = QGroupBox("3. 输出文件")
        f3 = QFormLayout()
        self.edit_output = QLineEdit("output/document.docx")
        btn_output = QPushButton("选择...")
        btn_output.clicked.connect(self._browse_output)
        row3 = QHBoxLayout(); row3.addWidget(self.edit_output); row3.addWidget(btn_output)
        f3.addRow(row3)
        g3.setLayout(f3)
        layout.addWidget(g3)

        # ── 生成按钮 ──
        self.btn_render = QPushButton("🚀 生成 Word 文档")
        self.btn_render.setMinimumHeight(42)
        self.btn_render.clicked.connect(self._render)
        layout.addWidget(self.btn_render)

        # ── 进度条 ──
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.label_status = QLabel("就绪 — 可以直接拖拽文件到窗口")
        layout.addWidget(self.label_status)
        layout.addStretch()

        # 启动时恢复上次路径
        last_style = self.settings.value("last_style", "")
        last_content = self.settings.value("last_content", "")
        if last_style:
            self.edit_style.setText(last_style)
        if last_content:
            self.edit_content.setText(last_content)

    # ── 浏览 ──
    def _browse(self, kind, edit):
        if kind == "yaml":
            path, _ = QFileDialog.getOpenFileName(self, "选择样式文件", "", "YAML (*.yaml *.yml)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择内容文件", "", "文本 (*.txt)")
        if path:
            edit.setText(path)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 Word 文档", "output/document.docx", "Word (*.docx)")
        if path:
            self.edit_output.setText(path)

    # ── 历史记录 ──
    def _load_recent(self, key, combo):
        items = self.settings.value(key, [])
        if isinstance(items, str):
            items = json.loads(items)
        if items:
            combo.addItems(items)

    def _on_recent(self, text, edit):
        if text and text != "（历史记录）":
            edit.setText(text)

    # ── 拖拽 ──
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.endswith(('.yaml', '.yml')):
                self.edit_style.setText(path)
            elif path.endswith('.txt'):
                self.edit_content.setText(path)

    # ── 渲染 ──
    def _render(self):
        sp = self.edit_style.text().strip()
        cp = self.edit_content.text().strip()
        op = self.edit_output.text().strip()

        if not sp or not cp:
            QMessageBox.warning(self, "缺少文件", "请选择样式文件和内容文件。")
            return

        # 记忆路径
        self.settings.setValue("last_style", sp)
        self.settings.setValue("last_content", cp)
        self._add_recent("recent_styles", sp, self.combo_style)
        self._add_recent("recent_contents", cp, self.combo_content)

        self.btn_render.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(5)
        self.label_status.setText("⏳ 正在生成文档...")

        self.worker = RenderWorker(sp, cp, op)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _add_recent(self, key, value, combo):
        items = self.settings.value(key, [])
        if isinstance(items, str):
            items = json.loads(items)
        if value in items:
            items.remove(value)
        items.insert(0, value)
        items = items[:8]
        self.settings.setValue(key, json.dumps(items))
        combo.clear()
        combo.addItem("（历史记录）")
        combo.addItems(items)

    def _on_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.label_status.setText(f"⏳ {msg} ({pct}%)")

    def _on_finished(self, path):
        self.progress.setValue(100)
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
        self.fsm = None

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        splitter.addWidget(self.chat_history)

        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(70)
        self.input_field.setPlaceholderText("在此输入你的回答...")
        input_layout.addWidget(self.input_field)

        btn_row = QHBoxLayout()
        self.btn_send = QPushButton("发送")
        self.btn_send.clicked.connect(self._send)
        self.btn_new = QPushButton("新建对话")
        self.btn_new.clicked.connect(self._new_dialog)
        self.btn_save = QPushButton("保存样式")
        self.btn_save.clicked.connect(self._save_style)
        self.btn_save.setEnabled(False)
        btn_row.addWidget(self.btn_send)
        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_save)
        input_layout.addLayout(btn_row)

        splitter.addWidget(input_widget)
        layout.addWidget(splitter)

        self.label_status = QLabel("点击「新建对话」开始")
        layout.addWidget(self.label_status)

        self._new_dialog()

    def _new_dialog(self):
        self.fsm = StyleDialogFSM(self.ollama)
        self.chat_history.clear()
        self.btn_save.setEnabled(False)
        self._append("系统", "开始新对话。")
        q = self.fsm.current_question
        if q:
            self._append("AI", q)
            self.label_status.setText("等待你的回答...")

    def _send(self):
        text = self.input_field.toPlainText().strip()
        if not text or self.fsm is None or self.fsm.finished:
            return
        self._append("你", text)
        self.input_field.clear()
        self.label_status.setText("AI 思考中...")
        self.btn_send.setEnabled(False)

        result = self.fsm.submit(text)
        self._append("解析", str(result) if result else "（未识别）")

        q = self.fsm.current_question
        if q:
            self._append("AI", q)
            self.label_status.setText("等待你的回答...")
        else:
            self._append("系统", "✅ 对话完成！点击「保存样式」导出。")
            self.btn_save.setEnabled(True)
            self.label_status.setText("对话完成")
        self.btn_send.setEnabled(True)

    def _save_style(self):
        if not self.fsm or not self.fsm.finished:
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存样式", "output/ai_style.yaml", "YAML (*.yaml)")
        if path:
            self.fsm.save_yaml(Path(path), "AI生成样式")
            self._append("系统", f"已保存: {path}")
            QMessageBox.information(self, "已保存", f"样式文件已保存到:\n{path}")

    def _append(self, role, text):
        self.chat_history.append(f"<b>[{role}]</b> {text}")


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("DocFormatX")
        title.setStyleSheet("font-size: 24pt; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "离线智能文档排版引擎\n\n"
            "Formatting as Conversation\n"
            "一次对话定义格式，永久复用，一键生成完美 Word 文档。\n\n"
            "完全离线 · 本地 AI 驱动 · 开源免费"
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        version = QLabel("版本 0.2.1")
        version.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(version)
        layout.addStretch()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()