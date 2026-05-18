"""
Ollama 管理器 - 封装本地 AI 对话接口。
稳健解析由 robust_json 模块处理。
"""
import subprocess
import logging
import sys
import time

from .robust_json import safe_parse_json

log = logging.getLogger(__name__)

SIZE_MAP = {
    "初号": 42, "小初": 36, "一号": 26, "小一": 24,
    "二号": 22, "小二": 18, "三号": 16, "小三": 15,
    "四号": 14, "小四": 12, "五号": 10.5, "小五": 9,
}

FONT_FIX = {
    "黑色": "黑体", "楷书": "楷体", "仿宋体": "仿宋",
    "宋体字": "宋体", "times new roman": "Times New Roman",
}


class OllamaManager:
    def __init__(self, model="qwen2.5:7b"):
        self.model = model
        self._proc = None

    # ── 公开接口 ─────────────────────────────────
    def chat(self, system_prompt, user_prompt):
        """发送对话请求，返回模型原始输出"""
        if not self._is_running():
            self._start()
        try:
            result = subprocess.run(
                [
                    "ollama", "run", self.model,
                    "--format", "json",          # 源头约束
                    f"{system_prompt}\n\n{user_prompt}",
                ],
                capture_output=True, text=True, encoding="utf-8", timeout=120,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            log.error("Ollama 请求超时")
            return ""
        except Exception as e:
            log.error(f"Ollama 请求失败: {e}")
            return ""

    def structured_chat(self, system_prompt, user_prompt):
        """返回字典，已清洗并修复常见 AI 错误"""
        raw = self.chat(system_prompt, user_prompt)
        if not raw:
            return {}
        data = self._safe_json_parse(raw)
        if not data:
            log.warning("JSON 解析失败，返回空字典。原始输出: %s", raw[:200])
            return {}
        return self._fix_ai_errors(data)

    # ── JSON 解析（委托给 robust_json）───────────
    def _safe_json_parse(self, raw: str) -> dict:
        try:
            result = safe_parse_json(raw)
            if isinstance(result, dict):
                return result
            return {}
        except ValueError as e:
            log.warning("安全 JSON 解析失败: %s", e)
            return {}

    # ── AI 常见错误修正 ──────────────────────────
    def _fix_ai_errors(self, data: dict) -> dict:
        fixed = {}
        for key, value in data.items():
            if isinstance(value, dict):
                fixed[key] = {}
                for k, v in value.items():
                    if k == "font_name" and isinstance(v, str):
                        v_lower = v.lower().strip()
                        fixed[key][k] = FONT_FIX.get(v, FONT_FIX.get(v_lower, v))
                    elif k == "size_pt" and isinstance(v, str):
                        v_clean = v.replace("号", "").strip()
                        if v_clean in SIZE_MAP:
                            fixed[key][k] = SIZE_MAP[v_clean]
                        else:
                            try:
                                fixed[key][k] = float(v_clean)
                            except ValueError:
                                fixed[key][k] = v
                    else:
                        fixed[key][k] = v
            else:
                fixed[key] = value
        return fixed

    # ── Ollama 服务管理 ──────────────────────────
    def _is_running(self):
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _start(self):
        log.info("正在启动 Ollama 服务...")
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self._proc = subprocess.Popen(["ollama", "serve"], **kwargs)
        for _ in range(30):
            if self._is_running():
                log.info("Ollama 服务已就绪")
                return
            time.sleep(1)
        raise RuntimeError("Ollama 启动超时")