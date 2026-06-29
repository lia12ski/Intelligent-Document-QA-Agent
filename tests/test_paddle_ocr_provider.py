from pathlib import Path
import sys
from types import SimpleNamespace

from docqa.ocr.paddle_ocr import PaddleOcrProvider, _configure_paddle_runtime


class FakePaddleOcrV3:
    def __init__(self) -> None:
        self.kwargs = None

    def ocr(self, image_path: str, **kwargs):
        self.kwargs = kwargs
        assert image_path == "page.png"
        assert "cls" not in kwargs
        return [
            {
                "rec_texts": ["你好", "世界"],
                "rec_scores": [0.91, 0.82],
                "rec_polys": [
                    [[0, 0], [10, 0], [10, 5], [0, 5]],
                    [[1, 10], [11, 10], [11, 15], [1, 15]],
                ],
            }
        ]


class FakePaddleOcrV2:
    def __init__(self) -> None:
        self.calls = []

    def ocr(self, image_path: str, **kwargs):
        self.calls.append(kwargs)
        assert image_path == "page.png"
        if "use_textline_orientation" in kwargs:
            raise TypeError("unexpected keyword argument 'use_textline_orientation'")
        return [
            [
                (
                    [[0, 0], [10, 0], [10, 5], [0, 5]],
                    ("旧版", 0.77),
                )
            ]
        ]


def test_paddle_ocr_provider_supports_paddleocr_v3_result_shape() -> None:
    provider = PaddleOcrProvider.__new__(PaddleOcrProvider)
    provider._ocr = FakePaddleOcrV3()

    blocks = provider.recognize(Path("page.png"), page_number=2)

    assert provider._ocr.kwargs == {"use_textline_orientation": True}
    assert [block.text for block in blocks] == ["你好", "世界"]
    assert blocks[0].page == 2
    assert blocks[0].bbox == [0.0, 0.0, 10.0, 5.0]
    assert blocks[0].confidence == 0.91
    assert blocks[0].source == "paddleocr"


def test_paddle_ocr_provider_falls_back_to_paddleocr_v2_cls_argument() -> None:
    provider = PaddleOcrProvider.__new__(PaddleOcrProvider)
    provider._ocr = FakePaddleOcrV2()

    blocks = provider.recognize(Path("page.png"), page_number=1)

    assert provider._ocr.calls == [
        {"use_textline_orientation": True},
        {"cls": True},
    ]
    assert len(blocks) == 1
    assert blocks[0].text == "旧版"
    assert blocks[0].confidence == 0.77


def test_configure_paddle_runtime_disables_pir_flags(monkeypatch) -> None:
    captured_flags = {}

    class FakeFramework:
        @staticmethod
        def set_flags(flags):
            captured_flags.update(flags)

    fake_paddle = SimpleNamespace(framework=FakeFramework())
    monkeypatch.setitem(sys.modules, "paddle", fake_paddle)
    monkeypatch.delenv("FLAGS_enable_pir_api", raising=False)
    monkeypatch.delenv("FLAGS_enable_pir_in_executor", raising=False)

    _configure_paddle_runtime()

    assert captured_flags == {
        "FLAGS_enable_pir_api": False,
        "FLAGS_enable_pir_in_executor": False,
    }
