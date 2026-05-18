"""
サービスアカウントのGoogle Driveに溜まった古いファイルを削除するスクリプト。
ストレージクォータ超過エラーが発生したときに実行してください。

使い方:
  python cleanup_drive.py          # 一覧表示のみ（削除しない）
  python cleanup_drive.py --delete # 実際に削除
"""
import argparse
import json
import os
import sys

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_info = json.loads(creds_json)
    else:
        for path in ["credentials.json", ".credentials.json"]:
            if os.path.exists(path):
                with open(path) as f:
                    creds_info = json.load(f)
                break
        else:
            print("ERROR: GOOGLE_CREDENTIALS_JSON 環境変数か credentials.json が必要です")
            sys.exit(1)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def list_all_files(drive):
    files = []
    page_token = None
    while True:
        kwargs = {
            "q": "trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, createdTime, size)",
            "pageSize": 100,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        result = drive.files().list(**kwargs).execute()
        files.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="ファイルを実際に削除する")
    args = parser.parse_args()

    drive = get_drive()
    files = list_all_files(drive)

    if not files:
        print("サービスアカウントのDriveにファイルはありません。")
        return

    total_size = sum(int(f.get("size", 0)) for f in files)
    print(f"合計 {len(files)} 件のファイル（約 {total_size / 1024 / 1024:.1f} MB）\n")

    for f in files:
        size_kb = int(f.get("size", 0)) / 1024
        print(f"  [{f['createdTime'][:10]}] {f['name']}  ({size_kb:.0f} KB)")

    if not args.delete:
        print("\n上記ファイルを削除するには --delete オプションを付けて実行してください:")
        print("  python cleanup_drive.py --delete")
        return

    print(f"\n{len(files)} 件のファイルを削除します...")
    deleted = 0
    for f in files:
        try:
            drive.files().delete(fileId=f["id"]).execute()
            print(f"  削除: {f['name']}")
            deleted += 1
        except Exception as e:
            print(f"  スキップ: {f['name']} ({e})")

    print(f"\n完了: {deleted}/{len(files)} 件を削除しました。")


if __name__ == "__main__":
    main()
