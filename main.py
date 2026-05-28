import os
import json
import time
import gspread
from PIL import Image
from google import genai  # 使用新版 SDK
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

# 正確初始化新版 Gemini Client
client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

FOLDER_ID = '149F1PWx5ntPLZyoZrampX9KunWsX6viw'
PROCESSED_FOLDER_ID = '1OdiZW_biWTaXzIB6RD9MFM5BaWthryIx'

def analyze_prescription_image(image_path):
    """使用新版 SDK 進行分析"""
    image = Image.open(image_path)
    response = client.models.generate_content(
        model='gemini-2.0-flash', 
        contents=[image, "請擔任專業臨床藥師，嚴格輸出純 JSON 格式，不要包含 markdown 標記，分析病歷並生成練習題。"]
    )
    image.close()
    # 清理回應內容
    return response.text.replace('```json', '').replace('```', '').strip()

def save_to_sheet(data_dict):
    """寫入 Google Sheets"""
    sh = gc.open('Prescription_Practice').sheet1
    row = [
        time.strftime("%Y-%m-%d"),
        str(data_dict.get('patient_info', {}).get('age', '')),
        str(data_dict.get('patient_info', {}).get('gender', '')),
        str(data_dict.get('patient_info', {}).get('allergy', '')),
        str(data_dict.get('clinical_data', {}).get('diagnosis', '')),
        str(data_dict.get('medication_list', [])),
        str(data_dict.get('clinical_data', {}).get('lab_values', '')),
        str(data_dict.get('practice_question', {}).get('question', '')),
        str(data_dict.get('practice_question', {}).get('answer', '')),
        str(data_dict.get('practice_question', {}).get('explanation', ''))
    ]
    sh.append_row(row)

# 2. 自動化主邏輯
print("正在掃描 Google Drive...")
            results = drive_service.files().list(
                q=f"'{FOLDER_ID}' in parents and trashed = false", 
                fields="files(id, name)",
                pageSize=1  # 強制限制只拿取 1 個檔案
            ).execute()
            files = results.get('files', [])
            
            if not files:
                print("沒有需要處理的圖片。")
            else:
                file = files[0] # 只拿第一張
                print(f"本次任務只處理: {file['name']}")
            
            # 下載檔案
            request = drive_service.files().get_media(fileId=file['id'])
            with open(file['name'], 'wb') as f:
                f.write(request.execute())
            
            # 分析與儲存
            try:
                raw_text = analyze_prescription_image(file['name'])
                data = json.loads(raw_text)
                save_to_sheet(data)
                
                # 移動檔案
                drive_service.files().update(
                    fileId=file['id'], 
                    addParents=PROCESSED_FOLDER_ID, 
                    removeParents=FOLDER_ID,
                    fields='id, parents'
                ).execute()
                
                print(f"✅ 完成: {file['name']}")
            except Exception as e:
                print(f"❌ 處理失敗: {file['name']}, 錯誤: {e}")
            finally:
                if os.path.exists(file['name']):
                    os.remove(file['name'])
