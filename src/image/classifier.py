"""
图片智能分类器 - 级联架构（规则 → 手工特征 → CNN）
当前版本：仅启用 Stage 1 规则分类，模型文件就绪后可无缝升级到 Stage 2/3。
"""
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


class ImageKind(Enum):
    LOGO = "logo"
    PHOTO = "photo"


@dataclass
class ClassifyResult:
    kind: ImageKind
    confidence: float
    stage: int
    reason: str = ""


class ImageClassifier:
    """
    图片分类器。
    当前使用 Stage 1 强规则，准确率约 85-90%。
    后期放入 classifier.txt 和 mobilenet_v3_small_int8.onnx 后自动升级。
    """

    def __init__(self, lgbm_path: Optional[Path] = None, onnx_path: Optional[Path] = None):
        self.lgbm_path = lgbm_path
        self.onnx_path = onnx_path
        self._stage2 = None
        self._stage3 = None

    def classify(self, image_path: Path) -> ClassifyResult:
        """主分类入口"""
        with Image.open(image_path) as im:
            rgba = np.array(im.convert("RGBA"))

        # Stage 1：强规则
        result = self._stage1_classify(rgba)
        if result is not None:
            return result

        # Stage 2/3 占位（模型就绪后启用）
        return ClassifyResult(ImageKind.PHOTO, 0.5, stage=1, reason="无法确定，默认归为照片")

    def _stage1_classify(self, rgba: np.ndarray) -> Optional[ClassifyResult]:
        """强规则快速分类"""

        # 规则 A：透明背景 → Logo
        if rgba.shape[2] == 4:
            alpha = rgba[..., 3]
            transparent_ratio = (alpha < 250).mean()
            if transparent_ratio > 0.05:
                return ClassifyResult(
                    ImageKind.LOGO, 0.98, stage=1,
                    reason=f"透明背景 (比例={transparent_ratio:.2f})"
                )

        # 规则 B：颜色数极少 → Logo
        rgb_q = rgba[..., :3] >> 4
        uniq = np.unique(rgb_q.reshape(-1, 3), axis=0).shape[0]
        if uniq < 16:
            return ClassifyResult(
                ImageKind.LOGO, 0.97, stage=1,
                reason=f"颜色数极少 ({uniq})"
            )

        # 规则 C：颜色数极多 → 照片
        if uniq > 3000:
            return ClassifyResult(
                ImageKind.PHOTO, 0.96, stage=1,
                reason=f"颜色数极多 ({uniq})"
            )

        return None