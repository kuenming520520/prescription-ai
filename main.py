#20260527

import os
import json
from google.oauth2 import service_account

# 讀取 GitHub Secrets 的金鑰內容
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = service_account.Credentials.from_service_account_info(creds_dict, 
        scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"])

# 接下來使用這個 creds 進行 gspread 或 Drive API 的初始化

import google.generativeai as genai
import json
import os
import gspread
import time
import shutil
from google.auth import default
from google.colab import auth, drive
from PIL import Image

# --- 1. 環境初始化與掛載 ---
# 若未掛載則執行掛載
if not os.path.exists('/content/my_drive/MyDrive'):
    drive.mount('/content/my_drive')

# 設定 API Key 與模型
genai.configure(api_key='AIzaSyBwKoksLbACIiK-XX06kdc8Kdjz7L90p0w') # 請填入您的 API KEY
model = genai.GenerativeModel('gemini-2.5-flash')

# 認證 Google Sheets
auth.authenticate_user()
creds, _ = default()
gc = gspread.authorize(creds)

# --- 2. 核心功能函式 ---

def analyze_prescription_image(image_path, user_comment):
    """呼叫 Gemini 進行影像分析並回傳 JSON 文字"""
    img = Image.open(image_path)
    prompt = f"""
    請擔任專業臨床藥師，分析這張藥歷圖片。請嚴格輸出純 JSON 格式，不要包含任何 markdown 符號。
    要求欄位：patient_info (age, gender, allergy), clinical_data (diagnosis, lab_values),
    medication_list, practice_question (type, question, options, answer, explanation)。
    使用者疑義描述：{user_comment}
    """
    response = model.generate_content([img, prompt])

    img.close() # <--- 重要：一定要加這一行，釋放檔案鎖定

    # 清理回應內容：移除 markdown 標記
    text = response.text.replace('```json', '').replace('```', '').strip()
    return text

def save_to_sheet(data_dict):
    """將解析後的字典資料寫入 Google Sheets"""
    sh = gc.open('Prescription_Practice').sheet1
    row = [
        time.strftime("%Y-%m-%d"),
        str(data_dict.get('patient_info', {}).get('age', '')),
        str(data_dict.get('patient_info', {}).get('gender', '')),
        str(data_dict.get('patient_info', {}).get('allergy', '')),
        str(data_dict.get('clinical_data', {}).get('diagnosis', '')),
        str(data_dict.get('medication_list', [])),
        str(data_dict.get('clinical_data', {}).get('lab_values', {})),
        str(data_dict.get('practice_question', {}).get('question', '')),
        str(data_dict.get('practice_question', {}).get('answer', '')),
        str(data_dict.get('practice_question', {}).get('explanation', ''))
    ]
    sh.append_row(row)

# --- 3. 自動化執行主迴圈 ---

import os
import shutil
import time
from pathlib import Path

# 定義絕對路徑物件
input_dir = Path('/content/my_drive/MyDrive/AI_Prescription_Project/input_images')
processed_dir = Path('/content/my_drive/MyDrive/AI_Prescription_Project/processed')

# 強制重新列出檔案，忽略系統快取
files = [f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.png', '.jpeg']]

if not files:
    print(f"掃描失敗：在 {input_dir} 下沒有發現圖片檔案。")
    print("目前該資料夾下有的項目:", list(input_dir.iterdir()))
else:
    for file_path in files:
        try:
            print(f"正在分析檔案: {file_path.name} ...")
            # 呼叫解析函式
            raw_text = analyze_prescription_image(str(file_path), "請分析此病歷並生成疑義處方練習題")
            data = json.loads(raw_text)

            # 寫入 Sheet
            save_to_sheet(data)

            # 歸檔 (使用 Path 物件移動)
            dest_path = processed_dir / file_path.name
            shutil.move(str(file_path), str(dest_path))

            print(f"✅ 成功完成並歸檔: {file_path.name}")
            time.sleep(2)
        except Exception as e:
            print(f"❌ 處理 {file_path.name} 失敗，錯誤訊息: {e}")
