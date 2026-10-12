# aiserver 開發與阶段驗收（2026-10-13）

## 已確認與尚未執行

已用既有專用SSH金鑰成功登入 `homeadmin@192.168.88.150`；`kewin`不是可用登入帳號。主機22邏輯CPU、31432MiB RAM（盤點時23980MiB available）、RTX4070 Laptop 8188MiB、NVMe剩約913GB。Docker29.9.0／Compose5.6.0、Node24.18.0、Python3.14.8、Git2.56.0可用；GitHub身分kewinall及本repo遠端SHA讀回成功。這些是本次SSH實測，不以先前Workspace紀錄代替。

homeadmin直接Docker會permission denied；既有 `sudo -n docker` 唯讀查詢成功。沿用sudo，不為方便開放socket或加入docker群組。Docker已啟用SELinux。原postgres-rag占localhost5432、主機Agent占8765、Paperclip占3100；本方案不碰它們。主機已有Codex及Claude CLI，但本輪未呼叫模型，不能以工具存在宣稱訂閱與模型流程可用。

本輪沒有在aiserver clone、啟動ETL環境、搬資料或秘密；以下配置已在本機Compose解析及結構檢查，**尚未在aiserver build／runtime驗收**。本機5197各容器已停止，今日正式Release GET重驗因connection refused未完成；2026-10-11保存的交付證據仍保留，不當作今日即時PASS。不因GET失敗自動啟動Worker或重送意圖。

## 分工與放置方式

建議將源碼放NVMe的 `/home/homeadmin/projects/ai-etl-workbench`，使用一般帳號即可建立；目前 `/srv/repos` 是root擁有，不直接更改它的權限。以GitHub為版本交接：Windows階段提交／push → aiserver clone／fetch → 新branch或worktree開發 → 遠端測試 → 提交回GitHub → Windows獨立驗證。

只clone受版本控制的源碼、文件及合成fixtures。不要複製Windows整個資料夾、`.venv`、`node_modules`、runtime-temp、outputs、私鑰、vault、PostgreSQL volume或既有交付目標。既有5197實際成果留在原環境；aiserver先建立新的工程DB與產物卷。若之後要搬正式驗收資料，另做一致備份／加密／獨立restore／指紋讀回，不能把Git clone當成資料遷移。

## 1. clone與固定起點（aiserver SSH terminal）

```bash
mkdir -p "$HOME/projects"
cd "$HOME/projects"
# 目標已存在時先查看git status，不覆蓋、不重新clone。
git clone https://github.com/kewinall/ai-etl-workbench.git
cd ai-etl-workbench
git status --short
git log -1 --format='%H %s'
git ls-remote origin refs/heads/main
git switch -c dev/aiserver-start
```

紀錄clone HEAD與階段上版遠端SHA相同後才開始；若remote又前進，先查差異。私人repo使用主機既有GitHub credential helper，不將token加到URL或檔案。現行主機Python3.14不同於backend鎖定Python3.12，後端先用既有Dockerfile，不用主機Python建立相容性未驗的venv。

## 2. 獨立工程網站與後端測試

```bash
sudo docker compose -f deploy/compose.aiserver-dev.yml config --quiet
sudo docker compose -f deploy/compose.aiserver-dev.yml build api web
sudo docker compose -f deploy/compose.aiserver-dev.yml up -d
sudo docker compose -f deploy/compose.aiserver-dev.yml ps
curl --fail http://127.0.0.1:5198/api/ready

# 完整後端回歸使用另一個專案／DB／volume，不使用網站DB或postgres-rag。
sudo docker compose -f deploy/compose.aiserver-tests.yml config --quiet
sudo docker compose -f deploy/compose.aiserver-tests.yml build tests
sudo docker compose -f deploy/compose.aiserver-tests.yml up --abort-on-container-exit --exit-code-from tests
sudo docker compose -f deploy/compose.aiserver-tests.yml stop
```

四個模型／ETL派發全部false；沒有control、Hop或可攜Worker，也沒有真實秘密。5198僅loopback，PG不公開port，內網獨立，產物與測試DB卷不共享。SELinux掛載用ro,Z；這會重標該clone檔案，只在獨立NVMe clone使用，不能套到NAS或其他服務共享目錄。不使用 `down -v` 或全域Docker prune。

## 3. Windows瀏覽與遠端編輯

```powershell
ssh -i C:/Users/kewin/.ssh/aiserver_ed25519 -o ExitOnForwardFailure=yes -N -L 5198:127.0.0.1:5198 homeadmin@192.168.88.150
```

隧道保持開啟，Windows開 `http://127.0.0.1:5198`。不使用5197避免混淆原驗收站。可用支援SSH的編輯器開上述遠端clone；也可在SSH terminal進入clone後使用主機已裝的Codex或Claude CLI，先確認AGENTS／Skills與專案範圍。這樣源碼、建置、測試在aiserver執行，Windows僅看畫面；Windows本地Codex一般執行工具不會因SSH登入就自動變成遠端工具。

## 4. 前端回歸與開發迴圈

```bash
cd "$HOME/projects/ai-etl-workbench/frontend"
npx --yes pnpm@10.11.0 install --frozen-lockfile
npx playwright install chromium
WORKBENCH_TEST_URL=http://127.0.0.1:5198 npx playwright test
npx --yes pnpm@10.11.0 build
```

pnpm版本沿用現有Dockerfile，aiserver目前未裝pnpm/corepack。Playwright可能需要Fedora系統依賴；瀏覽器安裝與native執行尚未驗收，若缺依賴先讀報錯，不能以build取代browser驗收或盲目裝一整套系統套件。每輪先做有關測試，再做必要完整回歸；提交前 `git diff --check`，保留測試scope／skip理由。

React／API／Hop本身主要使用CPU/RAM；8GiB GPU是可選本機推論資源，不會因搬repo就自動改用GPU。真實模型仍沿用已確認的Profile／CLI授權，Ollama接入另做契約與QA驗收，不替代原模型來冒稱全鏈通過。Windows local_acceptance_worker含wsl.exe及本機容器名稱，不能直接在Linux執行；aiserver正常工程測試不啟動它，之後真實驗收須接Linux Worker與新目標。

## 接手驗收与回復

初次遠端驗收需保存：source SHA、四派發false、獨立volume/networks、API ready、後端結果、前端build/browser結果、合成Task保存讀回，以及原postgres-rag／Agent／Paperclip仍正常。健康檢查不是七階段ETL驗收。

本配置停止：`sudo docker compose -f deploy/compose.aiserver-dev.yml stop`；保留新DB/產物方便核對。回復源碼用新worktree指向已驗收commit，不在有未提交修改的branch做reset。真實模型／Hop／Vertica／秘密搬移與故障中止仍需具體案例授權；沒有授權時只做工程隔離測試。
