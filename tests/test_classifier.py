"""图片分类器测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from image.classifier import ImageClassifier, ImageKind
import numpy as np
from PIL import Image


def test_logo_detection(tmp_path):
    """测试：透明背景图应识别为 Logo"""
    classifier = ImageClassifier()

    # 创建模拟 Logo：红色方块 + 透明背景
    logo_path = tmp_path / "logo.png"
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (50, 50, 150, 150))
    img.save(logo_path)

    result = classifier.classify(logo_path)
    assert result.kind == ImageKind.LOGO, f"预期 LOGO，实际 {result.kind}"
    assert result.stage == 1
    print(f"✅ Logo 检测通过: {result}")


def test_photo_detection(tmp_path):
    """测试：随机噪点图应识别为照片"""
    classifier = ImageClassifier()

    # 创建模拟照片：RGB 随机噪点
    photo_path = tmp_path / "photo.jpg"
    noise = np.random.randint(0, 255, (400, 400, 3), dtype=np.uint8)
    Image.fromarray(noise).save(photo_path)

    result = classifier.classify(photo_path)
    # 噪点图颜色数通常 > 3000，应判为照片
    assert result.kind == ImageKind.PHOTO, f"预期 PHOTO，实际 {result.kind}"
    print(f"✅ 照片检测通过: {result}")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_logo_detection(Path(tmp))
        test_photo_detection(Path(tmp))
    print("🎉 所有测试通过！")