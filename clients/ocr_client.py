import argparse
import json
import logging
import time
from typing import List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

import config

log = logging.getLogger("ap_agent.llm")


# ------------------------------------------------------------------
# Define your schema here.
# Add/remove fields as needed for your documents.
# ------------------------------------------------------------------

class LineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class Invoice(BaseModel):
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    purchase_order: Optional[str] = None
    currency: Optional[str] = None
    line_items: Optional[List[LineItem]] = None


PROMPT = """
You are an OCR and document extraction engine.

Instructions:
1. Read the PDF carefully.
2. Consider all pages.
3. Extract information into the provided schema.
4. If a value is explicitly present, populate it.
5. If a value is not present or cannot be determined confidently,
   return null.
6. Do NOT guess, infer, or hallucinate values.
7. Preserve dates, numbers, and text exactly as they appear.
8. Return only valid JSON matching the schema.

Think of the task as:
- Read document.
- Identify matching fields.
- Populate schema.
- Return null for missing fields.
"""


def pdf_bytes_to_structured_json(pdf_bytes: bytes) -> Invoice:
    if not config.LLM_API_KEY:
        raise RuntimeError(
            "Please set the LLM_API_KEY environment variable."
        )

    client = genai.Client(api_key=config.LLM_API_KEY)

    log.info("llm generate_content model=%s task=ocr_extraction pdf_bytes=%d", config.LLM_MODEL, len(pdf_bytes))
    start = time.monotonic()
    response = client.models.generate_content(
        model=config.LLM_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(
                        data=pdf_bytes,
                        mime_type="application/pdf",
                    ),
                    types.Part.from_text(text=PROMPT),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Invoice,
        ),
    )
    usage = getattr(response, "usage_metadata", None)
    log.info(
        "llm generate_content completed (%.1fms) tokens=%s",
        (time.monotonic() - start) * 1000,
        usage.total_token_count if usage else "?",
    )

    return Invoice.model_validate_json(response.text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("--out", default=None)

    args = parser.parse_args()

    with open(args.pdf_path, "rb") as f:
        pdf_bytes = f.read()

    result = pdf_bytes_to_structured_json(pdf_bytes)

    output = json.dumps(
        result.model_dump(),
        indent=2,
        ensure_ascii=False,
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)

        print(f"Output written to {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
