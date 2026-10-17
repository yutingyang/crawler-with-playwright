# crawler-with-playwright

研究 Scribd 文件檢視器如何把 PDF 拆成「圖片層 + 文字層」渲染成 HTML，並示範用兩種方法把前三頁組回 PDF。
分析過程與發現請看 [NOTES.md](NOTES.md)。

## 安裝

```powershell
uv sync                               # 建立 .venv 並安裝相依套件
uv run playwright install chromium    # 下載 Playwright 用的 Chromium
```

## 使用

所有功能都透過同一個指令：`uv run crawler-with-playwright <command>`

| 指令 | 作用 | 產出 |
|---|---|---|
| `open` | 用有視窗的瀏覽器開啟文件並截圖 | `output/screenshot.png` |
| `fetch` | 抓前三頁的 HTML 片段、背景圖、字型、版面 CSS | `data/` |
| `build [a\|b\|all]` | 由 `data/` 組成 PDF（a = PyMuPDF、b = Chromium） | `output/method_*.pdf` |
| `compare [--no-live]` | 截線上畫面並與兩份 PDF 比對（`--no-live` 只比 A vs B） | `output/compare_p*.png`、`output/live_p*.png` |
| `probe structure` | 印出頁面結構、文字層縮放、載入的資源 | 終端機 |
| `probe fonts` | 列出檢視器載入的 ffN 網頁字型 | 終端機 |
| `all` | `fetch` → `build` → `compare` | 以上全部 |

`fetch` 需要先跑過一次，`build` 才有資料可用；`compare` 需要兩份 PDF。

## 程式結構

```
src/crawler_with_playwright/
├── config.py        設定：網址、頁數、路徑、座標換算常數
├── viewer.py        Playwright 操作：開啟檢視器、捲到某頁、截圖（隱藏工具列/橫幅）
├── fetch.py         攔截網路回應，存下頁面片段 / 圖片 / ttfs.css / 版面 CSS
├── assets.py        讀取 data/ 的資料、解析 style 與字型
├── pdf_pymupdf.py   做法 A：自己重做排版，用 PyMuPDF 畫圖片與文字
├── pdf_chromium.py  做法 B：重組 HTML + CSS，用 Chromium page.pdf() 列印
├── compare.py       PDF 點陣化、疊圖、差異比例
├── probe.py         檢視線上頁面結構與字型
└── cli.py           指令列入口（上表的子指令）
```

相依關係：`config` ← `assets` / `viewer` ← `fetch`、`pdf_*`、`compare`、`probe` ← `cli`

## 注意

Scribd 的服務條款禁止抓取文件內容，帶 token 的資源網址也是刻意的存取控制。
本專案只以前三頁示範渲染技術；IPMI 規格本身可從 Intel 官方免費取得。
