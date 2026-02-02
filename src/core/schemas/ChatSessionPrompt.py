from pydantic import BaseModel
from typing import Optional


class ChatSessionPrompt(BaseModel):
    prompt: str
    sessionId: str
    # Optional PDF attachment (base64 encoded)
    pdf: Optional[str] = None
    pdfFilename: Optional[str] = None
    # PDF processing mode:
    # - True: Use vision (images) - for scanned PDFs, charts, visual layout
    # - False: Use text extraction - for data extraction, cheaper with gpt-4o-mini
    pdfUseVision: Optional[bool] = False