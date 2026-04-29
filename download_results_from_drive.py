"""
Download hasil (results/) dari Google Drive ke folder lokal.

Struktur Drive yang diunduh:
  MyDrive/UTS_DEEPL_S2/results/
    classification/figures/, tables/, models/
    regression/figures/, tables/, models/

Kebutuhan:
  pip install google-auth google-auth-oauthlib google-api-python-client

Langkah pertama kali:
  1. Buka https://console.cloud.google.com/
  2. Buat project baru → Enable "Google Drive API"
  3. Buat OAuth 2.0 Client ID (tipe: Desktop App)
  4. Download JSON credentials → simpan sebagai  credentials.json
     di folder yang sama dengan script ini
"""

import io
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ── Konfigurasi ────────────────────────────────────────────────────────────────
DRIVE_RESULTS_PATH = "UTS_DEEPL_S2/results"   # path di dalam My Drive
LOCAL_DEST = Path("results_from_drive")        # folder tujuan di lokal
CREDENTIALS_FILE = "credentials.json"          # file OAuth dari Google Console
TOKEN_FILE = "token.json"                      # disimpan otomatis setelah login

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
# ──────────────────────────────────────────────────────────────────────────────


def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def get_folder_id(service, folder_path: str) -> str:
    """Navigasi folder bertingkat di Drive berdasarkan path string."""
    parts = folder_path.strip("/").split("/")
    parent_id = "root"
    for part in parts:
        query = (
            f"name='{part}' and mimeType='application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents and trashed=false"
        )
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError(f"Folder '{part}' tidak ditemukan di Drive (parent: {parent_id})")
        parent_id = files[0]["id"]
        print(f"  Folder ditemukan: {part} (id={parent_id})")
    return parent_id


def download_folder(service, folder_id: str, local_path: Path):
    """Unduh seluruh isi folder secara rekursif."""
    local_path.mkdir(parents=True, exist_ok=True)

    query = f"'{folder_id}' in parents and trashed=false"
    page_token = None
    while True:
        response = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()

        for item in response.get("files", []):
            item_path = local_path / item["name"]
            if item["mimeType"] == "application/vnd.google-apps.folder":
                print(f"[DIR]  {item_path}")
                download_folder(service, item["id"], item_path)
            else:
                download_file(service, item["id"], item_path)

        page_token = response.get("nextPageToken")
        if not page_token:
            break


def download_file(service, file_id: str, local_path: Path):
    """Unduh satu file dari Drive."""
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    local_path.write_bytes(buffer.getvalue())
    print(f"[FILE] {local_path}")


def main():
    print("Autentikasi Google Drive...")
    creds = authenticate()
    service = build("drive", "v3", credentials=creds)

    print(f"\nMencari folder: {DRIVE_RESULTS_PATH}")
    folder_id = get_folder_id(service, DRIVE_RESULTS_PATH)

    print(f"\nMengunduh ke: {LOCAL_DEST.resolve()}")
    download_folder(service, folder_id, LOCAL_DEST)

    print(f"\nSelesai! Semua file tersimpan di: {LOCAL_DEST.resolve()}")


if __name__ == "__main__":
    main()
