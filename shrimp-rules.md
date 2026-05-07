# SDD 專案開發守則 (AI Agent 專用)

## 1. 專案概述
本專案為 **SDD (Spec-Driven Development) 工具鏈**，核心邏輯是透過「規格 (Spec) 驅動」來管理開發全生命週期，包括設計生成、門禁校驗、任務拆分與實現追溯。

## 2. 專案架構與事實來源
### 核心事實來源 (Baseline)
- **設計態事實**: `.spec/baseline/sdd-index-design.json`。所有已審批的設計意圖存儲於此。
- **實現態事實**: `.spec/baseline/sdd-index-real.json`。所有已落地的實現快照存儲於此。
- **架構紅線**: `.spec/baseline/constitution.md`。
- **物理事實**: `schema-context.json` 優先通過 `refresh-schema-context --from-polyquery` 獲取。
- **附著配置**: `.spec/attached-project.json` 定義當前附著路徑。
- **任務事實**: `tasks/task-slices.generated.json` 是 Gate 4 的輸入來源。

### 目錄結構
- `specs/{feature}/`: 存放具體 Feature 的規格、設計、任務與報告。
- `scripts/`: 專案運行的「肌肉」，包含所有自動化腳本。
- `docs/arch-standards/`: 存放各類技術標準。

## 3. 工作流程規範 (MANDATORY)
所有開發任務必須嚴格遵循以下階段，不得跳過：

1. **Phase 0: Project Attachment**
   - 動作: `run_pipeline.py onboard-project`。
1. **Phase 1: Feature Brief**
   - 產出: `specs/{feature}/feature-brief.md`。
   - 要求: 必須包含 `capability_tags`。不確定點必須標註 `[AMBIGUOUS]`。
2. **Phase 2: Design**
   - 產出: `design-v{N}.md` 及 `design-pack/`。
   - 門禁: 必須通過 `run_pipeline.py gate1/2/3`。
   - 審核: `risk_tier=high` 必須有 `reports/v{N}/approval.json.status == APPROVED`。
3. **Phase 3: Task Slice**
   - 產出: `tasks/slice-NNN.md`。
   - 包含: 垂直切片 (Vertical) 與橫切任務 (Cross-cutting)。
4. **Phase 5: Implementation & Verify**
   - 入口: `run_pipeline.py --verify {feature}`。
   - 動作: 通過 Gate 5 後，自動調用 `sync_baseline.py` 更新事實來源。

## 4. 關鍵文件命名與交互規範
### 設計包 (design-pack/) 命名
- **通用規則**: 使用「中文語義.後綴」。
- **狀態機**: 必須命名為 `{業務對象}狀態機.md`。
- **資料模型**: 必須命名為 `數據模型.md`。
- **資料庫變更**: 必須命名為 `數據庫變更.sql`。

### 聯動修改要求
- **修改 Spec**: 若修改了 `specs/` 下的任何規格文件，必須重新運行對應的 `Gate` 腳本。
- **切換附著項目**: 修改 `.spec/attached-project.json` 後，必須運行 `refresh-baseline`。
- **數據庫事實同步**: 在執行 Gate 2 前，若涉及 DB 變更，應執行 `refresh-schema-context --from-polyquery`。
- **完成實現**: 完成代碼實現後，必須運行 `Gate 5` 校驗。**嚴禁手動更新 `sdd-index-real.json`**。

## 5. 技術與設計紅線 (SonarQube 級別)
- **分層依賴**: 
  - `Controller` -> `Service` -> `Repository`。
  - `Service` 可調用 `StateMachine`。
  - **嚴禁** `Controller` 直接調用 `Repository`。
- **異常處理**: 
  - 設計中必須包含「異常處理表」。
  - 外部調用必須定義 `Timeout`, `Retry`, `CircuitBreaker`。
- **資料庫**: 
  - 表名必須以 `t_` 開頭。
  - 變更腳本必須包含 `-- UP` 和 `-- DOWN` 區塊。
- **併發控制**: 涉及狀態流轉、支付、庫存扣減時，必須說明「冪等策略」。

## 6. AI 決策規範
- **優先級**: 實現態事實 (`sdd-index-real.json`) > 設計態事實 (`sdd-index-design.json`) > 通用知識。
- **衝突處理**: 若發現當前設計與 `sdd-index-design.json` 中的 `ACTIVE` 條目路徑衝突，必須在 `feature-brief.md` 中標註並尋求解決方案。
- **模糊處理**: 嚴禁猜測業務邏輯。若 `requirements` 描述不清，必須插入 `[AMBIGUOUS]`。

## 7. 禁止事項 (CRITICAL)
- ❌ **嚴禁**在未通過 `Gate 1/2/3` 的情況下將設計寫入索引。
- ❌ **嚴禁「偽通過」行為**: 嚴禁為了通過門禁校驗而刪除設計細節、使用空占位符、或僅提供文檔引用。
- ❌ **嚴禁內容縮水**: 設計方案 (`design-vN.md`) 每個章節必須包含實質性的邏輯闡述，不得僅有標題。
- ❌ **內容優先權**: 物理細節（SQL 精度、超時參數、算法邏輯）的優先級始終高於門禁通過的速度。
- ❌ **嚴禁手動修改** .spec/ 下的任何 JSON 索引文件。
- ❌ **嚴禁**設計中出現反向依賴（如 `Repository` 調用 `Service`）。
- ❌ **嚴禁**在 `pyproject.toml` 中添加未經確認的依賴。
- ❌ **嚴禁**忽略 `risk_tier=high` 的審批要求。
