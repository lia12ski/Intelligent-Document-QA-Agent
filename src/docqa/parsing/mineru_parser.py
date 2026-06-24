from __future__ import annotations

import json
from pathlib import Path
import time
import zipfile

from docqa.config import Settings
from docqa.pdf.detector import PdfDetectionResult
from docqa.parsing.base import DocumentParser
from docqa.parsing.mineru_normalizer import pages_from_mineru_content_list
from docqa.parsing.schema import ParseResult


class MineruParser(DocumentParser):
    provider_name = "mineru"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def parse(
        self,
        pdf_path: str | Path,
        detection: PdfDetectionResult,
        output_dir: str | Path,
    ) -> ParseResult:
        _ = detection
        if not self._settings.mineru_api_key:
            raise RuntimeError(
                "PARSER_PROVIDER=mineru requires MINERU_API_KEY. "
                "Use PARSER_PROVIDER=local for offline parsing."
            )
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("MinerU parser requires requests. Install requirements.txt.") from exc

        pdf = Path(pdf_path)
        mineru_dir = Path(output_dir) / "mineru"
        mineru_dir.mkdir(parents=True, exist_ok=True)

        base_url = self._settings.mineru_base_url.rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.mineru_api_key}",
        }
        data_id = pdf.stem.replace(" ", "_")[:120]
        payload = {
            "files": [
                {
                    "name": pdf.name,
                    "data_id": data_id,
                    "is_ocr": True,
                }
            ],
            "model_version": self._settings.mineru_model_version,
            "enable_table": True,
            "enable_formula": True,
            "language": "ch",
        }

        submit_response = requests.post(
            f"{base_url}/api/v4/file-urls/batch",
            headers=headers,
            json=payload,
            timeout=30,
        )
        submit_response.raise_for_status()
        submit_result = submit_response.json()
        _ensure_success(submit_result, "apply MinerU upload URL")
        batch_id = submit_result["data"]["batch_id"]
        file_url = submit_result["data"]["file_urls"][0]

        with pdf.open("rb") as file_obj:
            upload_response = requests.put(file_url, data=file_obj, timeout=120)
        upload_response.raise_for_status()

        extract_result = self._poll_result(requests, base_url, headers, batch_id)
        zip_url = extract_result.get("full_zip_url")
        if not zip_url:
            raise RuntimeError(f"MinerU result does not include full_zip_url: {extract_result}")

        zip_path = mineru_dir / "mineru_result.zip"
        zip_response = requests.get(zip_url, timeout=120)
        zip_response.raise_for_status()
        zip_path.write_bytes(zip_response.content)

        extract_dir = mineru_dir / "result"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        markdown_text = _read_first_text(extract_dir, "full.md")
        content_list = _read_first_json_list(extract_dir, "_content_list.json")
        pages = pages_from_mineru_content_list(content_list, markdown_text)

        return ParseResult(
            source_file=str(pdf),
            parser_provider=self.provider_name,
            strategy="mineru",
            pages=pages,
            warnings=[
                f"MinerU batch_id={batch_id}",
                f"MinerU result extracted to {extract_dir}",
            ],
        )

    def _poll_result(self, requests_module, base_url: str, headers: dict[str, str], batch_id: str) -> dict:
        deadline = time.time() + self._settings.mineru_max_wait_seconds
        last_result: dict | None = None
        while time.time() < deadline:
            response = requests_module.get(
                f"{base_url}/api/v4/extract-results/batch/{batch_id}",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            _ensure_success(result, "poll MinerU result")
            extract_results = result.get("data", {}).get("extract_result", [])
            if extract_results:
                last_result = extract_results[0]
                state = last_result.get("state")
                if state == "done":
                    return last_result
                if state == "failed":
                    raise RuntimeError(f"MinerU parse failed: {last_result.get('err_msg')}")
            time.sleep(self._settings.mineru_poll_interval_seconds)

        raise TimeoutError(f"MinerU parse timed out. Last result: {last_result}")


def _ensure_success(result: dict, action: str) -> None:
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to {action}: {result.get('msg') or result}")


def _read_first_text(root: Path, filename: str) -> str:
    matches = list(root.rglob(filename))
    if not matches:
        return ""
    return matches[0].read_text(encoding="utf-8", errors="replace")


def _read_first_json_list(root: Path, suffix: str) -> list[dict]:
    matches = [path for path in root.rglob("*") if path.name.endswith(suffix)]
    if not matches:
        return []
    data = json.loads(matches[0].read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []
