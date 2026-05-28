import os
import json
import time
import gspread
from PIL import Image
import google.generativeai as genai # 使用最新推薦套件
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 1. 認證與初始化
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=[
        "https://www.googleapis.com/auth/drive", 
        "https://www.googleapis.com/auth/spreadsheets"
    ]
)

drive_service = build('drive', 'v3', credentials=creds)
gc = gspread.authorize(creds)
# 初始化 Gemini 客戶端 (確保已安裝 google-genai)
client = Client(api_key=os.environ['GEMINI_API_KEY'])

FOLDER_ID = '1aUSfbCKTw6IrJz3Pe2S2wt9RZ_gMYwTh' # 您提供的 ID

def analyze_prescription_image(image_path):
    # 使用新版 SDK 呼叫
    image = Image.open(image_path)
    response = client.models.generate_content(
        model='gemini-2.0-flash', # 請確認模型版本
        contents=[image, "請擔任專業臨床藥師，嚴格輸出純 JSON 格式，分析病歷並生成練習題。"]
    )
    image.close()
    return response.text.replace('```json', '').replace('```', '').strip()

def save_to_sheet(data_dict):
    sh = gc.open('Prescription_Practice').sheet1
    # ... (您的存檔邏輯維持不變) ...
    row = [time.strftime("%Y-%m-%d"), str(data_dict.get('patient_info', {}).get('age', ''))] # 簡化示範
    sh.append_row(row)

# 2. 自動化主邏輯 (使用 Drive API 取代 os.listdir)
print("正在掃描 Google Drive...")
results = drive_service.files().list(
    q=f"'{FOLDER_ID}' in parents and trashed = false", 
    fields="files(id, name)"
).execute()
files = results.get('files', [])

for file in files:
    if file['name'].lower().endswith(('.jpg', '.png', '.jpeg')):
        print(f"正在處理: {file['name']}")
        
        # 下載檔案到本地暫存
        request = drive_service.files().get_media(fileId=file['id'])
        with open(file['name'], 'wb') as f:
            f.write(request.execute())
        
        # 分析與儲存
        raw_text = analyze_prescription_image(file['name'])
        save_to_sheet(json.loads(raw_text))
        
        # 移動檔案：將檔案從 FOLDER_ID 移到 processed 資料夾 (需先取得 processed 的 ID)
        # 簡單作法：直接刪除或改名 (這裡是將它移出 input 資料夾)
        PROCESSED_FOLDER_ID = '1OdiZW_biWTaXzIB6RD9MFM5BaWthryIx'
        drive_service.files().update(
                    fileId=file['id'], 
                    addParents=PROCESSED_FOLDER_ID, 
                    removeParents=FOLDER_ID,
                    fields='id, parents'
                ).execute()
        
        os.remove(file['name']) # 清理本地暫存
        print(f"✅ 完成: {file['name']}")
