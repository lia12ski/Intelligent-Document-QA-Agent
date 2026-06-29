from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docqa.agent.qa_agent import QaAgent
from docqa.agent.query_analyzer import QueryAnalyzerConfig
from docqa.config import load_settings
from docqa.llm.client import build_llm_client
from docqa.parsing.chunker import build_chunks
from docqa.parsing.factory import create_parser
from docqa.pdf.detector import PdfDetectionResult, detect_pdf
from docqa.retrieval.factory import build_retriever
from docqa.retrieval.manifest import (
    build_manifest,
    validate_manifest,
    validate_target_keywords,
    write_manifest,
)
from docqa.retrieval.store import load_chunks


def main() -> None:
    st.set_page_config(
        page_title="Intelligent Document QA Agent",
        layout="wide",
    )
    st.title("Intelligent Document QA Agent")
    st.caption(
        "AI Native 文档问答 Agent MVP：上传扫描版 PDF，完成解析、检索、引用问答与答案自检。"
    )

    settings = _render_sidebar(load_settings())

    uploaded_file = st.file_uploader("PDF 上传", type=["pdf"])
    if uploaded_file is not None:
        pdf_path = _save_uploaded_pdf(uploaded_file)
        st.session_state["uploaded_pdf_path"] = str(pdf_path)
        st.success(f"Uploaded: {pdf_path.name}")

    pdf_path = _current_pdf_path()
    if pdf_path is None:
        st.info("请上传 PDF 后开始检测和解析。")
    else:
        _render_pipeline_controls(pdf_path, settings)

    _render_qa_panel(settings)


def _render_sidebar(settings: Any) -> Any:
    with st.sidebar:
        st.header("Runtime")
        parser_options = ("local", "mineru")
        selected_parser = st.selectbox(
            "Parser provider",
            options=parser_options,
            index=parser_options.index(_default_streamlit_parser_provider(settings)),
            format_func=lambda value: (
                "MinerU (recommended for scanned PDFs)" if value == "mineru" else "Local"
            ),
            help=(
                "MinerU bypasses local PaddleOCR and is usually more stable for scanned PDFs, "
                "but it requires MINERU_API_KEY and network access."
            ),
        )
        if selected_parser == "mineru" and not settings.mineru_api_key:
            st.warning("MinerU requires MINERU_API_KEY in .env. Local parser remains available offline.")

        settings = replace(settings, parser_provider=selected_parser)
        st.write(
            {
                "parser_provider": settings.parser_provider,
                "ocr_provider": settings.ocr_provider,
                "llm_provider": settings.llm_provider,
                "dense_retrieval_enabled": settings.dense_retrieval_enabled,
                "dense_backend": settings.dense_backend,
            }
        )
        st.session_state["top_k"] = st.slider("Top K", 1, 10, 5)
        st.session_state["validate_target_keywords"] = st.checkbox(
            "执行目标关键词校验（仅财报样本/回归评估需要）",
            value=False,
            help=(
                "上传任意 PDF 做 Demo 时保持关闭。只有确认当前 PDF 应该包含 "
                ".env 里的 TARGET_DOCUMENT_KEYWORDS 时再开启。"
            ),
        )
        if settings.target_validation_enabled:
            st.caption("CLI 评估仍会按 .env 做目标文档校验；前端 Demo 默认关闭，方便测试任意 PDF。")
        st.session_state["parse_strategy_override"] = st.radio(
            "解析策略",
            options=("auto", "ocr"),
            format_func=lambda value: "自动检测" if value == "auto" else "强制 OCR",
            help=(
                "如果 PDF 检测为 text 但问答结果出现乱码，说明文本层编码可能损坏；"
                "切换到“强制 OCR”后重新点击 Parse & Build Index。"
            ),
        )

    return settings


def _default_streamlit_parser_provider(settings: Any) -> str:
    configured_provider = str(settings.parser_provider).lower().strip()
    if configured_provider == "mineru":
        return "mineru"
    if str(settings.mineru_api_key).strip():
        return "mineru"
    return "local"


def _render_pipeline_controls(pdf_path: Path, settings: Any) -> None:
    st.subheader("Document Pipeline")
    st.write(f"当前文件：`{pdf_path}`")

    detect_col, parse_col = st.columns(2)
    with detect_col:
        if st.button("Detect PDF", type="primary", use_container_width=True):
            try:
                detection = _run_detection(pdf_path, settings.processed_data_dir)
                st.session_state["detection"] = detection
                st.session_state["parse_summary"] = None
            except Exception as exc:
                st.error(f"PDF detection failed: {type(exc).__name__}: {exc}")

    with parse_col:
        if st.button("Parse & Build Index", use_container_width=True):
            try:
                detection = st.session_state.get("detection")
                if detection is None or detection.file_path != str(pdf_path):
                    detection = _run_detection(pdf_path, settings.processed_data_dir)
                    st.session_state["detection"] = detection
                st.session_state["parse_summary"] = _run_parse(
                    pdf_path=pdf_path,
                    settings=settings,
                    detection=detection,
                    strategy_override=str(st.session_state.get("parse_strategy_override", "auto")),
                )
            except Exception as exc:
                st.error(f"Parse/index build failed: {type(exc).__name__}: {exc}")

    detection = st.session_state.get("detection")
    if detection is not None:
        _render_detection(detection)

    parse_summary = st.session_state.get("parse_summary")
    if parse_summary:
        _render_parse_summary(parse_summary)


def _render_detection(detection: PdfDetectionResult) -> None:
    st.subheader("PDF 类型检测")
    cols = st.columns(5)
    cols[0].metric("PDF type", detection.pdf_type)
    cols[1].metric("Pages", detection.page_count)
    cols[2].metric("Text pages", detection.text_page_count)
    cols[3].metric("Scanned-like pages", detection.scanned_like_page_count)
    cols[4].metric("Strategy", detection.recommended_strategy)

    if detection.recommended_strategy == "reject":
        st.warning("Detector recommended rejecting this PDF.")
    if detection.reasons:
        st.write("Reasons:")
        st.write(detection.reasons)

    with st.expander("Detection JSON"):
        st.json(detection.to_dict())


def _render_parse_summary(summary: dict[str, Any]) -> None:
    st.subheader("解析结果")
    cols = st.columns(5)
    cols[0].metric("Page count", summary["page_count"])
    cols[1].metric("Chunk count", summary["chunk_count"])
    cols[2].metric("Table count", summary["table_count"])
    cols[3].metric("Parser", summary["parser_provider"])
    cols[4].metric("Strategy", summary["recommended_strategy"])

    if summary["warnings"]:
        st.warning("\n".join(summary["warnings"]))
    with st.expander("Generated files"):
        st.json(summary["outputs"])


def _render_qa_panel(settings: Any) -> None:
    st.subheader("Document QA")
    question = st.text_input("输入问题")
    ask_clicked = st.button("Ask", disabled=not question.strip())
    if not ask_clicked:
        return

    try:
        answer = _answer_question(
            question=question.strip(),
            settings=settings,
            top_k=int(st.session_state.get("top_k", 5)),
            validate_target=bool(st.session_state.get("validate_target_keywords", False)),
        )
    except RuntimeError as exc:
        _render_qa_runtime_error(str(exc))
        return
    except Exception as exc:
        st.error(f"Question answering failed: {type(exc).__name__}: {exc}")
        return

    answer_dict = answer.to_dict()
    st.markdown("### Answer")
    st.write(answer_dict["answer"])

    self_check = dict(answer_dict.get("self_check", {}))
    risk_flags = list(self_check.get("risk_flags") or [])
    if self_check.get("grounded") is False or risk_flags:
        st.warning(
            "Answer requires review: "
            f"grounded={self_check.get('grounded')}, risk_flags={risk_flags}"
        )

    meta_col, analysis_col = st.columns(2)
    with meta_col:
        st.markdown("### self_check")
        st.json(self_check)
    with analysis_col:
        st.markdown("### query_analysis")
        st.json(answer_dict.get("query_analysis", {}))

    sources = list(answer_dict.get("sources") or [])
    st.markdown("### Sources")
    if not sources:
        st.info("No source chunks returned.")
        return

    st.dataframe(
        [
            {
                "page": source.get("page"),
                "chunk_id": source.get("chunk_id"),
                "score": source.get("score"),
                "retrieval_source": source.get("retrieval_source"),
                "snippet": source.get("snippet"),
            }
            for source in sources
        ],
        use_container_width=True,
    )
    for source in sources:
        title = f"Page {source.get('page')} - {source.get('chunk_id')}"
        with st.expander(title):
            st.write(source.get("snippet", ""))
            st.json(source)


def _save_uploaded_pdf(uploaded_file: Any) -> Path:
    data = uploaded_file.getvalue()
    if not data:
        raise ValueError("Uploaded PDF is empty.")

    digest = hashlib.sha256(data).hexdigest()[:12]
    safe_name = _safe_pdf_name(uploaded_file.name)
    upload_dir = PROJECT_ROOT / "data" / "raw" / "streamlit_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_path = upload_dir / f"{digest}_{safe_name}"
    output_path.write_bytes(data)
    return output_path


def _safe_pdf_name(name: str) -> str:
    stem = Path(name).stem or "document"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    safe_stem = safe_stem or "document"
    return f"{safe_stem[:80]}.pdf"


def _current_pdf_path() -> Path | None:
    raw_path = st.session_state.get("uploaded_pdf_path")
    if not raw_path:
        return None
    path = Path(raw_path)
    return path if path.exists() else None


def _run_detection(pdf_path: Path, processed_dir: str) -> PdfDetectionResult:
    output_dir = Path(processed_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    detection = detect_pdf(pdf_path)
    _write_json(output_dir / "pdf_detection.json", detection.to_dict())
    return detection


def _run_parse(
    *,
    pdf_path: Path,
    settings: Any,
    detection: PdfDetectionResult,
    strategy_override: str = "auto",
) -> dict[str, Any]:
    if detection.recommended_strategy == "reject":
        raise RuntimeError("PDF cannot be parsed because detector recommended rejection.")

    output_dir = Path(settings.processed_data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    parser = create_parser(settings)
    parse_detection = _detection_for_parse(detection, strategy_override)
    parse_result, chunk_result = _parse_and_chunk(
        parser=parser,
        pdf_path=pdf_path,
        detection=parse_detection,
        output_dir=output_dir,
        settings=settings,
    )

    route_warnings: list[str] = []
    initial_quality_warnings = _text_quality_warnings(chunk_result.to_chunks_dict())
    if _should_retry_with_ocr(
        strategy_override=strategy_override,
        detection=detection,
        chunk_count=len(chunk_result.chunks),
        quality_warnings=initial_quality_warnings,
    ):
        route_warnings.append(
            "自动检测到文本层质量异常，已从 text 解析自动路由到 OCR。"
        )
        ocr_detection = _detection_for_parse(detection, "ocr")
        try:
            parse_result, chunk_result = _parse_and_chunk(
                parser=parser,
                pdf_path=pdf_path,
                detection=ocr_detection,
                output_dir=output_dir,
                settings=settings,
            )
            if not chunk_result.chunks:
                route_warnings.append(
                    "OCR 路由已执行，但没有产出可检索 chunks。"
                    "请检查 OCR provider，或切换 PARSER_PROVIDER=mineru。"
                )
        except Exception as exc:
            route_warnings.append(
                f"自动 OCR 路由失败：{type(exc).__name__}: {exc}。"
                "请切换 OCR_PROVIDER=tesseract 或 PARSER_PROVIDER=mineru 后重试。"
            )

    _write_json(output_dir / "pages.json", parse_result.to_dict())
    _write_json(output_dir / "chunks.json", chunk_result.to_chunks_dict())
    _write_json(output_dir / "tables.json", chunk_result.to_tables_dict())

    manifest = build_manifest(
        source_file=pdf_path,
        parser_provider=parse_result.parser_provider,
        strategy=parse_result.strategy,
        page_count=len(parse_result.pages),
        chunk_count=len(chunk_result.chunks),
        table_count=len(chunk_result.tables),
    )
    manifest_path = write_manifest(output_dir, manifest)
    warnings = [*route_warnings, *parse_result.warnings, *chunk_result.warnings]
    warnings.extend(_runtime_guidance_warnings(warnings))
    warnings.extend(_text_quality_warnings(chunk_result.to_chunks_dict()))

    return {
        "page_count": len(parse_result.pages),
        "chunk_count": len(chunk_result.chunks),
        "table_count": len(chunk_result.tables),
        "parser_provider": parse_result.parser_provider,
        "recommended_strategy": parse_result.strategy,
        "warnings": warnings,
        "outputs": {
            "pdf_detection": str(output_dir / "pdf_detection.json"),
            "pages": str(output_dir / "pages.json"),
            "chunks": str(output_dir / "chunks.json"),
            "tables": str(output_dir / "tables.json"),
            "manifest": str(manifest_path),
        },
    }


def _parse_and_chunk(
    *,
    parser: Any,
    pdf_path: Path,
    detection: PdfDetectionResult,
    output_dir: Path,
    settings: Any,
) -> tuple[Any, Any]:
    parse_result = parser.parse(pdf_path, detection, output_dir)
    chunk_result = build_chunks(
        parse_result,
        inline_table_keywords=settings.inline_table_keywords,
    )
    return parse_result, chunk_result


def _detection_for_parse(
    detection: PdfDetectionResult,
    strategy_override: str,
) -> PdfDetectionResult:
    if strategy_override != "ocr":
        return detection
    if detection.recommended_strategy == "ocr":
        return detection
    return replace(
        detection,
        recommended_strategy="ocr",
        reasons=[
            *detection.reasons,
            "user forced OCR in Streamlit demo",
        ],
    )


def _should_retry_with_ocr(
    *,
    strategy_override: str,
    detection: PdfDetectionResult,
    chunk_count: int,
    quality_warnings: list[str],
) -> bool:
    return (
        strategy_override == "auto"
        and detection.recommended_strategy == "text"
        and (chunk_count == 0 or bool(quality_warnings))
    )


def _runtime_guidance_warnings(warnings: list[str]) -> list[str]:
    joined = "\n".join(warnings)
    if "ConvertPirAttribute2RuntimeAttribute" in joined or "onednn_instruction" in joined:
        return [
            "检测到 PaddleOCR / PaddlePaddle 的 PIR oneDNN 运行时错误。"
            "请重启 Streamlit 后再试；代码已默认关闭 FLAGS_enable_pir_api 和 "
            "FLAGS_enable_pir_in_executor。"
            "如果仍失败，请切换 OCR_PROVIDER=tesseract 或 PARSER_PROVIDER=mineru。"
        ]
    if "MuPDF error" in joined or "incorrect header check" in joined:
        return [
            "检测到 MuPDF PDF 流解压错误，通常表示该 PDF 内部对象损坏或格式不标准。"
            "如 OCR 渲染失败，请换用重新导出的 PDF 或 MinerU provider。"
        ]
    return []


def _text_quality_warnings(chunks_data: dict[str, Any]) -> list[str]:
    chunks = chunks_data.get("chunks", [])
    text = "\n".join(str(chunk.get("text", "")) for chunk in chunks)
    if not text.strip():
        return ["解析结果没有可用文本，请尝试 OCR 或 MinerU 解析。"]

    suspicious_scripts = {
        script
        for char in text
        if (script := _suspicious_script_family(char))
    }
    suspicious_count = sum(1 for char in text if _suspicious_script_family(char))
    useful_count = sum(1 for char in text if not char.isspace())
    suspicious_ratio = suspicious_count / useful_count if useful_count else 0.0
    if suspicious_ratio >= 0.25 or (suspicious_ratio >= 0.15 and len(suspicious_scripts) >= 4):
        return [
            "解析出的文本疑似乱码。当前 PDF 虽然有文本层，但文本层编码可能损坏；"
            "请在左侧“解析策略”选择“强制 OCR”，然后重新点击 Parse & Build Index。"
            "如果 OCR 效果仍不好，可改用 MinerU provider。"
        ]
    return []


def _suspicious_script_family(char: str) -> str:
    if char.isascii() or char.isspace():
        return ""
    codepoint = ord(char)
    if 0x4E00 <= codepoint <= 0x9FFF:
        return ""
    if 0x3000 <= codepoint <= 0x303F:
        return ""
    name = unicodedata.name(char, "")
    if not name:
        return "UNKNOWN"
    family = name.split()[0]
    if family in {"LATIN", "CJK", "IDEOGRAPHIC", "FULLWIDTH", "HALFWIDTH"}:
        return ""
    if family in {"HIRAGANA", "KATAKANA", "HANGUL"}:
        return family
    if family in {
        "ARABIC",
        "ARMENIAN",
        "BALINESE",
        "CANADIAN",
        "COMBINING",
        "CYRILLIC",
        "DEVANAGARI",
        "ETHIOPIC",
        "GEORGIAN",
        "GURMUKHI",
        "KHMER",
        "MYANMAR",
        "NEW",
        "ORIYA",
        "RUNIC",
        "SINHALA",
        "SYRIAC",
        "THAI",
        "TIBETAN",
    }:
        return family
    return ""


def _answer_question(
    *,
    question: str,
    settings: Any,
    top_k: int,
    validate_target: bool,
) -> Any:
    processed_dir = Path(settings.processed_data_dir)
    chunks_path = processed_dir / "chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunk index not found: {chunks_path}")

    validation = validate_manifest(
        processed_dir,
        require_manifest=settings.require_index_manifest,
    )
    if not validation.ok:
        raise RuntimeError(validation.message)

    if validate_target:
        target_validation = validate_target_keywords(
            chunks_path,
            settings.target_document_keywords,
        )
        if not target_validation.ok:
            raise RuntimeError(target_validation.message)

    chunks = load_chunks(chunks_path)
    retriever = build_retriever(chunks, settings)
    agent = QaAgent(
        retriever,
        min_score=settings.retrieval_min_score,
        llm_client=build_llm_client(settings),
        focus_terms=settings.domain_focus_terms,
        query_config=QueryAnalyzerConfig(
            table_terms=settings.query_table_terms,
            numeric_terms=settings.query_numeric_terms,
            definition_terms=settings.query_definition_terms,
            generic_phrases=settings.query_generic_phrases,
            ocr_replacements=settings.query_ocr_replacements,
            generic_amount_expansion=settings.generic_amount_expansion,
        ),
        dense_min_score=settings.dense_min_score,
        all_chunks=chunks,
    )
    return agent.answer(question, top_k=top_k)


def _render_qa_runtime_error(message: str) -> None:
    if "indexed document does not match expected target keywords" in message:
        st.warning(
            "当前 PDF 没有命中默认财报样本关键词。"
            "如果你是在演示或测试任意 PDF，请关闭左侧的“执行目标关键词校验”后重新点击 Ask；"
            "如果你确实要验证财报样本文档，请重新上传正确 PDF 并重新解析。"
        )
        with st.expander("原始错误"):
            st.code(message)
        return

    st.error(f"Question answering failed: RuntimeError: {message}")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
