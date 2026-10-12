# 2026-10-13 階段驗收與aiserver開發准备

## 判定

可驗收並上版：已完成正常三案與新失敗修正版的既有實際證據、目前新增部分提交純守門，以及aiserver工程環境配置準備。不是整個v2完成，也不是aiserver已部署或新部分提交案例通過。

## 本次實際驗證

- 源碼起點f7e287d，原未提交Join測試SHA cc1f19bd4e2da5bf311ed3d3f89802f65e497d5fa40e7cc954d32b6a553e9777未變。新增partial_acceptance_scope：固定1001筆／SHA、Task／Run／新目標／APPEND／無變換及未寫入前置、完整1000筆前綴multiset、精確live容器ID／nonce／labels／restart=no與独立故障授權；純函式不派發、SQL、kill或核准。尚未接完整部分提交Worker／監督器，不會因環境字串存在就自行中止程序。
- 無網路Docker隔離：新增40PASS1.40s；與既有failure/local_worker相容組合72PASS5.48s、0FAIL。未重跑全backend或瀏覽器，先前2134/139、152/28結果有其歷史範圍。
- 本機5197 GET下載重驗connection refused；Docker實際api/web/postgres/control容器均已停止約25h。沒有重送任何模型/Hop/QA/Release或命令重開5197。20261011實際新修正版Release與八原成果指紋證據保留，今日不能宣稱它們又完成runtime regression。
- SSH既有aiserver_ed25519、已確認hostkey：kewin帳號publickey拒絕；依Workspace已確認homeadmin登入成功。主機22邏輯CPU、31432MiB RAM／23980MiB available、RTX4070 Laptop8188MiB、NVMe約913GB空間。GitHub身分kewinall與repo f7e287d遠端讀回成功。Docker直接拒絕、sudo-n唯讀version/ps成功；SELinux已enabled。Node24.18、Python3.14.8、Git2.56、Docker29.9、Compose5.6可用；Codex/Claude path存在，本輪未呼叫模型。
- 新compose.aiserver-dev與compose.aiserver-tests解析成功；分離工程/測試DB、network、volume；四派發false、PG不公開、web127.0.0.1:5198、Fedora測試bind只讀ro,Z。沒有在aiserver clone/build/啟動服務，沒有觸碰postgres-rag/Agent/Paperclip或Windows資料／秘密。完整說明docs/aiserver-development.md。

## 範圍與下一步

1. aiserver以GitHub階段源碼clone到/home/homeadmin/projects/ai-etl-workbench，NVMe開發、Docker Python3.12、獨立DB、SSH5198隧道；先做source/config/API/backend/browser驗收。主機Python3.14不直接當後端鎖定環境；原Win32/WSL local_acceptance_worker不直接搬到Linux。GPU不自動取代模型Profile。
2. 移轉源碼與正式資料是兩回事；秘密/資料/舊產物仍留原環境，後續需獨立一致備份／加密／restore／指紋與明確範圍。沒有複製本機runtime-temp或vault。
3. R21仍待完整受控Worker／監督器與新故障寫入授權；R19合法QA同次補證、390真實寫入、JSON/table、REPLACE/UPSERT、已交付修訂、維運與人工基準保持未完成。WS0007 active。
