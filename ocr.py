import argparse
import json
import os
from typing import List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ["LLM_MODEL"]


# ------------------------------------------------------------------
# Define your schema here.
# Add/remove fields as needed for your documents.
# ------------------------------------------------------------------

class LineItem(BaseModel):
    quantity: Optional[float] = None
    amount: Optional[float] = None


class Invoice(BaseModel):
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_amount: Optional[float] = None
    tax_amount: Optional[float] = None
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


def pdf_to_structured_json(pdf_path: str) -> Invoice:
    api_key = os.environ.get("LLM_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Please set the LLM_API_KEY environment variable."
        )

    client = genai.Client(api_key=api_key)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.models.generate_content(
        model=MODEL,
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

    return Invoice.model_validate_json(response.text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("--out", default=None)

    args = parser.parse_args()

    result = pdf_to_structured_json(args.pdf_path)

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