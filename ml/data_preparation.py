import pandas as pd
from datetime import datetime
import secrets
import string
from pathlib import Path

# ==========================================
# 檔案路徑設定
# ==========================================
RAW_DATA_PATH = Path("data/employee_data.csv")
OUTPUT_DB_DATA = Path("data/frontend_users_db.csv")

def generate_random_password(length=10):
    """生成隨機初始密碼供前端測試與登入使用"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_frontend_db(filepath: Path) -> pd.DataFrame:
    """
    讀取原始人事資料，並生成包含帳號、密碼、Email 的前端資料庫
    """
    print(f"讀取原始人事資料: {filepath}...")
    df = pd.read_csv(filepath)
    
    # 1. 處理姓名並生成 Email (加入容錯機制，處理沒有逗號的異常資料)
    def generate_email(name_str):
        if pd.isna(name_str):
            return ""
        name_str = str(name_str).strip()
        
        # 情況 A: "Last, First" (例如 "Brown, Mia")
        if ',' in name_str:
            parts = name_str.split(',')
            last = parts[0].strip().lower()
            first = parts[1].strip().lower()
        # 情況 B: "First Last" (例如 "Jeremy Prater")
        else:
            parts = name_str.split(' ')
            first = parts[0].strip().lower()
            last = parts[-1].strip().lower() if len(parts) > 1 else ""
            
        # 處理姓名中可能有的單引號或特殊字元 (例如 Jene'ya -> jeneya)
        first = first.replace("'", "").replace('"', '')
        last = last.replace("'", "").replace('"', '')
        
        return f"{first}.{last}@company.com"

    df['email'] = df['Employee Name'].apply(generate_email)
    
    # 2. 建立登入帳號與密碼
    # 使用員工編號當作登入帳號 (確保唯一性)
    df['username'] = df['Employee Number'].astype(str)
    # 生成隨機密碼 (實務上寫入 DB 前會使用 bcrypt 等套件 Hash 加密)
    df['raw_password'] = [generate_random_password() for _ in range(len(df))]
    
    # 3. 處理生日轉換為年齡 (若前端個人資料頁面需要顯示年齡)
    df['DOB'] = pd.to_datetime(df['DOB'], errors='coerce')
    current_date = pd.to_datetime('today')
    df['Age'] = (current_date - df['DOB']).dt.days / 365.25
    df['Age'] = df['Age'].round(1)
    
    # 4. 篩選前端與後端 API 實際需要的欄位
    frontend_db_columns = [
        'Employee Number',   # ⚠️ 關鍵欄位：後端用來對應 hr_data.csv 抓特徵
        'username', 
        'email', 
        'raw_password', 
        'Employee Name', 
        'Age',
        'Department', 
        'Position', 
        'Employment Status',
        'Manager Name'
    ]
    df_frontend = df[frontend_db_columns].copy()
    
    return df_frontend

def main():
    try:
        # 確保輸出資料夾存在
        OUTPUT_DB_DATA.parent.mkdir(parents=True, exist_ok=True)
        
        # 執行轉換
        df_front = create_frontend_db(RAW_DATA_PATH)
        
        # 輸出 CSV 檔案
        df_front.to_csv(OUTPUT_DB_DATA, index=False)
        
        print(f"\n✅ 前端使用者資料庫已成功生成: {OUTPUT_DB_DATA}")
        print("-" * 50)
        print("資料預覽 (前 5 筆帳密資訊):")
        print(df_front[['Employee Number', 'username', 'email', 'raw_password']].head())
        print("-" * 50)
        
        # 特別檢查 Jeremy Prater 的 Email 是否成功生成
        jeremy_check = df_front[df_front['Employee Name'].str.contains('Jeremy Prater', na=False, case=False)]
        if not jeremy_check.empty:
            print("\n🔍 異常資料檢查 (Jeremy Prater):")
            print(jeremy_check[['Employee Name', 'email']])
            
        print("\n你可以將這份檔案交給前端/後端工程師，作為開發登入系統的 Mock Database！")
        
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {RAW_DATA_PATH}，請確認路徑是否正確。")
    except Exception as e:
        print(f"❌ 執行時發生錯誤: {e}")

if __name__ == "__main__":
    main()