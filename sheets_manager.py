import os
import json
from collections import defaultdict
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SPREADSHEET_ID = os.environ["GOOGLE_SPREADSHEET_ID"]


def _get_client():
    try:
        import streamlit as st
        creds_info = dict(st.secrets["gcp_service_account"])
    except Exception:
        creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)


def create_expense_report(name: str, address: str, items: list) -> list:
    gc = _get_client()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")

    # インボイス番号ごとにグループ化（なければ "その他"）
    groups: dict[str, list] = defaultdict(list)
    for item in items:
        key = item.get("invoice_number") or "その他"
        groups[key].append(item)

    urls = []
    for invoice_key, group_items in groups.items():
        sheet_title = f"{name}_{ts}_{invoice_key}"
        ws = spreadsheet.add_worksheet(title=sheet_title, rows=35, cols=10)
        total_row, note_row = _fill_form(ws, name, address, group_items, now)
        _format_sheet(ws, len(group_items), total_row, note_row)
        urls.append(
            f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={ws.id}"
        )

    return urls


def _fill_form(ws, name: str, address: str, items: list, now: datetime):
    issue_date = now.strftime("%Y年%-m月%-d日")

    updates = [
        {"range": "A2", "values": [["請求書（立替金清算書）"]]},
        {"range": "H4", "values": [[f"発行日　　{issue_date}"]]},
        {"range": "A6", "values": [["株式会社Vinyl Junkie Recordings"]]},
        {"range": "E6", "values": [["御中"]]},
        {"range": "H6", "values": [["氏名"]]},
        {"range": "I6", "values": [[name]]},
        {"range": "H7", "values": [["住所"]]},
        {"range": "I7", "values": [[address]]},
        {"range": "A10", "values": [["内容"]]},
        {"range": "E10", "values": [["税込金額"]]},
        {"range": "G10", "values": [["消費税　10％"]]},
        {"range": "I10", "values": [["備考"]]},
    ]

    total_amount = 0
    total_tax = 0
    invoice_notes = []

    for i, item in enumerate(items):
        row = 11 + i
        amount = item.get("amount_total") or 0
        tax = item.get("tax_amount") or round(amount * 10 / 110)
        date_str = item.get("date") or ""
        store = item.get("store_name") or ""
        desc = item.get("description") or ""
        invoice = item.get("invoice_number") or ""

        content = f"{date_str}　{desc}".strip("　 ") if date_str else desc

        biko = store  # 備考は店名のみ
        if store and invoice:
            invoice_notes.append(f"{store}（登録番号{invoice}）")

        updates += [
            {"range": f"A{row}", "values": [[content]]},
            {"range": f"E{row}", "values": [[amount]]},
            {"range": f"G{row}", "values": [[tax]]},
            {"range": f"I{row}", "values": [[biko]]},
        ]
        total_amount += amount
        total_tax += tax

    # 合計は16行目（枠内）、インボイス注記は19行目（欄外）固定
    TOTAL_ROW = 16
    NOTE_ROW = 19

    updates += [
        {"range": f"A{TOTAL_ROW}", "values": [["合　計"]]},
        {"range": f"E{TOTAL_ROW}", "values": [[total_amount]]},
        {"range": f"G{TOTAL_ROW}", "values": [[total_tax]]},
    ]

    invoice_notes = list(dict.fromkeys(invoice_notes))
    note_text = (
        "、".join(invoice_notes) + "への支払額として"
        if invoice_notes
        else "○○株式会社（登録番号T××××）への支払額として"
    )
    updates.append({"range": f"E{NOTE_ROW}", "values": [[note_text]]})

    ws.batch_update(updates, value_input_option="RAW")
    return TOTAL_ROW, NOTE_ROW


def _format_sheet(ws, num_items: int, total_row: int, note_row: int):
    """
    total_row: 合計行（枠内、通常16）
    note_row:  インボイス注記行（枠外 欄外、通常19）
    """
    sid = ws.id
    sp = ws.spreadsheet
    TSR = 9   # table start row (0-indexed) = row 10

    BLACK  = {"red": 0, "green": 0, "blue": 0}
    WHITE  = {"red": 1, "green": 1, "blue": 1}
    DARK   = {"red": 0.2, "green": 0.2, "blue": 0.2}
    GRAY   = {"red": 0.95, "green": 0.95, "blue": 0.95}
    BORDER = {"style": "SOLID_MEDIUM", "color": BLACK}
    THIN   = {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}}

    def rng(r1, c1, r2, c2):
        return {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                "startColumnIndex": c1, "endColumnIndex": c2}

    total_idx = total_row - 1  # 0-indexed（合計行）
    note_idx  = note_row - 1   # 0-indexed（欄外注記行）

    requests = [
        # ── タイトル行 A2:J2 結合 ──
        {"mergeCells": {"range": rng(1, 0, 2, 10), "mergeType": "MERGE_ALL"}},

        # ── H4:J4 発行日エリア結合 ──
        {"mergeCells": {"range": rng(3, 7, 4, 10), "mergeType": "MERGE_ALL"}},

        # ── ヘッダ行 (row10) 各列結合 ──
        {"mergeCells": {"range": rng(TSR, 0, TSR+1, 4),  "mergeType": "MERGE_ALL"}},
        {"mergeCells": {"range": rng(TSR, 4, TSR+1, 6),  "mergeType": "MERGE_ALL"}},
        {"mergeCells": {"range": rng(TSR, 6, TSR+1, 8),  "mergeType": "MERGE_ALL"}},
        {"mergeCells": {"range": rng(TSR, 8, TSR+1, 10), "mergeType": "MERGE_ALL"}},

        # ── 合計行 各列結合（枠内最終行）──
        {"mergeCells": {"range": rng(total_idx, 0, total_idx+1, 4),  "mergeType": "MERGE_ALL"}},
        {"mergeCells": {"range": rng(total_idx, 4, total_idx+1, 6),  "mergeType": "MERGE_ALL"}},
        {"mergeCells": {"range": rng(total_idx, 6, total_idx+1, 8),  "mergeType": "MERGE_ALL"}},
        {"mergeCells": {"range": rng(total_idx, 8, total_idx+1, 10), "mergeType": "MERGE_ALL"}},

        # ── インボイス注記行（欄外）E19:J19 結合 ──
        {"mergeCells": {"range": rng(note_idx, 4, note_idx+1, 10), "mergeType": "MERGE_ALL"}},

        # ── タイトル書式 ──
        {"repeatCell": {
            "range": rng(1, 0, 2, 10),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {"bold": True, "fontSize": 16},
            }},
            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment,textFormat)",
        }},

        # ── 宛先ボックス罫線（内部merge前に適用してセル単位で確実に設定）──
        {"updateBorders": {
            "range": rng(5, 0, 7, 7),
            "top": BORDER, "bottom": BORDER, "left": BORDER, "right": BORDER,
        }},

        # ── 氏名/住所ボックス罫線（内部merge前に適用）──
        {"updateBorders": {
            "range": rng(5, 7, 7, 10),
            "top": BORDER, "bottom": BORDER, "left": BORDER, "right": BORDER,
            "innerHorizontal": THIN, "innerVertical": THIN,
        }},

        # ── ヘッダセクション内部結合（罫線適用後）──
        # A6:D6 会社名
        {"mergeCells": {"range": rng(5, 0, 6, 4),  "mergeType": "MERGE_ALL"}},
        # I6:J6 氏名値
        {"mergeCells": {"range": rng(5, 8, 6, 10), "mergeType": "MERGE_ALL"}},
        # I7:J7 住所値
        {"mergeCells": {"range": rng(6, 8, 7, 10), "mergeType": "MERGE_ALL"}},

        # ── ヘッダセクション書式 ──
        {"repeatCell": {
            "range": rng(3, 7, 4, 10),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "RIGHT",
                "verticalAlignment": "MIDDLE",
            }},
            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
        }},
        {"repeatCell": {
            "range": rng(5, 0, 6, 4),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "LEFT",
                "verticalAlignment": "BOTTOM",
            }},
            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
        }},
        {"repeatCell": {
            "range": rng(5, 4, 6, 5),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "LEFT",
                "verticalAlignment": "BOTTOM",
            }},
            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
        }},
        {"repeatCell": {
            "range": rng(5, 7, 7, 8),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "LEFT",
                "verticalAlignment": "MIDDLE",
            }},
            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
        }},
        {"repeatCell": {
            "range": rng(5, 8, 7, 10),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "LEFT",
                "verticalAlignment": "MIDDLE",
            }},
            "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
        }},

        # ── テーブルヘッダ行書式（濃色背景・白文字）──
        {"repeatCell": {
            "range": rng(TSR, 0, TSR+1, 10),
            "cell": {"userEnteredFormat": {
                "backgroundColor": DARK,
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {"bold": True, "foregroundColor": WHITE, "fontSize": 10},
            }},
            "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)",
        }},

        # ── 合計行書式（薄グレー背景・太字）──
        {"repeatCell": {
            "range": rng(total_idx, 0, total_idx+1, 10),
            "cell": {"userEnteredFormat": {
                "backgroundColor": GRAY,
                "textFormat": {"bold": True},
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }},

        # ── テーブル全体の罫線（row10〜total_row、欄外の注記行は含まない）──
        {"updateBorders": {
            "range": rng(TSR, 0, total_idx+1, 10),
            "top": BORDER, "bottom": BORDER, "left": BORDER, "right": BORDER,
            "innerHorizontal": THIN, "innerVertical": THIN,
        }},

        # ── 金額列：右寄せ・通貨フォーマット（データ行 row11〜total_row-1）──
        {"repeatCell": {
            "range": rng(TSR+1, 4, total_idx, 8),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "RIGHT",
                "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
            }},
            "fields": "userEnteredFormat(horizontalAlignment,numberFormat)",
        }},
        # 合計行の金額も右寄せ
        {"repeatCell": {
            "range": rng(total_idx, 4, total_idx+1, 8),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "RIGHT",
                "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
            }},
            "fields": "userEnteredFormat(horizontalAlignment,numberFormat)",
        }},

        # ── 備考列（I-J）のデータ行：テキスト折り返し ──
        {"repeatCell": {
            "range": rng(TSR+1, 8, total_idx, 10),
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat(wrapStrategy)",
        }},

        # ── インボイス注記（欄外 row19）：左寄せ・斜体 ──
        {"repeatCell": {
            "range": rng(note_idx, 4, note_idx+1, 10),
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "LEFT",
                "textFormat": {"italic": True, "fontSize": 9},
            }},
            "fields": "userEnteredFormat(horizontalAlignment,textFormat)",
        }},

        # ── タイトル行の高さ ──
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 48},
            "fields": "pixelSize",
        }},

        # ── 列幅：10列均等（100px）──
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 10},
            "properties": {"pixelSize": 100},
            "fields": "pixelSize",
        }},
    ]

    # ── データ行（row11〜total_row-1）の列結合 ──
    for i in range(total_row - 11):
        r = TSR + 1 + i
        requests += [
            {"mergeCells": {"range": rng(r, 0, r+1, 4),  "mergeType": "MERGE_ALL"}},
            {"mergeCells": {"range": rng(r, 4, r+1, 6),  "mergeType": "MERGE_ALL"}},
            {"mergeCells": {"range": rng(r, 6, r+1, 8),  "mergeType": "MERGE_ALL"}},
            {"mergeCells": {"range": rng(r, 8, r+1, 10), "mergeType": "MERGE_ALL"}},
        ]

    sp.batch_update({"requests": requests})
