# 單一 CSV 來源換檔修訂

## 實作與限制

既有 Run revisions API 接受 csv_replacement_v1（upload_id、checksum、size、original_name、fields），不另建 Task 系統。後端重新讀取受控檔案，拒絕任意 path、錯誤 checksum／size、非單一 CSV 及未支援的來源 metadata。未知 metadata 不會默默丟棄。欄位描述需後续 Gate／Naming／規格驗證，換檔不代表型別或語意通過。

修訂沿用 Task-first transaction；舊 Run 轉為 SUPERSEDED_BY_REVISION，舊 snapshot／Gate／approval 保留，新 Run 沒有核准且須重跑 Gate。不覆寫舊檔，不執行 ETL。舊扁平 CSV metadata 可在允許範圍內轉為單一 sources。

## 驗證

- 本機 source replacement／source revision／run API／upload integrity 共 31 passed。
- 隔離 PostgreSQL replacement 與 run queue 共 19 passed（2.42 秒）：成功只新增一個 child；相同 request key 回傳同一 child；舊 checksum、核准及舊檔保留；未核准 child 不被 Worker 領取；重新核准後保存新 checksum 證據。
- 新檔在上傳後被同長度替換：拒絕修訂，Task source_config 不變、舊 Run 仍 NEEDS_REVIEW、只有原本一個 Run。
- 測試使用暫存合成檔案與獨立測試資料，原平台設定由 fixture 還原，沒有模型呼叫或 Vertica 寫入。
- api／control-worker 後端已部署；執行開關保持關閉。

## 網站追加驗收

- 已部署 CsvReplacement：選取 CSV、顯示大小與樣本推定欄位、明確確認、取消換檔。尚未確認或上傳失敗時不能保存修訂，可取消換檔回原來源；保存進行中鎖住換檔欄位。
- 位於可修訂版本的「補正需求並建立新版」。只對 csv_contract_editable 版本顯示；舊扁平來源尚未有此 UI 入口。
- 真實 upload-live 流程新增換檔驗收，不 mock：先取消一次再上傳確認；新 Run 無核准；核准後 Worker 保存新 checksum；舊 Run 保留原 checksum 及 APPROVE，狀態為 SUPERSEDED_BY_REVISION。
- 單獨測試 9.2 秒通過：TASK-20260913-0115，child 039c8029-5feb-46f8-bf6b-3db4f2c60459。
- 最終部署全套瀏覽器 12 passed / 2 skipped（40.0 秒），TASK-20260913-0123，parent 89cada4b-2535-4cad-87c1-756f826adcbf，child 9af2719d-7523-451c-b5ec-7a823c619f70。測試恢復原設定並取消自身未写入 Run，保留歷史。無模型／Hop／Vertica 執行。

## 尚未完成

- 舊扁平來源、設定失效或已取消版本的換檔入口，以及命名契約有欄位變更時的完整重新確認流程。
- Excel／JSON 換檔、多來源／Join 修訂未支援。
- Hop 使用 immutable byte snapshot、Vertica QA、SDM 與 Release 仍未完成。
