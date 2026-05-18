import os

import streamlit as st
from dotenv import load_dotenv

from receipt_extractor import extract_receipt_info
from sheets_manager import create_expense_report, cleanup_service_account_drive, create_expense_xlsx

load_dotenv(dotenv_path=".env")

st.set_page_config(
    page_title="バンド経費精算",
    page_icon="🎸",
    layout="centered",
)

# ── Session state 初期化 ────────────────────────────────────
if "expense_items" not in st.session_state:
    st.session_state.expense_items = []
if "sheet_urls" not in st.session_state:
    st.session_state.sheet_urls = []
if "xlsx_data" not in st.session_state:
    st.session_state.xlsx_data = None
if "xlsx_filename" not in st.session_state:
    st.session_state.xlsx_filename = ""


# ── ダイアログ：精算書作成して終了 ────────────────────────
@st.dialog("確認")
def confirm_create(name, address, folder_name):
    st.write("終了ですか？")
    st.caption("確認後、精算書（Excelファイル）を作成してダウンロードします。")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("はい", type="primary", use_container_width=True):
            with st.spinner("精算書を作成中..."):
                try:
                    from datetime import datetime
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    xlsx_bytes = create_expense_xlsx(
                        name=name,
                        address=address,
                        items=st.session_state.expense_items,
                    )
                    fn = folder_name.strip() or f"経費精算_{name}_{ts}"
                    st.session_state.xlsx_data = xlsx_bytes
                    st.session_state.xlsx_filename = f"{fn}.xlsx"
                    st.session_state.expense_items = []
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ エラーが発生しました：{e}")
    with c2:
        if st.button("いいえ", use_container_width=True):
            st.rerun()


# ── ダイアログ：リセット確認 ──────────────────────────────
@st.dialog("確認")
def confirm_reset():
    st.write("終了ですか？")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("はい", type="primary", use_container_width=True):
            st.session_state.expense_items = []
            st.session_state.sheet_urls = []
            st.session_state.xlsx_data = None
            st.session_state.xlsx_filename = ""
            st.rerun()
    with c2:
        if st.button("いいえ", use_container_width=True):
            st.rerun()


# ── ヘッダー ──────────────────────────────────────────────
st.title("🎸 バンド経費精算")
st.caption("レシート・領収書の写真またはPDFをアップロードして精算書を自動作成します")

st.divider()

# ── 申請者情報 ────────────────────────────────────────────
MEMBERS = [
    {"name": "二宮大河", "address": "京都府京都市中京区左京町141 ウィルパーク高倉御池505"},
]

st.subheader("📋 申請者情報")

member_names = [m["name"] for m in MEMBERS]
selected = st.selectbox("氏名", member_names)
member = next(m for m in MEMBERS if m["name"] == selected)
name = member["name"]
address = member["address"]
st.caption(f"住所：{address}")

folder_name = st.text_input("案件名（Driveフォルダ名）", placeholder="例：2026年5月 スタジオ代")

st.divider()

# ── ファイルアップロード ───────────────────────────────────
st.subheader("📎 レシート・領収書をアップロード")
st.caption("写真（JPG・PNG）またはPDFに対応。複数まとめて選択できます。")

uploaded_files = st.file_uploader(
    "ファイルを選択",
    type=["jpg", "jpeg", "png", "pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if uploaded_files:
    if st.button("📖 読み取り開始", type="primary", use_container_width=True):
        progress = st.progress(0, text="読み取り中...")
        new_items = []

        for i, f in enumerate(uploaded_files):
            progress.progress(
                (i + 1) / len(uploaded_files),
                text=f"読み取り中… {f.name} ({i+1}/{len(uploaded_files)})",
            )
            raw = f.read()
            infos = extract_receipt_info(raw)
            for j, info in enumerate(infos):
                info["_filename"] = f.name if len(infos) == 1 else f"{f.name} #{j+1}"
                new_items.append(info)

        progress.empty()

        errors = [it for it in new_items if "error" in it]
        ok = [it for it in new_items if "error" not in it]

        if errors:
            for e in errors:
                st.error(f"❌ {e.get('_filename', '')}: {e['error']}")
        if ok:
            st.session_state.expense_items.extend(ok)
            st.success(f"✅ {len(ok)}件を読み取りました！内容を確認してください。")
            st.session_state.sheet_urls = []

st.divider()

# ── 読み取り済みリスト（確認・編集）──────────────────────
if st.session_state.expense_items:
    st.subheader(f"📝 経費一覧（{len(st.session_state.expense_items)}件）")
    st.caption("内容を確認・修正してから精算書を作成してください。")

    delete_index = None

    for i, item in enumerate(st.session_state.expense_items):
        with st.expander(
            f"#{i+1}　{item.get('date') or '日付不明'}　{item.get('store_name') or '店名不明'}　"
            f"¥{item.get('amount_total', 0):,}",
            expanded=False,
        ):
            c1, c2 = st.columns(2)
            with c1:
                item["date"] = st.text_input("日付", value=item.get("date") or "", key=f"date_{i}")
                item["store_name"] = st.text_input("店名・支払先", value=item.get("store_name") or "", key=f"store_{i}")
                item["description"] = st.text_input("内容・用途", value=item.get("description") or "", key=f"desc_{i}")
            with c2:
                amount = st.number_input(
                    "税込金額（円）",
                    value=int(item.get("amount_total") or 0),
                    min_value=0,
                    step=1,
                    key=f"amount_{i}",
                )
                item["amount_total"] = amount
                default_tax = round(amount * 10 / 110) if amount else 0
                tax = st.number_input(
                    "消費税（円）",
                    value=int(item.get("tax_amount") or default_tax),
                    min_value=0,
                    step=1,
                    key=f"tax_{i}",
                )
                item["tax_amount"] = tax
                item["invoice_number"] = st.text_input(
                    "インボイス番号（任意）",
                    value=item.get("invoice_number") or "",
                    placeholder="T1234567890123",
                    key=f"invoice_{i}",
                )

            if st.button("🗑️ この件を削除", key=f"del_{i}"):
                delete_index = i

    if delete_index is not None:
        st.session_state.expense_items.pop(delete_index)
        st.session_state.sheet_urls = []
        st.rerun()

    # 合計
    total_amount = sum(it.get("amount_total") or 0 for it in st.session_state.expense_items)
    total_tax = sum(it.get("tax_amount") or 0 for it in st.session_state.expense_items)
    st.info(f"**合計：¥{total_amount:,}**　（うち消費税：¥{total_tax:,}）")

    st.divider()

    # 精算書作成ボタン
    st.subheader("📄 精算書を作成")

    if not name:
        st.warning("氏名を入力してください。")
    else:
        if st.button("🚀 精算書を作成して終了", type="primary", use_container_width=True):
            confirm_create(name, address, folder_name)

# ── 作成済みリンク表示 ────────────────────────────────────
if st.session_state.sheet_urls:
    n = len(st.session_state.sheet_urls)
    st.success(f"✅ 精算書が{n}件完成しました！（インボイス番号ごとに分割）")
    for i, url in enumerate(st.session_state.sheet_urls, 1):
        st.link_button(
            f"📊 精算書 {i} を開く",
            url,
            use_container_width=True,
        )
    st.divider()
    if st.button("🔄 新しい精算書を作る", use_container_width=True):
        confirm_reset()

# ── XLSXダウンロード表示 ──────────────────────────────────
if st.session_state.xlsx_data:
    st.success("✅ 精算書が完成しました！")
    st.download_button(
        label="📥 精算書をダウンロード（Excel）",
        data=st.session_state.xlsx_data,
        file_name=st.session_state.xlsx_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
    st.divider()
    if st.button("🔄 新しい精算書を作る", key="new_after_xlsx", use_container_width=True):
        st.session_state.xlsx_data = None
        st.session_state.xlsx_filename = ""
        confirm_reset()

# ── 初期表示 ──────────────────────────────────────────────
elif not st.session_state.expense_items and not st.session_state.xlsx_data:
    st.info("上のエリアからレシート・領収書をアップロードしてください。")

# ── 管理：ストレージクリーンアップ ───────────────────────
with st.sidebar:
    st.divider()
    st.caption("🛠️ 管理")
    if st.button("🗑️ サービスアカウントのDriveを空にする", use_container_width=True):
        with st.spinner("削除中..."):
            try:
                deleted, total = cleanup_service_account_drive()
                st.success(f"✅ {deleted}/{total} 件を削除しました。再度アップロードをお試しください。")
            except Exception as e:
                st.error(f"❌ {e}")
