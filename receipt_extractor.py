import json
import os
import re

import google.generativeai as genai

def _get_model():
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel("gemini-2.5-flash")

PROMPT = """このレシート・領収書から情報を抽出して、必ずJSON形式のみで返してください。

{
  "date": "YYYY年MM月DD日形式（例：2024年10月12日）",
  "store_name": "店名・支払先名",
  "amount_total": 税込合計金額（整数、円記号なし）,
  "tax_amount": 消費税額（整数。記載なければ合計×10÷110を四捨五入）,
  "description": "購入品目や用途の簡潔な説明（例：機材費、交通費、スタジオ代）",
  "invoice_number": "インボイス登録番号（Tから始まる13桁、なければnull）"
}

注意：
- 金額は整数のみ（カンマ・円記号なし）
- 読み取れない項目はnull
- 説明は日本語で30文字以内
- JSON以外のテキストは絶対に含めない"""


def detect_media_type(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:3] == b"GIF":
        return "image/gif"
    if data[:4] == b"%PDF":
        return "application/pdf"
    return "image/jpeg"


def extract_receipt_info(raw_bytes: bytes) -> dict:
    """画像またはPDFのバイト列からレシート情報を抽出する。"""
    mime_type = detect_media_type(raw_bytes)
    try:
        part = {"mime_type": mime_type, "data": raw_bytes}
        response = _get_model().generate_content([part, PROMPT])
        text = response.text.strip()

        json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            return {"error": "JSONを抽出できませんでした", "raw": text}

        data = json.loads(json_match.group())
        for field in ("amount_total", "tax_amount"):
            if data.get(field) is not None:
                try:
                    data[field] = int(data[field])
                except (ValueError, TypeError):
                    data[field] = 0
        return data

    except json.JSONDecodeError as e:
        return {"error": f"JSON解析エラー: {e}"}
    except Exception as e:
        return {"error": str(e)}
