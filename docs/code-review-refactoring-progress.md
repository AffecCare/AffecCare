# 程式碼審查修正進度追蹤

> 依據：`docs/backend-code-review.md`、`docs/frontend-code-review.md`
> 建立日期：2026-08-24
> 用途：記錄分階段修正的設計、已完成項目與未完成項目，供後續 session 接續執行。

---

## 一、工作流程規範（每階段固定）

1. **Subagent 修正** → 2. **AI 自行檢查**（讀 diff＋獨立驗證：語法／建置／煙霧測試）→ 3. **向業主回報** → 4. **業主確認 OK** → 5. **才在對應 submodule 建立 commit**

### 業主已核可的規則與決策

| 項目 | 決策 |
|------|------|
| git 權限 | 允許 AI 自行執行唯讀指令（status/diff/log）；add/commit/push 等寫入操作須逐次取得明確同意 |
| batch_weekly.py | 直接刪除（會以假文章覆蓋真模型且必然 AttributeError） |
| pytest 遷移 | 暫不處理（test_api.py 僅做契約對齊，完整改寫日後再議） |
| repo 結構 | `backend/`、`frontend/` 各自是獨立 git submodule；commit 分別在子目錄內建立 |

---

## 二、八階段總覽

| 階段 | 範圍 | 對應審查條目 | 狀態 | Commit |
|------|------|-------------|------|--------|
| 1 | backend P0/P1 安全 | 後端 1.1~1.6 | ✅ 完成 | backend `4e1c9ec` |
| 1b | 腳本 fail-safe 連動補強 | （階段1衍生） | ✅ 完成（併入上者） | backend `4e1c9ec` |
| 2 | backend P1 假數據 | 後端 二-1,2,3,4,7,8 | ✅ 完成 | backend `6d97cde` |
| 3 | frontend P0 致命 bug | 前端 2.1, 2.2, 1.1, 1.2, 6.5（含 6.3 部分） | ✅ 完成 | frontend `a270978` |
| 4 | frontend P1 API 契約＋認證 | 前端 1.3, 1.4, 2.4, 2.5, 2.6, 1.5, 5.1, 5.10 | ✅ 完成 | frontend `ff9f07a`＋`e7acfba` |
| 5 | backend P2 架構 | 後端 3.1, 3.2, 1.3, 3.4, 3.5 | ⬜ 未開始 | — |
| 6 | frontend P2 UX | 前端 1.7, 5.2, 5.11, 1.6, 3.2 | ⬜ 未開始 | — |
| 7 | backend P3 品質 | 後端 3.3, 3.7(部分), 13（不含 pytest） | ⬜ 未開始 | — |
| 8 | frontend P3 清理 | 前端 3.4, 4.x, 6.x 其餘, 三/五章其餘 | ⬜ 未開始 | — |

> 階段順序設計理由：階段 1 先改後端 `/recommend`、`/track_click` 契約（user_id 改由 JWT 取得），階段 4 前端才能對接新契約。**前端推薦功能已於階段 4 修復。**

---

## 三、各階段完成內容細節

### 階段 1：backend 安全修正（commit `4e1c9ec`）

**檔案**：`config.py`、`app/__init__.py`、`app/routes/recommend.py`、`scripts/import_employees.py`、`scripts/push_recommendations.py`、`scripts/test_api.py`、`scripts/sync_db.py`

- config.py 移除三環境寫死的 Neon 連線字串與 SECRET_KEY 預設值；新增 `validate_config()`——production 缺 `DATABASE_URL`/`SECRET_KEY` 直接 RuntimeError 拒絕啟動。
- `create_app(config_name=None)`：未指定時依 `FLASK_CONFIG` 環境變數，再無則預設 `'production'`（fail-safe）；未知名稱 raise ValueError 不再靜默 fallback。
- `/api/recommend`、`/api/track_click` 加 `@login_required`；user_id 改由 JWT 取得；員工端回應移除 `turnover_risk_detected`（僅 HR 角色可見）。**注意：`/track_click` 的 body 不再需要 user_id（傳了也會被覆寫），必要欄位剩 article_id/action/timestamp。**
- import_employees.py 移除硬編碼 email→HR 角色；改 CSV `role` 欄位（合法值 hr/manager/employee）→ `--hr-emails` 參數 → 預設 employee；hr+manager 合計 0 時預設中止匯入（`--allow-no-hr` 放行）。
- push_recommendations.py 移除寫死 HR 帳密，改 `HR_EMAIL`/`HR_PASSWORD` 環境變數或互動輸入。
- test_api.py：防護置於 `from app import ...` **之前**（因 `app/__init__.py` 匯入時即建立 gunicorn 入口實例）；預設 testing、禁止 production；登入改 email 契約＋憑證環境變數化（TEST_EMP_EMAIL 等）；recommend/track_click 測試對齊新契約。
- sync_db.py：production 需 `SYNC_DB_ALLOW_PRODUCTION=1` 才放行。

### 階段 2：backend 假數據修正（commit `6d97cde`）

**檔案**：`app/services/hr_dashboard.py`、`app/routes/hr_actions.py`、`app/models/pg_models.py`、`scripts/sync_db.py`、刪除 `scripts/batch_weekly.py`

- overview_metrics 三個假變化量改為真實期間對比：新增 `_compute_period_metrics()`，本期＝近 30 天、前期＝30~60 天前，以 `ClickLog.created_at` 過濾；**前期無資料時 change 回傳 None**（前端應顯示「無前期資料」，非 0）。
- cohort role 寫死 "General Staff"：發現 DB 無職稱欄位（CSV 有 Position 但 model 沒收）→ User 新增 `position` 欄位；cohort role 改為成員非空 position 最常見值聚合，全空顯示「未提供職稱」。
- lastActive 依 cohort 最後點擊時間真實換算（無／最近 7 天內／最近 30 天內／最近 90 天內／N 天前）。
- feedback rate 分母改為實際收到的推薦推播次數（InboxMessage type=recommendation，group_by 一次查詢）。
- 刪除 batch_weekly.py。

### 階段 3：frontend 致命 bug（commit `a270978`）

**檔案**：共 12 個（login.tsx、api.ts、InboxContext.tsx、article.$articleId.tsx、package.json 及型別錯誤相關檔案）

- 移除 login.tsx 明文印出 email+password/token、api.ts 三處 headers/body log；全 src/ 已無 console.log。
- InboxContext.markAsRead：`setSavedArticles`（未定義，點訊息即 ReferenceError）→ 改更新 `allMessages`（同時修好 5.4 Saved tab 已讀狀態）。
- /article/$articleId 外層包 `ArticlePageWrapper` + `InboxProvider`，修復 useInbox 白畫面 crash。
- build script：`tsc --noEmit && vite build`；清完全部 25 行 tsc 錯誤（未使用 import 刪除、Base UI Select onValueChange null 防護、DialogTrigger/DropdownMenuTrigger 的 asChild 改 render prop）。

### 階段 4：frontend P1 API 契約＋認證（commits `ff9f07a`、`e7acfba`）

**檔案**：共 14 個（api.ts、AuthContext.tsx、RecommendationsSection.tsx、article.$articleId.tsx、articles.tsx、cmsApi.ts、profile.tsx、history.tsx 新增、InboxSidebar/MobileSidebar、UserMenu.tsx、InboxDetail.tsx、insights.tsx、routeTree.gen.ts）

- `/recommend`：讀 `res.recommendations`；自訂 `RecommendationPayload` 型別；key/路由參數用 `article_id`；未登入不發請求。卡片以 Link state 傳遞推薦資料，並落 sessionStorage（`affeccare_rec_<id>`）供重新整理還原；文章頁對非數字 id 走 state/sessionStorage 渲染＋reactions API，數字 id 維持收件夾訊息流程。
- `/track_click`：payload 改 `article_id/action/timestamp`；靜默吞錯改 console.error；兩處發送加同生命週期防重發 guard。
- fetchWithAuth：新增 `ApiError`（帶 HTTP status）；非 JSON 回應不再吞成 `{}`；401＋有 token＋非 auth 端點 → 清 session 並轉址登入。
- AuthContext：in-flight getMe 加 cancellation（tokenRef）防幽靈登入；login 後不再重複 getMe；login 驗證 user 資料才寫入；token 失效僅本地清 session 不打 logout API；await 後比對 localStorage 一致性。
- `/auth/profile` 加 `beforeLoad: requireAuth`。
- CMS：Save as Draft 改存 draft（原寫死 published）；list/create/update/delete 錯誤顯示於 UI；openEdit 抓不到完整內容即中止（移除會清空 content 的 fallback）；動態 import 改靜態。
- 新增 `/inbox/history` 公告頁＋桌面/行動側欄入口（5.1：HR 公告員工可見）。
- 審查意見追加修正（`e7acfba`）：insights CSV 匯出雙引號跳脫；InboxDetail effect 改 cleanup-flag 防晚到回應覆蓋、復原 Share Link 按鈕與 copied 回饋；UserMenu Preferences 僅 HR 可見。

---

## 四、⚠️ 待業主執行的作業事項（程式碼無法解決）

1. **更換 Neon 資料庫密碼（急）**：舊帳密仍在 git 歷史與 `backend/data/frontend_users_db.csv`（含全部員工明文密碼）中，請儘速輪替憑證；並考慮將 data/ 移出版本控制。
2. **部署節奏**：拉取階段 2 之後的 commit 時，必須先執行 `python scripts/sync_db.py` 幫 users 表新增 `position` 欄位，否則所有 User 查詢拋 UndefinedColumn。
3. 本機 `.env`（已 gitignore）需含 `DATABASE_URL`、`SECRET_KEY`（參見 `.env.example`）；production 環境漏設會直接拒絕啟動（by design）。

---

## 五、已知遺留事項（未排入任何階段／待處理）

| 事項 | 說明 | 預計處理 |
|------|------|---------|
| test_api.py inbox 測試寫死 `"EMP001"` 收件人 | 種子資料無此 ID（實為數字），公告/推播測試可能靜默失敗 | pytest 重寫時一併處理（業主已決定暫緩） |
| `npm test` 無任何測試檔 | vitest exit 1（No test files found） | 日後補 |
| Vite build chunk >500kB 警告 | code-splitting 議題 | 未排定 |
| 各檔 console.error | 錯誤處理用，非安全問題 | 保留 |
| ~~backend 啟動警告 `No module named 'xgboost'`~~ | ~~本機環境缺套件（ml/models 載入失敗→風險分數靜默為 0）~~ | ✅ **已解決**：離職預測模型與 `ml/` 資料夾已被徹底移除，系統改為純 3 大分類推薦架構。 |

---

## 六、如何接續（給下一次 session 的指令）

下一輪從**階段 5**開始。可直接下達：

```
請根據 docs/code-review-refactoring-progress.md 接續執行階段 5
（backend P2 架構修正），
沿用相同工作流程：subagent 修正 → 你自行檢查 → 回報等我確認 → 我同意後才 commit。
```

### 階段 5 工作清單（backend，對應後端審查報告）

見總覽表：後端 3.1, 3.2, 1.3, 3.4, 3.5（**註：3.1 關於 xgboost 載入失敗與風險分數的議題，已於本次專題方向變更「移除離職預測模型並導入三大分類推薦」中提前解決並移除**，後續重構可直接跳過該部分）。

之後依序：階段 6（frontend P2）→ 7（backend P3）→ 8（frontend P3），各階段範圍見上方總覽表與兩份審查報告原文。
