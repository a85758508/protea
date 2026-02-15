"""PDF utilities — Chinese-friendly PDF generation from Markdown.

Uses reportlab for PDF rendering and markdown2 for Markdown parsing.
Automatically registers CJK fonts from macOS/Linux system paths.
"""

from __future__ import annotations

import logging
import pathlib
import re
from html.parser import HTMLParser

log = logging.getLogger("protea.pdf_utils")

# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------

_FONT_CANDIDATES: list[tuple[str, str, int | None]] = [
    # (label, path, subfontIndex or None)
    ("PingFang SC", "/System/Library/Fonts/PingFang.ttc", 2),
    ("STHeiti Medium", "/System/Library/Fonts/STHeiti Medium.ttc", None),
    ("Songti SC", "/System/Library/Fonts/Songti.ttc", 0),
    ("Arial Unicode", "/Library/Fonts/Arial Unicode.ttf", None),
    # Linux common paths
    ("Noto Sans CJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("WenQuanYi Micro Hei", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
]

_CJK_FONT_NAME: str | None = None


def _ensure_font() -> str:
    """Register a CJK font and return its name.  Falls back to Helvetica."""
    global _CJK_FONT_NAME
    if _CJK_FONT_NAME is not None:
        return _CJK_FONT_NAME

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for label, path, sub in _FONT_CANDIDATES:
        if not pathlib.Path(path).exists():
            continue
        try:
            kwargs = {"subfontIndex": sub} if sub is not None else {}
            pdfmetrics.registerFont(TTFont("CJKFont", path, **kwargs))
            _CJK_FONT_NAME = "CJKFont"
            log.info("Registered CJK font: %s (%s)", label, path)
            return _CJK_FONT_NAME
        except Exception as exc:
            log.debug("Font %s failed: %s", label, exc)

    log.warning("No CJK font found — falling back to Helvetica")
    _CJK_FONT_NAME = "Helvetica"
    return _CJK_FONT_NAME


# ---------------------------------------------------------------------------
# Simple HTML → reportlab flowable converter
# ---------------------------------------------------------------------------

class _HTMLToFlowables(HTMLParser):
    """Parse simple HTML (from markdown2) into reportlab Paragraph text.

    This does NOT build a full DOM — it converts tags into reportlab's
    XML-like markup that Paragraph understands (<b>, <i>, <br/>, etc.)
    and splits on block boundaries to produce separate flowables.
    """

    _BLOCK_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6",
                              "li", "tr", "blockquote", "pre", "hr"})

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, str]] = []  # (tag, content)
        self._tag_stack: list[str] = []
        self._current_tag = "p"
        self._buf: list[str] = []

    def _flush(self) -> None:
        text = "".join(self._buf).strip()
        if text:
            self.blocks.append((self._current_tag, text))
        self._buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCK_TAGS:
            self._flush()
            self._current_tag = tag
        elif tag == "strong" or tag == "b":
            self._buf.append("<b>")
        elif tag == "em" or tag == "i":
            self._buf.append("<i>")
        elif tag == "br":
            self._buf.append("<br/>")
        elif tag == "code":
            self._buf.append("<font face='Courier'>")
        elif tag == "a":
            self._buf.append("<u>")
        elif tag == "ul" or tag == "ol":
            self._flush()
        elif tag == "table":
            self._flush()
        elif tag == "th" or tag == "td":
            self._buf.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self._flush()
            self._current_tag = "p"
        elif tag == "strong" or tag == "b":
            self._buf.append("</b>")
        elif tag == "em" or tag == "i":
            self._buf.append("</i>")
        elif tag == "code":
            self._buf.append("</font>")
        elif tag == "a":
            self._buf.append("</u>")

    def handle_data(self, data: str) -> None:
        # Escape XML special chars for reportlab Paragraph
        text = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._buf.append(text)

    def close(self) -> None:
        self._flush()
        super().close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def markdown_to_pdf(md_path: str | pathlib.Path, pdf_path: str | pathlib.Path) -> str:
    """Convert a Markdown file to PDF with CJK font support.

    Args:
        md_path: Path to input .md file.
        pdf_path: Path for output .pdf file.

    Returns:
        Absolute path of the generated PDF, or an error string starting
        with "Error:".
    """
    md_path = pathlib.Path(md_path)
    pdf_path = pathlib.Path(pdf_path)

    if not md_path.is_file():
        return f"Error: markdown file not found: {md_path}"

    try:
        import markdown2
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
        )
    except ImportError as exc:
        return f"Error: missing dependency: {exc}"

    font_name = _ensure_font()

    # Read and convert markdown
    md_text = md_path.read_text(encoding="utf-8")
    html = markdown2.markdown(md_text, extras=["tables", "fenced-code-blocks",
                                                "header-ids", "strike"])

    # Parse HTML into blocks
    parser = _HTMLToFlowables()
    parser.feed(html)
    parser.close()

    # Build styles
    styles = getSampleStyleSheet()

    style_body = ParagraphStyle(
        "CJKBody", parent=styles["BodyText"],
        fontName=font_name, fontSize=10, leading=16, alignment=TA_LEFT,
        spaceBefore=4, spaceAfter=4,
    )
    style_h1 = ParagraphStyle(
        "CJKH1", parent=styles["Heading1"],
        fontName=font_name, fontSize=22, leading=28,
        textColor=colors.HexColor("#2C3E50"),
        spaceAfter=16, spaceBefore=20, alignment=TA_CENTER,
    )
    style_h2 = ParagraphStyle(
        "CJKH2", parent=styles["Heading2"],
        fontName=font_name, fontSize=16, leading=22,
        textColor=colors.HexColor("#34495E"),
        spaceAfter=10, spaceBefore=16,
    )
    style_h3 = ParagraphStyle(
        "CJKH3", parent=styles["Heading3"],
        fontName=font_name, fontSize=13, leading=18,
        textColor=colors.HexColor("#5D6D7E"),
        spaceAfter=8, spaceBefore=12,
    )
    style_li = ParagraphStyle(
        "CJKListItem", parent=style_body,
        leftIndent=20, bulletIndent=10,
        spaceBefore=2, spaceAfter=2,
    )
    style_pre = ParagraphStyle(
        "CJKPre", parent=style_body,
        fontName="Courier", fontSize=9, leading=12,
        leftIndent=15, backColor=colors.HexColor("#F5F5F5"),
        spaceBefore=6, spaceAfter=6,
    )

    tag_style_map = {
        "h1": style_h1,
        "h2": style_h2,
        "h3": style_h3,
        "h4": style_h3,
        "h5": style_h3,
        "h6": style_h3,
        "li": style_li,
        "pre": style_pre,
        "p": style_body,
        "blockquote": style_body,
        "tr": style_body,
    }

    # Build story
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    story: list = []

    for tag, content in parser.blocks:
        style = tag_style_map.get(tag, style_body)
        if tag == "li":
            content = "\u2022 " + content
        if tag == "hr":
            story.append(Spacer(1, 0.5 * cm))
            continue
        try:
            story.append(Paragraph(content, style))
        except Exception:
            # If reportlab can't parse the markup, strip tags and retry
            clean = re.sub(r"<[^>]+>", "", content)
            try:
                story.append(Paragraph(clean, style))
            except Exception:
                story.append(Paragraph(clean[:200], style_body))

    if not story:
        story.append(Paragraph("(empty document)", style_body))

    try:
        doc.build(story)
    except Exception as exc:
        return f"Error: PDF build failed: {exc}"

    return str(pdf_path.resolve())
