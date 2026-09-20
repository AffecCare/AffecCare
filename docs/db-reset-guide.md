# 資料庫完整重設流程（DB Reset Guide）

> 適用情境：推薦引擎改為 3 分類偏好制後的資料結構變更（向量維度 5→3、
> `users` 表新增 `preferred_category` 欄位），決定以「整個 DB 重設」
> 取代逐步遷移。
> 建立日期：2026-09-20

---

## 目錄

- [一、重設前的確認事項](#一重設前的確認事項)
- [二、重設步驟](#二重設步驟)
  - [步驟 1：刪除所有資料表](#步驟-1刪除所有資料表)
  - [步驟 2：重建表結構](#步驟-2重建表結構)
  - [步驟 3：匯入文章](#步驟-3匯入文章)
  - [步驟 4：遷移文章標籤（視情況）](#步驟-4遷移文章標籤視情況)
  - [步驟 5：匯入員工](#步驟-5匯入員工)
  - [步驟 6：收尾清理](#步驟-6收尾清理)
- [三、重設後的驗證](#三重設後的驗證)
- [四、此流程解決的問題](#四此流程解決的問題)

---

## 一、重設前的確認事項

### 1. 三個環境指向同一個 DB（⚠️ 破壞性操作）

`backend/.env` 中 `DATABASE_URL`、`DEV_DATABASE_URL`、`TEST_DATABASE_URL`
目前都是**同一條** Zeabur 連線字串（`zeabur` 資料庫）。

> **重設 = 刪光該 DB 的所有資料**：使用者帳號、點擊紀錄、like/dislike
> 反應、收件匣訊息、積分、票單、推播紀錄，全部消失。
> 若該 DB 還有正式流量在跑，請先確認目前沒有使用者正在使用。

### 2. 環境可載入檢查

所有指令都在 `backend/` 目錄下執行（腳本依 cwd 解析相對路徑）：

```bash
cd backend
python3 -m py_compile app/__init__.py   # 環境與套件可載入的快速檢查
```

### 3. 確認 `.env` 存在且已填入

`.env`（已 gitignore）需含 `FLASK_CONFIG`、`SECRET_KEY`、`DATABASE_URL`。
實際重設打的 DB 以 `DEV_DATABASE_URL`／預設 `DATABASE_URL` 為準
（腳本預設 `--config development`）。

---

## 二、重設步驟

### 步驟 1：刪除所有資料表

有 psql 的話：

```bash
psql "$DATABASE_URL" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
```

沒有 psql 改用 Python（ Working from backend/ 目錄）：

```bash
python3 -c "
from app import create_app, db
from sqlalchemy import text
app = create_app('development')
with app.app_context():
    db.session.execute(text('DROP SCHEMA public CASCADE; CREATE SCHEMA public;'))
    db.session.commit()
print('schema dropped')"
```

### 步驟 2：重建表結構

```bash
python3 scripts/sync_db.py
```

**原理**：全新空 DB 上 `create_all()` 會依目前 model 定義建立所有資料表，
`users` 表會**連同 `preferred_category` 欄位一起建立**，
`user_behavior_vectors` 表為空 → 舊的 5 維向量自然消失。

**建議一併修改** `scripts/sync_db.py` 的 `missing_user_cols`（約 60 行）加入：

```python
    missing_user_cols = [
        ('position', 'VARCHAR(100)'),
        ('preferred_category', 'VARCHAR(50)'),
    ]
```

這樣未重設的其他環境（testing／production）跑 sync_db 也有升級保險。

### 步驟 3：匯入文章

先 dry-run 預覽再正式匯入：

```bash
python3 scripts/import_articles.py article/AI_article_01.csv --dry-run
python3 scripts/import_articles.py article/AI_article_01.csv
python3 scripts/import_articles.py article/AI_article_02.csv
```

若 CSV 欄位有 `description`／`content`／`tags`／`hr_tags` 等選填欄位會一併匯入。

### 步驟 4：遷移文章標籤（視情況）

若匯入的 CSV 內容仍含**舊標籤**（5 分類時代：職場壓力、工作倦怠、
技巧、辦公室、人際關係、團隊合作、衝突處理、職涯規劃、轉型、自我成長、
職場、情緒管理、正念練習、心理韌性、運動、睡眠、飲食…），需執行一次
mapping 轉成新標籤（6 個子標籤：壓力管理、情緒覺察、職場溝通、職涯發展、
健康生活、身心平衡）：

```bash
python3 scripts/migrate_tags.py
```

> 若 CSV 已使用新標籤，此步驟為 no-op（updated_count = 0），跑一次無妨。

### 步驟 5：匯入員工

`data/frontend_users_db.csv` 目前**沒有 `role` 欄**，全部會預設 employee，
而腳本會在 hr+manager 總數為 0 時中止匯入。兩種做法擇一：

**做法 A：指定 HR email**

```bash
python3 scripts/import_employees.py data/frontend_users_db.csv --dry-run
python3 scripts/import_employees.py data/frontend_users_db.csv --hr-emails <hr的email>
```

- 匯入時會從 `raw_password` 欄位雜湊生成密碼（不會以明文存入 DB）。
- 多個 HR 用逗號分隔：`--hr-emails a@x.com,b@x.com`。

**做法 B：CSV 先加 `role` 欄位**

在 `frontend_users_db.csv` 加上 `role` 欄（合法值：`hr`／`manager`／
`employee`），再直接匯入：

```bash
python3 scripts/import_employees.py data/frontend_users_db.csv
```

### 步驟 6：收尾清理

1. **移出含明文密碼的 CSV**：
   `data/frontend_users_db.csv` 含全公司員工明文密碼，匯入完畢後建議
   移出專案資料夾（或至少加入 `.gitignore`），不要提交。
   （`data/ml_data.csv` 已刪除，員工匯入腳本其實用不到它。）
2. **舊 ML 依賴已移除**：父 repo 的 `ml/` 目錄已刪除，backend 不再
   讀取 `voluntary_risk.pkl`，無需任何還原。

---

## 三、重設後的驗證

1. **啟動後端**應無 schema 錯誤、無 `xgboost` 載入警告（已移除依賴）。

2. **文章數量正確**：

   ```bash
   psql "$DATABASE_URL" -c 'SELECT count(*) FROM articles;'
   ```

3. **員工與角色正確**：

   ```bash
   psql "$DATABASE_URL" -c \
     "SELECT role, count(*) FROM users GROUP BY role;"
   ```

   至少要有 1 位 `hr`。

4. **文章標籤符合新分類**（抽查幾筆不應出現舊標籤）：

   ```bash
   psql "$DATABASE_URL" -c \
     "SELECT DISTINCT tags FROM articles WHERE tags ~ '職場壓力|人際關係|工作倦怠' LIMIT 5;"
   ```

   預期結果 0 筆。

5. **推薦 API 煙霧測試**：登入任一員工帳號取得 JWT 後：
   - `GET /api/recommend` → 應回傳初始向量（`[0.33]×3`）版本的推薦，
     HTTP 200（不再有 5 維 vs 3 維的 `ValueError` 500）。
   - 員工端回應**不含** `turnover_risk_detected`。

6. **偏好設定煙霧測試**：

   ```
   POST /api/auth/set-preference
   Body: { "preferred_category": "壓力與情緒" }
   ```

   應回傳 success，且 `user_behavior_vectors` 出現該使用者的 3 維向量
   （`[0.1, 0.1, 0.8]`）。

---

## 四、此流程解決的問題

| 問題 | 原因 | 解決方式 |
|------|------|----------|
| Bug 1：`/api/recommend` 500 | 舊的 5 維 `UserBehaviorVector` 未做維度檢查，`cosine_similarity(1×5, N×3)` 拋 ValueError | DB 重設後向量表為空，全部從 3 維初始向量開始 |
| Bug 2：`/auth/set-preference` 500 | model 新增 `preferred_category` 但缺少 DB 遷移（`UndefinedColumn`） | 重設後 `users` 表依新 model 建立，欄位齊全；並建議補進 `sync_db.py` 保險 |

> **未接線提醒**：frontend 尚未串接 `/auth/set-preference`（屬階段 4
> 待辦），重設後未設偏好的員工推薦會走 `[0.33]×3` 初始向量，屬預期行為。

---

## 五、常用相關指令速查

```bash
# 預覽（不寫入）各匯入腳本
python3 scripts/import_articles.py article/AI_article_01.csv --dry-run
python3 scripts/import_employees.py data/frontend_users_db.csv --dry-run

# 檢查資料表結構
psql "$DATABASE_URL" -c '\d users'

# 重建所有員工行為向量（大量 like/dislike 後的維護工具）
# 路徑：POST /api/hr/actions/rebuild-vectors（HR 權限）
```
