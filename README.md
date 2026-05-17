# バンド経費精算アプリ 🎸

レシート・領収書の写真またはPDFをアップロードするだけで、立替金精算書（Googleスプレッドシート）を自動作成するWebアプリです。

## 使い方

1. アプリを開いて氏名・住所を入力
2. レシートの写真またはPDFをアップロード（複数OK）
3. 「読み取り開始」を押す
4. 内容を確認・修正して「精算書を作成」
5. Googleスプレッドシートのリンクが表示される

---

## セットアップ手順

### 必要なもの（全て無料）

- **Google Gemini API Key** — レシート読み取り用（1日1,500回まで無料）
- **Google Service Account** — スプレッドシート書き込み用
- **GitHub アカウント** — コードのホスティング
- **Streamlit Community Cloud** — 無料Webホスティング

---

### Step 1: Google Gemini API Key の取得（無料）

1. [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) にアクセス
2. Googleアカウントでログイン
3. 「APIキーを作成」→ キーをコピーして保存

無料枠：1日1,500リクエスト（バンドの経費精算には十分です）

---

### Step 2: Google Sheets の設定

#### 2-1. サービスアカウントを作成

1. [Google Cloud Console](https://console.cloud.google.com/) にログイン
2. 「新しいプロジェクト」を作成（例：band-expense）
3. 「APIとサービス」→「ライブラリ」で以下を有効化：
   - **Google Sheets API**
   - **Google Drive API**
4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」
5. 名前を入力（例：expense-bot）→「作成して続行」→「完了」
6. 作成されたサービスアカウントをクリック
7. 「キー」タブ→「鍵を追加」→「新しい鍵を作成」→「JSON」
8. JSONファイルがダウンロードされる

#### 2-2. スプレッドシートを作成・共有

1. [Google スプレッドシート](https://sheets.google.com) で新規作成
2. 名前：「バンド経費精算書」など
3. URLからスプレッドシートIDをコピー：
   ```
   https://docs.google.com/spreadsheets/d/【ここがID】/edit
   ```
4. 「共有」ボタン → サービスアカウントのメールを追加（**編集者**権限）
   - メールアドレスはJSONファイル内 `client_email` に記載

---

### Step 3: GitHubにプッシュ

```bash
cd band-expense-bot
git init
git add .
git commit -m "初回コミット"
# GitHubで新規リポジトリを作成（プライベート推奨）
git remote add origin https://github.com/あなたのID/band-expense-bot.git
git push -u origin main
```

---

### Step 4: Streamlit Cloud にデプロイ

1. [share.streamlit.io](https://share.streamlit.io) にログイン（GitHubアカウントで）
2. 「New app」→ リポジトリを選択
3. **Main file path**: `app.py`
4. 「Advanced settings」→「Secrets」に以下を入力：

```toml
GEMINI_API_KEY = "AIzaxxxxxxxxxxxxxxxx"
GOOGLE_SPREADSHEET_ID = "スプレッドシートのID"
GOOGLE_CREDENTIALS_JSON = '''
{
  "type": "service_account",
  "project_id": "...",
  ...JSONファイルの中身をそのまま貼る...
}
'''
```

5. 「Deploy!」でデプロイ完了（1〜2分）

---

### ローカルで試す場合

```bash
cd band-expense-bot

# 環境変数ファイルを作成
cp .env.example .env
# .env に各キーを入力

# 依存パッケージをインストール
pip install -r requirements.txt

# アプリを起動
streamlit run app.py
# ブラウザで http://localhost:8501 が開く
```

---

## ファイル構成

```
band-expense-bot/
├── app.py                  # Streamlit Webアプリ（メイン）
├── receipt_extractor.py    # Claude APIでレシート読み取り
├── sheets_manager.py       # Googleスプレッドシート生成
├── requirements.txt
├── .env.example
└── .streamlit/
    └── config.toml         # テーマ設定
```

## 精算書フォーマット

- **宛先**：株式会社Vinyl Junkie Recordings 御中（固定）
- **発行日**：作成日を自動入力
- **テーブル**：内容 / 税込金額 / 消費税10% / 備考
- **インボイス番号**：レシートに記載があれば備考欄に自動記入
