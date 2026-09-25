# Threads iRent 負評蒐集工具

## 每次最多 30 篇與 Word 匯出

雙擊 `start.cmd`，登入後回到命令視窗按 Enter。跨所有搜尋詞最多處理 **30 篇不重複貼文**，達上限立即停止繼續搜尋；負評初篩在這 30 篇之內進行，因此負評結果可能少於 30 篇。Threads 可能一次載入更多頁面內容，此上限限制工具收錄處理的篇數，無法解除平台的流量或登入限制。

完成後自動開啟 `output/results.docx`。每則依序編號，放入取得的評論文字（不是 80 字標題），下一段放可點擊的原文網址。來源未展開的內容仍可能不完整。重新執行前請先關閉上次的 Word 結果，以免無法覆寫。

可用 `python threads_irent.py --login --max-posts 30` 執行。程式會顯示「已讀取 X/30 篇」及疑似負評數量。Ctrl+C 中止時仍會嘗試匯出已取得的資料。

搜尋 iRent 相關公開貼文，以寬鬆關鍵詞篩選**疑似負評**，去重後依首次發現順序列出「編號、標題、網址」。貼文沒有獨立標題，標題取內文前 80 字。可抓到的公開回覆若有獨立貼文網址也會收錄，但不會逐篇展開所有留言。

## Windows 使用

需要 Python 3.10 以上及 Google Chrome。雙擊 `start.cmd`：首次安裝 Playwright，開啟獨立 Chrome 視窗。自行登入 Threads，再回到命令視窗按 Enter，工具開始搜尋；完成後會開啟結果清單。密碼不會交給程式，登入狀態存在本機 `.threads-profile`，請勿分享此資料夾。

也可在 PowerShell 執行：

```powershell
python -m pip install -r requirements.txt
python threads_irent.py --login
# 已登入後可直接執行
python threads_irent.py
# 使用 Edge
python threads_irent.py --channel msedge --login
# 加大載入範圍、指定搜尋詞與新增負評詞
python threads_irent.py --query irent --query "irent 客服" --scrolls 30 --negative-word "服務很差"
```

每次執行會覆寫 `output` 下的結果；保留多次結果時用 `--output output-0926` 指定另一個目錄。

- `results.html`：可直接點開的編號清單，含網址、命中詞與擷取文字。
- `results.txt`：可複製的編號、標題、網址。
- `results.json`：結構化結果及擷取狀態。
- `raw.json`：本次讀到的原始資料，可能重複，供重新分析。

## 官方 API 模式（可選）

有 Meta Threads API Token 且具備 `threads_keyword_search` 權限時，可在本機設定環境變數 `THREADS_ACCESS_TOKEN`，然後執行：

```powershell
python threads_irent.py --source api --pages 5
```

使用 Meta 的 `/keyword_search`，搜尋類型為 `RECENT`；每個搜尋詞獨立分頁，合併結果依發現順序，並非跨搜尋詞的全域時間排序。Token 不會寫入輸出，也請勿貼到公開檔案。

參考：[Meta 官方 API 搜尋範例](https://www.postman.com/meta/threads/request/m9j4i2x/search-for-threads-posts)。

## 範圍與限制

這是關鍵詞初篩，不是已人工查證的情緒分析。「不爛」「沒有故障」或談論其他品牌的文章也可能命中；未使用收錄詞彙的反諷或抱怨可能漏掉。保留命中詞及原文供人工確認。

網頁模式依賴 Threads 當前頁面結構，可能含作者、時間、按鈕等介面文字；引用文章、未展開的長文、圖片文字及影片語音可能漏抓。搜尋顯示哪些文章由 Threads 決定，無法保證找出「全部負評」。

遇到登入牆、驗證或限制時請在可見瀏覽器自行處理，工具不繞過限制；連續無法讀取時停止並保存紀錄。空結果不等於沒有負評。API 模式需要自己的有效權限，不能用網頁登入代替 API 授權。

## 驗證

```powershell
python -m unittest discover -s tests -v
```

測試涵蓋網址驗證、去重、品牌及關鍵詞篩選、HTML 安全輸出、API 分頁及失敗保存邏輯。真人登入後的完整擷取仍需實際帳號驗證。
