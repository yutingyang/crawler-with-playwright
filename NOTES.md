# Scribd 文件渲染分析筆記

對象：<https://www.scribd.com/document/4026761/Intelligent-Platform-Management-Interface-Specification-v1-0>
（IPMI v1.0 規格，共 205 頁）

## 1. 環境

- `uv init` 建立專案（Python 3.12），`uv add playwright pymupdf beautifulsoup4 pillow`
- `uv run playwright install chromium`

## 2. Scribd 怎麼顯示 PDF

瀏覽器拿不到原始 PDF。每一頁是伺服器事先轉好的兩個檔案，捲到附近時才載入：

```
pages/5-9f39a990ea.jsonp?token=...   ← 該頁的 HTML 片段
images/5-9f39a990ea.jpg?token=...    ← 該頁的背景圖（實際是 webp）
```

- `.jsonp` 內容是 `window.page5_callback(["<div class=\"newpage\" ...>"])`
- 第 1 頁不需 token；之後的頁面帶有會過期的 JWT token（存取控制）

每頁分兩層疊在一起：

```html
<div class="newpage" style="width:902px; height:1167px">
  <div class="text_layer">                       <!-- z-index 2：真正的文字 -->
    <div class="ff12" style="font-size:157px">   <!-- ffN = 字型 -->
      <span class="a" style="left:1293px; top:1241px">Intelligent Platform Management</span>
  </div>
  <div class="image_layer">                      <!-- z-index 1：線條、表格框、圖 -->
    <img class="absimg" src="…/1-xxx.jpg" style="left:26px; top:10px; width:876px; height:1157px; clip:rect(…)">
  </div>
</div>
```

- **圖片層幾乎是空白的**（第 1 頁只有 1.9 KB），只有框線和底線。看得到的字是文字層畫的，不是 OCR 那種隱形文字。
- **字型**：`ff0`～`ff21` 是從原 PDF 抽出的子集字型，以 base64 data URI 寫在 `ttfs.css` 裡。它們不會出現在網路請求清單中，而且 `ttfs.css` 是跨網域檔案，頁面內的 JS 讀不到規則，只能直接攔截網路回應。
- **逐字定位**：表格標題這類文字會用 `letter-spacing` 加上巢狀 `span.l`（負的 `margin-left`），並用 `span.w` 或 `wN`（固定寬度）做欄位間的空白。
- **圖片拼圖（sprite）**：第 3 頁是一張 png 被 7 個 `<img>` 共用，每個 `<img>` 用 `clip: rect(top right bottom left)` 只顯示其中一塊。

這種做法的好處：原始 PDF 不外流、文字可以選取與搜尋（SEO）、一頁一頁載入，205 頁也開得快。原理和 pdf2htmlEX 相同。

## 3. 座標換算

| 圖層 | 原始單位 | → 頁面 px | → PDF pt |
|---|---|---|---|
| 文字 `<span left top>` | 頁面座標的 5 倍 | × 0.2（`.text_layer { transform: scale(0.2) }`） | × 612/902 |
| 圖片 `<img left top>` | 頁面 px | 不變 | × 612/902 |

- **0.2**：實際量過。`left:1975` × 0.2 = 395px，和 Chromium 量到的位置一致。
- **612/902**：902 × 1167 px 約等於 106 dpi 下的 8.5 × 11 吋，也就是 US Letter，寬 612pt。
- **基線**：`span` 的 `top` 是文字框上緣，而 `line-height: 1`，所以基線 = `top + (1 + ascender + descender) / 2 × font-size`（descender 為負值）。Arial 約是 0.85 倍字級。
- PyMuPDF 和瀏覽器一樣以左上角為原點，y 不需翻轉。

## 4. 兩種組回 PDF 的做法

| | A：PyMuPDF 自己排版 | B：Chromium `page.pdf()` |
|---|---|---|
| 做法 | 解析 HTML，自己算每個字的位置，畫圖片與文字 | 把片段 + 檢視器 CSS + 字型放回一個 HTML，交給瀏覽器列印 |
| 要處理的細節 | 字寬、letter/word-spacing、`span.l` 和 `span.w`、clip 裁切、基線 | 只需縮放到 Letter（902px → 816px） |
| 程式量 | 多 | 少 |
| 準確度 | 取決於排版模擬得多準 | 與線上畫面一致 |
| 彈性 | 可只取文字、換字型、改成隱形文字層 | 只能靠 CSS 調整 |

## 5. 除錯過程中的發現

### 5.1 透明 png 變成黑塊（A）

第 3 頁的 sprite png 有透明背景，用 `convert("RGB")` 後透明區域變成黑色。改用 `convert("RGBA")` 保留透明度即可。

### 5.2 I2C 中間空了一大段（A、B 都有）

```
span left:571   "C is a two-wire ... IPMB is a subset of the I"   ← 字是一個接一個排出來的
span left:3289  "2"（上標）                                       ← 固定在絕對位置
span left:3311  "C bus/protocol and was"                          ← 固定在絕對位置
```

行尾的 `I` 沒有自己的座標，位置取決於前面整句排起來的寬度。當初誤以為 ffN 字型沒有載入，改用 Times New Roman 代替。Times 比原字型窄，整句累積少了大約 246 個單位（約 33pt），而 `²C` 固定在原位，中間就空出一段。

| | `I` 右緣 | `²` 左緣 |
|---|---|---|
| 線上（真正的 ff4 字型） | 3280 | 3289 |
| 用 Times 代替 | 約 3043 | 3289 |

修正方式：從 `ttfs.css` 解出真正的 TTF。A 用 `pymupdf.Font(fontbuffer=…)` 載入，B 把 `ttfs.css` 放進 HTML。所有左右對齊段落的行尾也因此一起對齊了。

### 5.3 和線上畫面截圖比對

| 頁 | 線上 vs A | 線上 vs B | A vs B |
|---|---|---|---|
| 1 | 1.5% | 1.5% | 0.0% |
| 2 | 4.3% | 0.0% | 0.0% |
| 3 | 2.0% | 0.4% | 0.1% |

（比例 = 差異像素 ÷ 文字和線條的像素，先模糊 1.5px 再比，以忽略抗鋸齒造成的抖動）

1. **截圖被網站介面擋住**：第一次比對時第 1 頁差了 35%，原因是 cookie 橫幅和 Download 工具列蓋在截圖上。現在截圖前會把文件以外所有 `fixed` 和 `sticky` 元素隱藏。
2. **`&nbsp;` 少算字距（A 的 bug，已修正）**：標題後面那段文字的第一個字元是 `\xa0`。CSS 的 `word-spacing` 對 `\xa0` 也有效，A 原本只對一般空白加。偏移量完全吻合：`word-spacing:26` × 0.2 × 612/902 = 3.53pt，實測也是 3.53pt。修正後第 3 頁 A vs B 從 1.5% 降到 0.1%。
3. **剩下的差異是 1 像素取樣誤差**：第 2、3 頁的差異集中在頁底那條橫線。A 先把圖片裁成 clip 範圍再貼上，B 是整張貼上再用裁切路徑遮掉邊緣。看得到的範圍相同，A 的位置也和理論值一致（誤差 0.01pt 以內），但像素格線的起點差了 1 個原始像素，點陣化時一條 1 像素的線就可能落到相鄰的那一列。如果要完全一致，可以把 A 改成「整張貼上再裁切」。
4. **第 1 頁的 1.5%**：A 和 B 相同，是 Chromium 與 MuPDF 繪製字體邊緣的方式不同。

## 6. 注意事項

Scribd 的服務條款禁止抓取文件內容，資源網址上的 token 是刻意的存取控制。本專案只用前三頁示範技術；這份 IPMI 規格本身可以從 Intel 官方免費下載。
