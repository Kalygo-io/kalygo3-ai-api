"""
PDF processing utilities for LLM input.

Two modes:
1. IMAGE MODE (use_vision=True): Convert PDF pages to images for GPT-4o/4o-mini vision
   - Best for: Visual docs, charts, scanned PDFs, layout-dependent content
   - Higher token cost

2. TEXT MODE (use_vision=False): Extract text from PDF
   - Best for: Data extraction, structured output, text-heavy PDFs
   - Much lower token cost, better for gpt-4o-mini

Uses PyMuPDF (fitz) which bundles its own PDF renderer - no system dependencies.
"""
import base64
from typing import List, Optional, Tuple
from langchain_core.messages import HumanMessage

import fitz  # PyMuPDF - pip install pymupdf


def pdf_to_base64_images(pdf_base64: str, max_pages: int = 10, zoom: float = 2.0) -> List[str]:
    """
    Convert PDF to list of base64-encoded PNG images.
    
    Args:
        pdf_base64: Base64-encoded PDF content
        max_pages: Maximum number of pages to convert (to limit token usage)
        zoom: Zoom factor for rendering (2.0 = 144 DPI, good for readability)
    
    Returns:
        List of base64-encoded PNG images (one per page)
    """
    pdf_bytes = base64.b64decode(pdf_base64)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    base64_images = []
    mat = fitz.Matrix(zoom, zoom)
    
    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        base64_images.append(base64.b64encode(png_bytes).decode("utf-8"))
    
    doc.close()
    return base64_images


def pdf_to_text(pdf_base64: str, max_pages: int = 50) -> Tuple[str, int]:
    """
    Extract text from PDF.
    
    Args:
        pdf_base64: Base64-encoded PDF content
        max_pages: Maximum number of pages to extract
    
    Returns:
        Tuple of (extracted_text, page_count)
    """
    pdf_bytes = base64.b64decode(pdf_base64)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    text_parts = []
    page_count = min(len(doc), max_pages)
    
    for page_num in range(page_count):
        page = doc[page_num]
        text = page.get_text("text")
        
        if text.strip():
            # Add page marker for multi-page docs
            if page_count > 1:
                text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
            else:
                text_parts.append(text)
    
    doc.close()
    
    full_text = "\n\n".join(text_parts)
    return full_text, page_count


def build_pdf_message(
    prompt: str,
    pdf_base64: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    use_vision: bool = False,
    max_pages: int = 10
) -> HumanMessage:
    """
    Build a LangChain HumanMessage with PDF content.
    
    Args:
        prompt: The user's text prompt
        pdf_base64: Optional base64-encoded PDF
        pdf_filename: Optional filename for context
        use_vision: If True, convert to images (for visual/scanned PDFs)
                   If False, extract text (for data extraction, cheaper)
        max_pages: Max PDF pages to include
    
    Returns:
        HumanMessage ready for the LLM
    """
    if not pdf_base64:
        return HumanMessage(content=prompt)
    
    filename_str = f" ({pdf_filename})" if pdf_filename else ""
    
    if use_vision:
        # IMAGE MODE: Convert PDF pages to images
        return _build_vision_message(prompt, pdf_base64, filename_str, max_pages)
    else:
        # TEXT MODE: Extract text from PDF (better for data extraction)
        return _build_text_message(prompt, pdf_base64, filename_str, max_pages)


def _build_vision_message(
    prompt: str, 
    pdf_base64: str, 
    filename_str: str, 
    max_pages: int
) -> HumanMessage:
    """Build multimodal message with PDF as images."""
    content = []
    
    try:
        images = pdf_to_base64_images(pdf_base64, max_pages=max_pages)
        page_count = len(images)
        
        content.append({
            "type": "text",
            "text": f"[PDF Document{filename_str} - {page_count} page{'s' if page_count != 1 else ''}]"
        })
        
        for img_base64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}",
                    "detail": "high"
                }
            })
    except Exception as e:
        content.append({
            "type": "text",
            "text": f"[Error processing PDF: {str(e)}]"
        })
    
    content.append({"type": "text", "text": prompt})
    return HumanMessage(content=content)


def _build_text_message(
    prompt: str, 
    pdf_base64: str, 
    filename_str: str, 
    max_pages: int
) -> HumanMessage:
    """Build text message with extracted PDF content."""
    try:
        text, page_count = pdf_to_text(pdf_base64, max_pages=max_pages)
        
        if not text.strip():
            # PDF might be scanned/image-based - fall back to vision
            return _build_vision_message(prompt, pdf_base64, filename_str, max_pages)
        
        # Structure the document clearly for extraction tasks
        document_section = f"""<document filename="{filename_str.strip(' ()')}" pages="{page_count}">
{text}
</document>"""
        
        full_prompt = f"{document_section}\n\n{prompt}"
        return HumanMessage(content=full_prompt)
        
    except Exception as e:
        return HumanMessage(content=f"[Error extracting PDF text: {str(e)}]\n\n{prompt}")


# Keep backward compatibility
def build_multimodal_message(
    prompt: str,
    pdf_base64: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    max_pages: int = 10
) -> HumanMessage:
    """
    Backward compatible function - uses vision mode by default.
    For new code, use build_pdf_message() with use_vision parameter.
    """
    return build_pdf_message(
        prompt=prompt,
        pdf_base64=pdf_base64,
        pdf_filename=pdf_filename,
        use_vision=True,
        max_pages=max_pages
    )
