# 前端程式碼總體檢報告（Frontend Code Review）

> 檢查範圍：`frontend/src/` 目錄（routes、components、contexts、lib），並與 `backend/app/routes/` 交叉比對 API 契約
> 檢查日期：2026-08-23
> 複查日期：2026-08-24 — 所有保留項目已逐條對照程式碼驗證屬實（含實跑 `tsc --noEmit`，目前全專案 25 處型別錯誤）；經判定不需修正的項目已移除，少數不準確的描述已更正

---

## 目錄

- [一、嚴重 Bug（會 crash 或核心功能失效）](#一嚴重-bug會-crash-或核心功能失效)
- [二、安全問題（需立刻修正）](#二安全問題需立刻修正)
- [三、純裝飾／假功能（點了沒反應）](#三純裝飾假功能點了沒反應)
- [四、寫死資料（未實作 API、只顯示固定結果）](#四寫死資料未實作-api只顯示固定結果)
- [五、資料流／邏輯斷裂](#五資料流邏輯斷裂)
- [六、死碼與維護性問題](#六死碼與維護性問題)
- [七、建議修正優先順序](#七建議修正優先順序)

---

## 一、嚴重 Bug（會 crash 或核心功能失效）

### 1.1 `setSavedArticles` 未定義 — 點擊任何訊息即 ReferenceError

**位置**：`frontend/src/components/inbox/InboxContext.tsx:75`

- `markAsRead` 內呼叫了不存在的 `setSavedArticles`（`savedArticles` 是第 68 行的 derived const，從未宣告對應 state，TypeScript 回報 TS2304 `Cannot find name 'setSavedArticles'`；`tsc --noEmit` 實測失敗）。
- 因為 `package.json` 的 build 只有 `vite build` 不跑 tsc，此錯誤會直接上線。
- 後果：使用者點擊任何訊息時，第 74 行 `setRecommendations` 執行後即丟出 `ReferenceError`，後續的 `setHistoryMessages`、`setUnreadCount`、以及真正的後端 `inboxApi.markAsRead(id)` **永遠不會被呼叫** → 後端永不標記已讀、未讀數永不減少、已讀狀態重新整理後就還原。

**修正方向**：`savedArticles` 由 `allMessages` 衍生，`markAsRead` 應改為更新 `allMessages`（或 recommendations/historyMessages 的資料來源 state），移除對 `setSavedArticles` 的呼叫。

### 1.2 `/article/$articleId` 在 Provider 外使用 `useInbox` — 開啟即 crash

**位置**：`frontend/src/routes/article.$articleId.tsx:75-78`

- 此路由不在 `/inbox` layout 下（root 只有 `AuthProvider`；`InboxProvider` 全專案僅出現在 `routes/inbox/route.tsx:17`），卻渲染 `InboxDetail`，而 `InboxDetail.tsx:23` 呼叫 `useInbox()`。
- `InboxContext.tsx:106-111` 在無 Provider 時會 throw `'useInbox must be used within an InboxProvider'` → 開啟 `/article/xxx` 頁面必定白畫面。

**修正方向**：將 `toggleSave`/`savedMessageIds` 由 props 傳入 `InboxDetail`，或在此 route 外層包 `InboxProvider`。

### 1.3 `/recommend` API 契約三重不符 — Landing page 推薦區從未顯示過

**位置**：`frontend/src/components/RecommendationsSection.tsx:14-23, 47`

- 前端呼叫 `GET /recommend` **不帶 `user_id`**，但後端 `recommend.py:45-52` 要求必帶，缺參數直接回 400。
- 前端讀 `res.data`，但後端回傳的 key 是 `recommendations`（`recommend.py:57-61`）。
- `RecommendationItem extends InboxMessage` 期望 `id/sender/date/read/tags`，但後端推薦項目只有 `{article_id, title, content, tags, score}`（註：`turnover_risk_detected` 已於本次重構徹底移除），因此第 47 行 `String(item.id)` 是 `"undefined"`。
- 三重錯誤疊加：請求永遠 400 → `.catch(() => setRecommendations([]))` → render null，「Recommended for You」區塊**從未成功顯示過**。

**修正方向**：改用 `GET /recommend?user_id=...`（登入後從 current user 取得）、讀 `res.recommendations`、以 `article_id` 作為 key 與路由參數。

### 1.4 `trackClick` payload 缺 3 個必要欄位 — 點擊回饋永遠收集不到

**位置**：`frontend/src/lib/api.ts:75-79`、`frontend/src/routes/article.$articleId.tsx:33`

- `trackClick` 只送 `{article_id, click_type?}`，但後端 `/track_click`（`recommend.py:90-97`）必要欄位是 `user_id, article_id, action, timestamp`，缺欄位回 400。
- 前端 `.catch(() => {})` 靜默吞掉 → 行為回饋資料永遠收集不到，**推薦引擎的 feedback loop 形同虛設**。

**修正方向**：補齊 `user_id`、`action`、`timestamp` 欄位（後端若改從 JWT 取 user_id 更佳，見後端報告 1.2）。

### 1.5 CMS 文章管理三連問題 — 資料完整性風險

**位置**：`frontend/src/routes/admin/articles.tsx`

- 「Save as Draft」按鈕實際行為是**發布**（`articles.tsx:69-77` 的 `handleCreate` 寫死 `status: 'published'`，文案與行為矛盾）。
- API 錯誤被靜默吞掉（`cmsApi.ts` 各方法 catch 後回傳 null/[]/false），HR 不會知道儲存失敗。
- 編輯文章時的 fallback 邏輯（`articles.tsx:138-140` 的 `|| ''`／`|| []`）可能以空值覆蓋、**清空文章內容**。

**修正方向**：分流 draft/publish 兩個 action；錯誤必須顯示；fallback 改為保留原值而非空值。

### 1.6 API 載入失敗被偽裝成「沒有資料」

**位置**：`frontend/src/routes/admin/control-center.tsx:26-37, 256-261`、`frontend/src/routes/admin/support.tsx:28-38, 77-82`

- `fetchStats` / `fetchTickets` 失敗時 state 維持空陣列，畫面顯示「目前尚無回饋資料」／「目前沒有諮詢票單」，把「載入失敗」偽裝成「真的沒資料」。
- 對照 `insights.tsx:157-163` 至少有失敗處理，但錯誤文案是開發者向的（叫 HR 去終端機 Ctrl+C 重啟 Flask），不應出現在正式 UI。
- 另外 `control-center.tsx:39-46`：`fetchModelPerf` 失敗只 `console.error`，`modelPerf` 維持 null，卡片**永遠卡在「載入指標中...」**，無錯誤或重試狀態。

**修正方向**：每個資料載入都需區分 loading / error / empty 三種狀態並分別渲染。

### 1.7 文章列表最多只顯示 20 筆，無分頁 UI，靜默截斷

**位置**：`frontend/src/lib/cmsApi.ts:28`、`frontend/src/routes/admin/articles.tsx:302-370`、後端 `backend/app/routes/cms.py:33-37`、`backend/app/services/cms.py:62-74`

- 後端 list API 支援分頁（預設 `per_page=20`，按 `created_at` 倒序）與 `search`/`tag`/`status` 過濾參數，但前端不帶參數只拿第一頁 20 筆，也沒有任何分頁或搜尋 UI，並丟棄回傳的 `total`/`pages` metadata。
- 文章超過 20 篇後，admin 將**永遠看不到較舊的文章**，且無任何提示。後端辛苦做的 search/tag/status 過濾也全部沒被使用。

**修正方向**：呼叫 `GET /cms/articles?page=&per_page=&search=&status=` 並補分頁 UI；至少也應用回傳的 `total` 顯示「共 N 篇」。

---

## 二、安全問題（需立刻修正）

### 2.1 使用者密碼被明文 console.log

**位置**：`frontend/src/routes/auth/login.tsx:53`

- `console.log('Calling login with:', { email, password })` — **使用者密碼明印到瀏覽器 console**。
- 第 55 行登入成功後又把 token 印到 console。

### 2.2 每個請求都 log 含 Bearer token 的完整 headers 與 response body

**位置**：`frontend/src/lib/api.ts:21, 23, 32`

- `fetchWithAuth` 對每個請求 `console.log` 完整 request headers（含 `Authorization: Bearer <token>`）與完整回應 body，且無 dev/prod 環境判斷——正式環境也會輸出，持續洩漏 token 與使用者資料。

**修正方向**：2.1 與 2.2 的 log 全數移除，或以 `import.meta.env.DEV` 包裹。

### 2.3 JWT 與角色存 localStorage，前端 guard 可被竄改

**位置**：`frontend/src/contexts/AuthContext.tsx:27, 56`、`frontend/src/lib/authGuard.ts:19, 22-30, 40-50`、`frontend/src/lib/api.ts:4`

- JWT token 存 `localStorage`（`auth_token`）：任何 XSS 都可直接竊取 token，較安全做法是 httpOnly cookie。
- `requireRole` 完全信任 localStorage 的 `auth_user` JSON——使用者在 devtools 把 `role` 改成 `"hr"` 即可通過所有前端 admin guard（admin layout 會完整渲染，只有 API 資料被後端擋）。角色從未向後端驗證。
- `auth_token` 與 `auth_user` 是兩把獨立 key，無一致性保證（只清其中一把會出現矛盾狀態）。
- `requireAuth`（`authGuard.ts:32-38`）只檢查 token「存在」，不解碼 JWT 檢查 `exp`——過期使用者可通過 guard 進入受保護頁面，之後所有 API 呼叫才失敗。

**修正方向**：前端 guard 僅作 UX 引導，真正權限一律靠後端 `role_required`；長期應改 httpOnly cookie。

### 2.4 登出後 in-flight `getMe` 造成「幽靈登入」

**位置**：`frontend/src/contexts/AuthContext.tsx:31-46`

- `initAuth` 中 in-flight 的 `getMe` 沒有 cancellation 控制：若使用者在其 resolve 前登出（logout 已清空 token/user/localStorage），之後 `getMe` resolve 會執行 `setUser(res.data)` + `setUserSession(res.data)`，把 user「復活」並把 `auth_user` 重新寫回 localStorage。
- 結果：已登出狀態下 user state 非 null、`auth_user` 殘留；由於 `requireRole` 只讀 `auth_user`，admin guard 仍會通過。

**修正方向**：加 cancellation flag（如 `useRef` 或 AbortController），logout 後 resolve 不得再寫入 state/localStorage。

### 2.5 `/auth/profile` 完全沒有 route guard

**位置**：`frontend/src/routes/auth/profile.tsx:10-12`

- 未登入者可直接開啟更改密碼頁，submit 後只收到後端 401 的 generic error，不會被導向登入頁（對比 `/inbox` 與 `/admin` 都有 guard）。

**修正方向**：加上 `beforeLoad: requireAuth`。

### 2.6 無 401 全域處理、Error 不帶 status code

**位置**：`frontend/src/lib/api.ts:34-36`

- token 過期後所有 API 只丟 generic Error，不會自動登出或導回登入頁（只有 App 啟動時的 `getMe` 會觸發 logout）。使用者在 session 中 token 過期後會卡在不斷失敗的頁面。
- Error 只帶 `message` 不帶 HTTP status code，呼叫端無法區分 401/403/409（例如 register 的「帳號已存在」無法差異化處理）。
- 回應非 JSON 時（`api.ts:25-30`，如 proxy 回傳 HTML 500 頁）被安靜吞掉成 `{}`，錯誤訊息退回 generic 字串，難以排查；也沒有 timeout/abort 機制。

---

## 三、純裝飾／假功能（點了沒反應）

### 3.1 「Forgot password?」是 `#` 連結

**位置**：`frontend/src/routes/auth/login.tsx:145-150`

- `href="#"`，沒有任何頁面或 API，密碼忘記流程未實作。

### 3.2 Inbox 搜尋框是空殼

**位置**：`frontend/src/components/inbox/InboxPageBase.tsx:69-73`

- `<input>` 沒有 `value`、沒有 `onChange`、沒有任何過濾邏輯，`/inbox` 與 `/inbox/saved` 的搜尋都無效。

### 3.3 Insights 行動按鈕是固定文案輪播且無 onClick

**位置**：`frontend/src/routes/admin/insights.tsx:363-373`、後端 `backend/app/services/hr_dashboard.py:399-413`

- 警示標題/描述是依資料動態產生的，但 action 按鈕文字是後端 4 句固定文案按索引輪播出現（`action_templates[idx % len(action_templates)]`），與該則警示的內容無關——後端註解自承「建立多樣化文案庫，避免看起來像機器假資料」，即刻意偽裝成智慧建議。
- 且前端這顆按鈕**沒有 onClick**，純裝飾。

### 3.4 Control Center 的 `top_n` 輸入框與推播對象選擇是純裝飾

**位置**：`frontend/src/routes/admin/control-center.tsx:51-54, 104`

- `top_n` 輸入框是非受控元件（`defaultValue={3}`、無 state 綁定），`handlePush` 寫死 `body: { target: "all", top_n: 3 }`；推播對象也只有寫死的 `All Employees` Badge，無法選部門。
- 但後端 `/hr/actions/push-recommendations`（`backend/app/routes/hr_actions.py:40-71`）完整支援 `target: "department"` + `dept_name` 與 `top_n` 參數——接線修復成本極低。

### 3.5 Redirect-return 機制是死的

**位置**：`frontend/src/lib/authGuard.ts:35, 43`

- `requireAuth`/`requireRole` 會帶 `search: { redirect: window.location.pathname }` 導向登入頁，但 `login.tsx` **從未讀取這個參數**，登入成功後也不會回到原頁面。

---

## 四、寫死資料（未實作 API、只顯示固定結果）

### 4.1 mock-data.ts 整檔死碼

**位置**：`frontend/src/lib/mock-data.ts:3-71`

- 整檔是寫死的假資料：`RECOMMENDATIONS`（3 筆假訊息，含寫死日期 `'10:42 AM'`、`'Yesterday'`、`'Mar 4'`、寫死 sender、寫死全文）、`SAVED_ARTICLES`（2 筆）、`HISTORY_MESSAGES`（2 筆）、`ALL_MESSAGES`。
- grep 全專案**沒有任何 import**，屬於殘留死碼，但內容會誤導開發者。應刪除。

### 4.2 AnimatedList 預設渲染 15 個假項目

**位置**：`frontend/src/components/AnimatedList.tsx:43-59`

- 預設 `items` prop 寫死 `'Item 1'` ~ `'Item 15'`；若呼叫端不傳 items 會渲染 15 個假項目。
- 實際上 `AnimatedList` default export 全專案沒人用，只有 `AnimatedItem` 被 `InboxPageBase` 使用——整個 list 元件也是死碼。

---

## 五、資料流／邏輯斷裂

### 5.1 HR 公告員工永遠看不到

**位置**：`frontend/src/components/inbox/InboxContext.tsx:27, 90`、`frontend/src/routes/inbox/route.tsx:31-32`

- `historyMessages`（announcement/system 類訊息）被 API 層分類、被 Context 暴露，但**沒有任何頁面渲染它**：routes 只有 index/saved/support，沒有 `/inbox/history`；`InboxSidebar.tsx` 也只有 3 個連結。
- 後果：HR 用 `AnnouncementComposer` 發的公告，員工端**永遠看不到**。
- 連帶死碼：`route.tsx:31-32` 檢查 `/history` 的分支永遠不成立、`types.ts:12` 的 `'history'` tab 型別殘留。

### 5.2 登入導向繞圈

**位置**：`frontend/src/routes/auth/login.tsx:26-32, 56`、`frontend/src/routes/auth/register.tsx:70`

- `handlePasswordSubmit` **無條件**導向 `/admin/dashboard`（包括 employee），同時 `useEffect` 又依 role 導向（hr→dashboard、其他→/inbox）→ employee 登入先被導到 `/admin/dashboard`，再被 admin guard 彈回 `/inbox`，多一次無意義 redirect。
- register 成功後導向 `/auth/login`，但 HR 本身仍在登入狀態，login 頁的 useEffect 又會立刻把 HR 彈回 `/admin/dashboard` → 詭異的繞圈導航；且建立成功後沒有任何成功提示。

**修正方向**：登入成功後依 `user.role` 單一來源導向；register 成功改顯示成功提示並留在原頁。

### 5.3 未讀數歸屬錯誤

**位置**：`frontend/src/components/inbox/InboxSidebar.tsx:37-43`（同 `MobileSidebar.tsx:43-49`）

- `unreadCount` 來自後端不分 type 的全部未讀（含看不到的公告/系統訊息），但 badge 只掛在「Recommendations」項目上，數字與頁面內容不符。

### 5.4 Saved tab 已讀狀態永不更新

**位置**：`frontend/src/components/inbox/InboxContext.tsx:68, 70-84`

- `savedArticles` 由 `allMessages` 衍生，但 `markAsRead` 不更新 `allMessages` → 已讀訊息在 Saved tab 永遠呈現未讀樣式（且實際上因 1.1 的 crash 連 markAsRead 都中斷）。

### 5.5 dislike 取消時計數錯誤

**位置**：`frontend/src/components/inbox/InboxDetail.tsx:59-61`

- 取消自己的反應時固定 `likes: prev.likes - 1`；若取消的是 dislike，應減 `dislikes` 卻減了 `likes`，顯示計數會錯。

### 5.6 `/inbox/support` 行動裝置無法導航

**位置**：`frontend/src/routes/inbox/support.tsx`

- 此頁沒有渲染 `MobileNav`（漢堡選單只在 `InboxPageBase.tsx:61` 出現）→ 行動裝置進入 `/inbox/support` 後無法開啟側欄選單，被困在頁面中。

### 5.7 Search param 驗證鬆散

**位置**：`frontend/src/routes/inbox/index.tsx:11-15`（同 `saved.tsx:11-15`）

- `Number(search.id)` 對非數字回 `NaN` 不驗證（`InboxPageBase.tsx:37` 會 `setSelectedId(NaN)` → detail 永遠找不到項目）；`id=0` 被 falsy 判斷吃掉；`urlId` 從有變無（手動改網址）時 `selectedId` 不會清空。
- 若 `?id` 指向的訊息不在當前 tab 的 items 裡（如公告 id），mobile 上列表隱藏、detail 顯示空 placeholder，畫面近乎全空。

### 5.8 Support 頁分頁切換有 race condition

**位置**：`frontend/src/routes/admin/support.tsx:24-38`

- `useEffect` 依 `activeTab` 重新 fetch，沒有 abort/stale-response 防護，快速切換「待回覆／已回覆／全部」時，較慢的舊回應可能晚到並覆蓋新分頁的資料。

### 5.9 `hrApi.ts` 型別與後端回傳結構完全不符

**位置**：`frontend/src/lib/hrApi.ts:3-30`；後端 `backend/app/services/hr_dashboard.py:163-175`

- `DashboardOverview` 宣告為扁平欄位（`company_stress_index` 等），但後端實際回傳巢狀結構 `{total_departments, departments, top_tags, overview_metrics: {...}}`——即使未來接上，路徑也對不上。
- `DepartmentData`（`risk/trend/score`）與後端實際的 `{department, total_employees, active_users, usage_rate, total_clicks, top_category}` 完全對應不起來；`RecentActivity` 更是後端根本沒有任何端點回傳的想像型別。這些型別是早期 mock 時代的殘留，且 `getDashboardOverview`/`getDepartmentData`/`getTrends` 全專案無人呼叫，會誤導後續開發者。

### 5.10 AuthContext 冗餘請求與邊界問題

**位置**：`frontend/src/contexts/AuthContext.tsx:31-46, 48-60`

- `useEffect` 依賴 `[token]`：`login()` 成功後 `setToken(newToken)` 會觸發 effect **再呼叫一次 `getMe()`**——但 login 回應已含 user 資料，等於每次登入都多一次冗餘網路請求；若這次 `getMe` 恰好失敗（網路抖動），`catch` 會呼叫 `logout()`，**把剛登入成功的使用者立刻登出**。
- `login()` 只驗證 token 存在、不驗證 `userData`：若後端回應缺 `user`，`JSON.stringify(undefined)` 為 undefined → `localStorage.setItem('auth_user', undefined)` 存成字串 `"undefined"`，之後 `JSON.parse` 永遠失敗。
- `getMe` 失敗（token 已無效）時呼叫 `logout()`，而 logout 會拿這支「剛驗證失敗的 token」再呼叫一次 `/auth/logout` API（必然再失敗）→ 冗餘網路請求；token 已知無效時應直接清理 local session。

### 5.11 密碼規則三處不一致

**位置**：`frontend/src/routes/auth/profile.tsx:35-38` vs `frontend/src/routes/auth/register.tsx:55-58` vs 後端 `backend/app/services/auth.py:173, 217`

- profile 改密碼要求 ≥8、註冊要求 ≥6、後端一律 ≥6。前端 profile 比後端嚴，造成「前端擋下但後端允許」的矛盾。

---

## 六、死碼與維護性問題

### 6.1 `router.tsx` 整檔死碼，且 auth context 從未生效

**位置**：`frontend/src/router.tsx:5-23`、`frontend/src/main.tsx:11-15`

- `getRouter()` **從未被使用**：真正的入口 `main.tsx:5-9`（index.html 引用）自己 `createRouter`，且不含 `context`。因此 `router.tsx` 的 `context: {...getAuthContext()}` 從未生效，`getAuthContext()`（`authGuard.ts:52-58`）只有這個死檔案在引用。
- 兩個檔案都對 `@tanstack/react-router` 做 `declare module { interface Register { router: ... } }`（`typeof router` vs `ReturnType<typeof getRouter>`）——實測 tsc 不會因此報錯（兩個型別解析結果相同，interface merging 靜默通過），但屬重複維護點。
- 即使被使用，`getAuthContext()` 只在 router 建立當下求值一次，登入/登出後不會更新 → stale snapshot。

### 6.2 `InboxLayout.tsx` 死碼

**位置**：`frontend/src/components/inbox/InboxLayout.tsx:1-29`

- 整個元件無人使用；`inbox/route.tsx:37-52`（`InboxLayoutWrapper`）內聯了完全相同的 layout markup——同一份排版邏輯存在兩份。

### 6.3 InboxDetail 殘留未使用的 import 與 state

**位置**：`frontend/src/components/inbox/InboxDetail.tsx:5, 19`

- `Share2`、`Check` import 與 `copied/setCopied` state 完全未使用（分享功能被拔掉的殘跡，TS6133）。

### 6.4 Admin 側欄選單複製貼上

**位置**：`frontend/src/routes/admin/route.tsx:43-99` 與 `138-194`

- 桌機側欄與手機 Sheet 選單整段複製貼上（兩份相同的 nav），日後加選單項要改兩處。

### 6.5 Build 不跑型別檢查

**位置**：`frontend/package.json:10`

- `build` 只是 `vite build`，**不執行 tsc**，所以上述所有 TypeScript 錯誤（含 1.1 的 `setSavedArticles` ReferenceError）都不會在建置時被擋下。
- 實測：`npx tsc --noEmit` 目前以 exit code 2 失敗，全專案共 25 處型別錯誤（`setSavedArticles` 未定義、多處未使用變數、admin 頁 Select `onValueChange` 型別不符等），但 build 照常成功。
- **修正方向**：build script 改為 `tsc --noEmit && vite build`（或 `tsc -b`），讓型別錯誤在 CI/建置階段就被發現。

---

## 七、建議修正優先順序

| 優先 | 項目 | 對應條目 |
|------|------|----------|
| P0 | 移除密碼／token 的 console.log | 2.1、2.2 |
| P0 | 修正 `setSavedArticles` ReferenceError（已讀功能全壞） | 1.1 |
| P0 | 修正 `/article/$articleId` Provider 外 crash | 1.2 |
| P0 | build 加入 tsc 型別檢查 | 6.5 |
| P1 | `/recommend` 與 `/track_click` API 契約修正（推薦系統等於沒運作） | 1.3、1.4 |
| P1 | 幽靈登入 race condition、401 全域處理、profile 加 guard | 2.4、2.5、2.6 |
| P1 | CMS「Save as Draft 實為發布」與資料完整性 | 1.5 |
| P1 | HR 公告員工看不到（補 `/inbox/history` 或併入列表） | 5.1 |
| P2 | 文章分頁（超過 20 篇即隱形資料遺失） | 1.7 |
| P2 | 登入導向繞圈、密碼規則三處不一致 | 5.2、5.11 |
| P2 | 載入失敗／空資料狀態區分、Inbox 搜尋實作 | 1.6、3.2 |
| P3 | Control Center top_n／部門推播接線 | 3.4 |
| P3 | 死碼清理（mock-data、AnimatedList、router.tsx、InboxLayout、InboxDetail 殘留 import） | 4.1、4.2、6.1、6.2、6.3 |
| P3 | 其餘 UX 不一致與雜項 | 三、五、六章其餘各條 |
