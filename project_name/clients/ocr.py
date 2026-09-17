from pathlib import Path


class OcrClient:
    def __init__(self, device: str = "auto"):
        # Deferred import: keeps paddleocr/torch/transformers optional (the "ocr" extra).
        from paddleocr import PaddleOCRVL

        # PaddleOCR's own Apple Silicon guidance: the layout-detection stage
        # runs via paddlepaddle, which has no Metal/MPS backend on macOS, so
        # "cpu" is what PaddleOCR itself recommends there; there is no "auto"
        # device the pipeline understands.
        pipeline_device = "cpu" if device == "auto" else device

        # Full two-stage pipeline (layout detection + per-region VLM OCR), not
        # the VLM called directly on the whole image: PaddleOCR's own docs warn
        # that VLM-only usage "potentially causes excessive hallucinated text" -
        # confirmed in practice (garbled/hallucinated output on a dense flyer).
        self.pipeline = PaddleOCRVL(engine="transformers", device=pipeline_device)

    def extract_text(self, image_path: Path) -> str:
        texts = []
        for res in self.pipeline.predict(str(image_path)):
            for block in res["parsing_res_list"]:
                if block.content:
                    texts.append(block.content)
        return "\n".join(texts).strip()
