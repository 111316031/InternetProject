# E-Game Center 遊戲娛樂大廳 🎮

E-Game Center 是一個基於 Python Pygame 開發的遊戲大廳，整合了心理博弈卡牌遊戲 **E-Card (國王與奴隸)** 以及 **Restricted RPS (限定剪刀石頭布)**。專案結合了高效的 **C 語言 TCP 連線核心 (Winsock2/POSIX)** 與 Python 接口，支援單機 AI 對戰與網路連線模式。

---

## 🏗️ 專案架構 (Project Structure)
專案遵循 **Clean Architecture** 與模組化設計：
```
InternetProject/
├── src/
│   ├── common/                  # 通用模組 (UI 元件、網路連線管理)
│   │   ├── network_manager.py
│   │   └── ui_components.py
│   ├── connection/              # C 語言 TCP 核心連線庫與 Python 接口
│   │   ├── connection.py        # Python Wrapper
│   │   ├── domain/              # 領域層 (抽象 Socket 定義與介面)
│   │   └── infrastructure/      # 基礎建設層 (平台 Winsock2/POSIX 具體實作)
│   ├── ecard/                   # E-Card 遊戲邏輯與 UI 介面
│   └── restricted_rps/          # Restricted RPS 遊戲邏輯與 UI
├── tests/                       # 測試與 Demo 腳本
├── pyproject.toml               # uv 專案設定檔
└── main.py                      # 遊戲大廳主程式入口
```

---

## ⚡ 快速開始：使用 `uv` 管理與運行專案 (從零開始)

本專案使用 Astral 開發的超高速 Python 套件管理工具 **`uv`** 來進行環境隔離與依賴管理。以下是從零開始的完整操作指引。

### 1. 安裝 `uv`
請根據您的作業系統，在終端機執行對應的安裝指令：

* **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
* **macOS / Linux**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
* **使用 Python `pip` 安裝**（跨平台通用）：
  ```bash
  pip install uv
  ```

安裝完成後，可重啟終端機並執行 `uv --version` 驗證是否安裝成功。

### 2. 初始化專案環境與安裝依賴
進入專案根目錄，執行以下指令：
```bash
uv sync
```
* **說明**：這個指令會讀取 `pyproject.toml` 與 `uv.lock`，自動在專案根目錄下建立虛擬環境（`.venv/`）並安裝所有必備套件（如 `pygame`），確保每個人使用的環境與版本完全一致。

### 3. 編譯 C 語言連線核心庫 (DLL)
專案的網路連線模組使用 C 語言編譯的動態庫，以提供最佳性能。
我們已經寫好了 [Makefile](file:///D:/Code/C/NetProgramming/InternetProject/Makefile)，您可以直接在專案根目錄下使用 `make` 進行編譯：

* **編譯動態連結庫**：
  ```bash
  make
  ```
  *(在 Windows 下會自動生成 `connection.dll`；在 Linux/macOS 下會自動生成 `connection.so` 或 `connection.dylib`)*

* **清除編譯結果**：
  ```bash
  make clean
  ```

### 4. 運行遊戲大廳
環境與 DLL 編譯完成後，即可直接透過 `uv run` 啟動遊戲大廳：
```bash
uv run python main.py
```
* **提示**：`uv run` 會自動在剛才建立的虛擬環境中執行 Python，您不需要手動去執行 `source .venv/activate` 或 `.\.venv\Scripts\activate`。

---

## 🛠️ 日常開發指令 (uv 常用操作)

在後續的開發過程中，您可以透過以下指令輕鬆管理套件：

* **新增套件** (例如要新增套件 `requests`，這會同步寫入 `pyproject.toml` 與 `uv.lock`)：
  ```bash
  uv add requests
  ```
* **移除套件**：
  ```bash
  uv remove requests
  ```
* **在虛擬環境中執行任意指令**（例如執行測試）：
  ```bash
  uv run python -m unittest discover tests
  ```
