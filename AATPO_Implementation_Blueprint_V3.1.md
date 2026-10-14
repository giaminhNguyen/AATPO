# AATPO - BAN DAC TA TRIEN KHAI CHO CODING AGENT

**Ten du an:** Autonomous AI Technology Production Office (AATPO)  
**Version:** 3.1 - Windows CLI-first / Role-based agents / Task-scoped sessions  
**Ngay:** 2026-10-14  
**Trang thai:** BAN HOAN CHINH de giao coding agent; KHONG phai bao cao he thong da duoc trien khai  
**Nen tang:** Windows 11 native, thuc thi tai may nguoi van hanh  
**Tai lieu lien quan:** `AI_Technology_Production_Office_Spec_V1.1.md`, `AATPO_Windows_CLI_First_Architecture_V2.md` (co the doc them, nhung file V3 nay tu du de coding agent bat dau).

> **Chot yeu cau:** Khach hang khong can hieu ky thuat, chi mo ta mong muon. Van phong tu lam ro yeu cau bang ngon ngu doi thuong, tu van giam tinh nang de phu hop ngan sach, tu len ke hoach / giao task / huy dong nhan vien AI / thuc hien / kiem dinh / ban giao. Runtime su dung **cac AI Agent CLI chinh thuc da cai dat va dang nhap tren Windows**, khong bat buoc API key rieng. **Mot CLI co the phuc vu nhieu nhan vien AI logic; moi task co phien thuc thi rieng.**

> **Huong dan cho coding agent:** Day la **spec**, khong phai lenh trien khai tat ca mot luc. Dung nen tang o day lam nguon chuan. Thuc hien theo milestone, viet test va chung minh chay that. Khong tu mo rong sang web, cloud, subscription-sharing, thanh toan, marketing hay he thong phat hanh.

---

## 0. QUYET DINH DA CHOT, UU TIEN VA NHUNG DIEU KHONG DUOC TU SUY DIEN

### 0.1. Da chot

1. Nguoi dua yeu cau la **khach hang**, co the khong biet lap trinh hay he thong may tinh.
2. Mot dau moi giao tiep voi khach hang la **Client Representative**, dung tieng Viet de hieu va chu dong tu van, khong noi chuyen nhu voi developer.
3. Ho tro: task ky thuat don le, cong viec nhieu buoc, du an san pham, nghien cuu/phan tich.
4. Van phong tu dieu phoi sau khi du thong tin, khong bat khach hang chia task hay chi dinh ky su.
5. Muc tieu **chi phi thap nhat hop ly**: can doi pham vi, chi phi van hanh va chat luong; khong hy sinh an toan cot loi de giam gia.
6. Chay tren **Windows native**, su dung **Codex CLI**, **Claude Code**, **Gemini CLI** neu da cai va xac thuc hop le; tung CLI la tuy chon. Khong buoc phai co ca ba.
7. **CLI != Agent Role != Task != Agent Session != Process Run**. Tat ca la nhung thuc the rieng, co ID rieng.
8. **1 CLI co the chay nhieu role**; **1 role co the lam nhieu task**; **moi (task, role tham gia) co session rieng**, khong dung chung lich su hoi thoai giua task.
9. Khi cung task can sua loi/lam tiep: uu tien `resume` **dung session ID cu** neu adapter chung minh duoc ho tro; neu khong, tao session moi tu brief luu tru. KHONG dung `latest` lam mac dinh.
10. Ho so role va tri thuc du an ben vung; phien CLI khong phai bo nho chinh thuc.
11. Duoc lap ke hoach / thuc thi tu dong trong pham vi quyen; quyet dinh thay doi scope/chi phi va thao tac nguy hiem can xin duyet.
12. Khong lam web/desktop GUI trong MVP. Giao tiep terminal / CLI app la du.
13. **Khong thiet ke he thong sandbox trong giai doan nay** theo yeu cau cua nguoi dung. Van can kiem soat pham vi file, quyen, xac nhan thao tac nhay cam. Git Worktree chi tach noi dung code, khong dam bao an toan OS.

### 0.2. Thu tu uu tien khi xung dot

`An toan + quyen cua khach + dieu khoan su dung` > `chuc nang cot loi + chat luong co the kiem chung` > `ngan sach da duyet` > `toi uu chi phi/thoi gian` > `tinh nang phu`.

Neu khong the cung dap ung, bao lai khach hang de chon **giam pham vi / doi ngan sach / dung**, khong am tham bo qua rang buoc.

### 0.3. Khong nam trong pham vi MVP

- Web dashboard, cong ty nhiem vu marketing/sales, thanh toan, billing khach hang, publish public, auto deploy production.
- 8 AI process chay lien tuc; thue 8 subscription; cloud service / database server / Redis / Kafka / vector DB mac dinh.
- API key tu dong, proxy tai khoan CLI cho nguoi khac, doc/copy file token dang nhap, bypass quota/terms.
- Mo hinh agent tu do trao doi khong gioi han; khong co log/kiem dinh dau ra.
- Sandbox/VM/container isolation la hang muc rieng co the xem xet sau, **khong phai dieu kien MVP**.

---

## 1. MUC TIEU NGHIEP VU (PRODUCT GOALS)

**G1 - Input tu nhien:** Khach noi 'Toi muon app quan ly kho, don gian va it tien'. He thong hieu muc tieu, khong yeu cau framework, DB, API.

**G2 - Clarification co chon loc:** Chi hoi dieu thieu ma anh huong den ket qua, cach dung, chi phi hoac rui ro. Hoi ngan gon, moi luot uu tien 1 cau quan trong; ho tro 'Toi khong biet, hay de xuat'.

**G3 - Tu van chi phi truoc khi lam:** Xep tinh nang MUST / SHOULD / LATER / DROP; de xuat phuong an TIET KIEM va CAN BANG neu la san pham chua ro scope; giai thich trade-off. Khong dua con so bao gia doan bua.

**G4 - Tu to chuc:** Office Manager tu phan loai, tao ke hoach, tach task DAG, chon role, chon CLI, theo doi tat ca phu thuoc.

**G5 - Thuc thi that:** Worker co the doc repo, tao/sua code, chay test, tao tai lieu, nghien cuu va xuat artifacts trong thu muc du an da duoc cho phep.

**G6 - Kiem dinh:** Khong danh dau thanh cong chi vi LLM noi da xong; yeu cau evidence nhu git diff, build/test result, tai lieu va acceptance criteria.

**G7 - Ben vung:** Restart chuong trinh / crash CLI / het quota khong lam mat work order, session ledger, decision, task, test evidence.

**G8 - Chi phi:** Cho phep 1 CLI lan luot dam nhan nhieu role; gioi han concurrency, so lan retry, timeouts, hoat dong vo ich; ghi usage co nguon neu CLI cung cap.

**G9 - Linh hoat:** Bat dau chi can mot provider dang nhap; bo sung CLI khac bang adapter, khong thay doi nghiep vu.

---

## 2. NHAN SU: 8 ROLE LOGIC, KHONG PHAI 8 PROCESS

| Ma role | Ten | Viec chinh | Dau ra/luat | Khong duoc tu lam |
|---|---|---|---|---|
| `client_representative` | Tiep nhan khach hang | Hoi lai bang ngon ngu de hieu, trinh bay lua chon, bao cao tien do | Cau hoi / tom tat / scope de duyet | Hoi jargon ky thuat; tu phe duyet doi scope |
| `business_analyst` | Phan tich nghiep vu | Tach needs/features, ambiguity, tieu chi nghiem thu | Requirement spec, feature shortlist | Mac dinh nhu cau chua xac nhan la bat buoc |
| `office_manager` | Dieu hanh | Lap plan, chon role, tao DAG, giu ngan sach, escalate | Work plan, assign, progress | Vuot quyen / chay vo han / bo qua quality gate |
| `system_architect` | Kien truc | Thiet ke giai phap, API/data contract, review thiet ke | Architecture decision, contract | Tu doi muc tieu kinh doanh |
| `frontend_engineer` | Frontend | Giao dien, tuong tac, unit tests lien quan | Code/diff/tests | Sua backend neu khong duoc giao |
| `backend_engineer` | Backend | API, logic, data, unit tests lien quan | Code/diff/tests | Sua du lieu quan trong ngoai pham vi |
| `qa_engineer` | QA | Test, review theo acceptance, defect/feedback | Verification report | Tu xac nhan done neu khong co bang chung |
| `devops_engineer` | Build/handover | Build, runbook, moi truong test, package | Build/run instructions/artifacts | Deploy production neu chua duoc phe duyet |

**Specialist Pool:** `mobile_engineer`, `ai_ml_engineer`, `security_engineer`, `data_engineer`, `research_engineer`, `ui_ux_designer`, `integration_engineer`... them bang `roles/*.md`, khong can chay thuong truc.

**Co che role:** Moi role la profile (`role_id`, `purpose`, `permissions`, `required_inputs`, `output_schema`, `quality_standard`, `customer_facing`) va co the duoc gan cho bat ky provider CLI nao co nang luc phu hop. Khong duoc hardcode 'Codex = Backend', 'Gemini = BA'.

**Kiem dinh doc lap:** QA role la goc nhin khac, nhung neu cung CLI/model thi khong duoc khang dinh doc lap tuyet doi. Test that, review diff va acceptance evidence phai la uu tien so 1.

---

## 3. 5 KHAI NIEM KY THUAT BAT BUOC PHAI TACH BIET

| Thuc the | Y nghia | Thoi gian song | Vi du |
|---|---|---|---|
| `CLIProvider` | Chuong trinh / nhom xac thuc co san | Lau dai, cap thiet bi | `codex`, `claude`, `gemini` |
| `AgentRole` | Danh tinh / chuc vu / quy tac | Lau dai, co phien ban | `backend_engineer@v1` |
| `Task` | Don vi cong viec co tieu chi nghiem thu | Trong mot work order | `TASK-004: build login API` |
| `AgentSession` | Ngu canh cho **mot role tren mot task** | Trong task, co the resume | `SESS-019` tu Codex |
| `ProcessRun` | Mot lan khoi chay CLI thuc te | Phut/gio, co the fail | `RUN-031` |

Quan he:

```text
1 CLI Provider (da dang nhap tren Windows)
   |--- 1..N role profiles (logic, khong phai process)
            |--- 1..N task assignments
                     |--- 1..N sessions cho cac role tham gia (khong share history)
                              |--- 1..N process runs / resume attempts

Example:
CODEx CLI
  - Office Manager -> Task A -> Session S-01 -> Run R-01
  - Backend Agent  -> Task B -> Session S-02 -> Run R-02, R-03 (resume)
  - QA Agent       -> Task B -> Session S-03 -> Run R-04
  - Backend Agent  -> Task C -> Session S-04 -> Run R-05 (NEW, not S-02)
```

**Invariants:**

- `task_id` va `role_id` khong the dung lam CLI session ID.
- Moi session thuoc dung 1 `(task_id, role_id, assignment_id, provider_id)`. Neu cung task co QA thi QA co session khac Developer.
- Khi chuyen provider cho mot assignment: ghi `handoff_summary` + evidence, tao session moi, khong co gang dung session ID cross-provider.
- Nhan vien A va B trao doi qua `handoffs`/`messages` co cau truc trong SQLite, KHONG tu chep raw chat cua nhau thanh system instruction.
- Mot vai tro co the xu ly 10 task lien tiep ma khong can 10 AI tai khoan; 10 task khong duoc gop chung vao 1 lich su CLI.

---

## 4. KIEN TRUC LOGIC DUOC CHON

```text
CUSTOMER (natural-language Vietnamese)
     |
     v
Local CLI App (Typer/Rich) --> Customer Gateway (Representative + BA)
     |                               |
     |  question / scope options     | confirmed requirements
     v                               v
SQLite (source of truth) <--> Office Engine / deterministic policies
                                 |-- Work order lifecycle
                                 |-- Scope and budget advisor
                                 |-- Office Manager planner
                                 |-- Task DAG scheduler
                                 |-- Approval gate / quality gate
                                 |-- Role registry / session manager
                                 v
                         CLI Router + Adapter
                            |       |       |
                          Codex   Claude  Gemini  (any subset)
                            \       |       /
                             v      v      v
                       Local Workspaces + Git + Test tools
                                 |
                                 v
                       Evidence -> QA -> Delivery
```

### 4.1. Module boundaries

1. **Customer Gateway:** Chiu trach nhiem text de hieu, no tech-jargon, questions, scope confirmation.
2. **Office Engine:** Xac dinh next step, task assignment, approval; logic cua app, khong uy quyen tu do cho LLM.
3. **Planner:** Goi mot role AI de de xuat task DAG theo JSON; engine validate va quyet dinh chap nhan.
4. **Task Scheduler:** Duyet dependency/lock/capacity/quota; claim task co transaction.
5. **Role Registry:** Doc profile, version, quyen, prompt composition.
6. **Session Manager:** Mapping task-role-provider-session, resume exact ID, khong dung recent-session fallback.
7. **CLI Adapter:** Probe chuc nang, launch process, parse stdout, return normalized result; khong can model API.
8. **Workspace Manager:** Repo, thu muc, task branch/worktree neu can; thu muc duoc phep, diff.
9. **Quality Gate:** Run test, validate artifacts, allow rework or fail/escalate.
10. **Cost Controller:** quota/time/runs, so sanh phuong an, chan loop.
11. **Persistence & Audit:** SQLite, migration, files, immutable run reports, structured events.

### 4.2. Technology stack - QUYET DINH MVP

| Lop | Su dung | Ly do |
|---|---|---|
| OS | Windows 11 native / PowerShell | Dung CLI da login tren user profile |
| Language | Python 3.12+ | Subprocess, SQLite, Windows integration |
| Local UX | Typer + Rich | Nhe, don gian; khong web |
| Contracts | Pydantic v2, JSON Schema | Validate output AI / input |
| State DB | SQLite (`sqlite3`) + migrations | Khong can server, durable |
| AI execution | Official CLI adapters (Codex/Claude/Gemini) | Dung subscription/login hien co khi duoc phep |
| Process mgmt | `asyncio.subprocess` + Windows launcher + `psutil` (neu can) | stdout/stderr/timeout/kill tree |
| Repository | Git for Windows | diff/review, optional worktree |
| Tests | pytest + test commands theo du an | Kiem dinh that |
| Workflow nang cao | LangGraph + SQLite checkpoint, them tai milestone 3 | Interrupt/resume/graph khi that su can |
| Config | TOML/YAML + Pydantic validation | Human-readable + fail-fast |

**Khong dua LangGraph vao 'Hello World' runtime truoc khi CLI adapter da pass smoke tests.** O milestone dau dung deterministic state machine + SQLite. LangGraph la lop orchestration thay cho cac quy trinh phuc tap, khong duoc thay `Task DB` hay `Session Ledger`.

**Khong can mac dinh:** CrewAI, OpenHands runtime, LiteLLM, Redis, Postgres, Docker, E2B, cloud LLM, web UI, vector DB, mot message broker ngoai. Ly do: thua so voi CLI da co, phu thuoc API hoac tang van hanh.

---

## 5. VONG DOI WORK ORDER VA TASK

### 5.1. Work Order

```text
RECEIVED -> DISCOVERING -> [WAITING_CUSTOMER] -> SCOPE_PROPOSED
    -> SCOPE_CONFIRMED -> PLANNED -> EXECUTING <-> VERIFYING
    -> PACKAGING -> DELIVERED -> ACCEPTED

Alternative: PAUSED_QUOTA | PAUSED_APPROVAL | BLOCKED | FAILED | CANCELLED
After DELIVERY: CHANGE_REQUESTED -> new version of scope / new work order
```

- `WAITING_CUSTOMER` neu thieu thong tin quan trong; nguoi tra loi chi thay mat Customer Gateway.
- Khi scope thay doi: tao `scope_version` moi; task bi anh huong phai duoc reassess, khong sua lich su da duyet.
- Khong duoc `ACCEPTED` chi tren phan hoi 'QA ok' - can co customer acceptance hoac ghi ro ban giao dang cho nghiem thu.

### 5.2. Task

```text
BACKLOG -> READY -> CLAIMED -> RUNNING -> OUTPUT_READY -> REVIEW
                                           |                |  
                                           |                +-> DONE (evidence verified)
                                           |                +-> REWORK -> READY
                                           +-> BLOCKED / PAUSED / FAILED
```

`READY` khi cac dependency `DONE` va inputs ton tai. `DONE` phai co reviewer/evidence theo policy. `BLOCKED` ghi ly do + nguoi/nguon can giai quyet.

### 5.3. Runs va sessions

- `AgentSession`: `NEW -> ACTIVE -> SUSPENDED -> CLOSED`, hoac `INVALIDATED` neu provider/session ID khong con resume duoc.
- `ProcessRun`: `QUEUED -> STARTING -> RUNNING -> SUCCEEDED / FAILED / TIMED_OUT / CANCELLED / UNKNOWN_AFTER_CRASH`.
- `SUCCEEDED` chi la process xong; khong co nghia task DONE.
- Neu restart khi process status RUNNING, kiem tra PID/process identity (neu co) + output artifact + event journal; neu khong xac minh duoc, chuyen `UNKNOWN_AFTER_CRASH`, khong blindly replay thao tac ghi.

---

## 6. GIAO TIEP VOI KHACH HANG: KHONG CHUYEN KHACH THANH DEV

### 6.1. Discovery algorithm

1. Nhan text tu khach, luu nguyen van.
2. Representative tom tat nhu cau bang tieng Viet pho thong.
3. BA tach facts da biet / gia dinh co the tu quyet / cau hoi quan trong / chi tiet ky thuat noi bo.
4. Neu thong tin thieu co the lam sai muc tieu, thay doi chi phi lon, bao mat hay du lieu -> hoi **mot cau uu tien cao**; cung cap phuong an 'chua ro, de xuat giup'.
5. Lap danh sach tinh nang va phan loai MUST/SHOULD/LATER/DROP.
6. Trinh bay phuong an toi gian va neu ket qua thu duoc / nhung gi de sau; hoi khach chap nhan pham vi.
7. Ghi `confirmed_by_customer`, `confirmed_at`, `scope_version` va assumptions ro rang.
8. Sau do Office Manager duoc phep len ke hoach, khong tiep tuc phang van neu khong can.

### 6.2. Cau hoi tot vs xau

- KHONG: 'Ban muon Redis hay RabbitMQ? React hay Vue?'
- CO: 'Co can nhan vien van ban hang duoc luc mat Internet khong? Neu khong, minh co the chon giai phap re va de bao tri hon.'
- KHONG: 'Nen tach microservices thanh may service?'
- CO: 'Ung dung nay chi phuc vu mot dia diem hay nhieu chi nhanh?'

### 6.3. Scope feature contract

Moi feature co: `name`, `user_problem`, `classification`, `reason`, `value`, `effort_band` (`XS/S/M/L/XL`), `dependencies`, `impact_if_omitted`, `optional_cost_drivers`, `customer_decision`.

**Hanh vi:** Neu ngan sach han che, van phong chu dong de xuat bo qua `LATER`/`DROP`, nhung khong tu bo nhung tinh nang `MUST` da duoc khach xac nhan. Mot MVP phai dung duoc vao muc dich chinh, khong phai ban demo khong su dung duoc.

---

## 7. LANH DAO TU DONG: PLANNER, SCHEDULER VA DECISION POLICY

### 7.1. Planner

Input: approved work order, scope version, repo details, constraints, current knowledge. Output Pydantic-validated **TaskPlan**:

- task list co objective, role, expected output, acceptance, dependencies, priority, `risk`, `effort_band`, `allowed_paths`.
- muc tieu la su phu thuoc hop le (no cycle), khong co task 'nghien cuu vo han'.
- task doc lap co the chay song song neu khong conflict, nhung mac dinh ban dau chi 1 run.
- thay doi plan duoc ghi `plan_version`, khong overwrite phan da lam xong.

**Sanity rules:** Giai thich co so phan chia; khong tao 50 task neu mot task co the giai quyet. Bat dau bang 'fast lane' cho viec nho.

### 7.2. Scheduler deterministically assigns

Gia lap priority:

```text
eligible = tasks where status READY and all dependencies DONE
for task in sort(eligible, by=priority, dependency_criticality, age):
    role = select_role(task)
    cli  = router.best_available(role, task, budgets, quota, capability)
    if none: set PAUSED_QUOTA or BLOCKED
    else if concurrency/resource-lock permits:
         atomically claim task (version check)
         get_or_create_task_scoped_agent_session(task, role, cli)
         create run and dispatch
```

**Khong phai LLM tu ghi truc tiep `tasks.status=done`.** AI de xuat; engine validate, policy quyết định va transaction commit.

### 7.3. Coordination / handoffs

- Moi message noi bo can `from_role`, `to_role`, `task_id`, `type`, `question_or_decision`, `evidence_refs`, `requires_reply`.
- Frontend ↔ Backend co the thong nhat API contract qua handoff record, Architect phan xu khi bat dong thiet ke.
- Neu phat hien nhu cau khach thay doi: BA -> Client Rep -> Customer, khong de engineer hoi tu `OAuth scopes`, `schema version`... truc tiep.
- Chan loop qua gioi han so handoff/task, so lan review/repair, so lan phan tich lai plan.

---

## 8. PHAN TACH RUNTIME: CLI ADAPTER KHONG PHAI AGENT

### 8.1. Adapter interface (pseudocode / design contract)

```python
class CLIAdapter(Protocol):
    provider_id: str

    async def probe(self) -> ProviderCapabilities: ...
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...
    async def resume(self, request: AgentRunRequest, provider_session_id: str) -> AgentRunResult: ...
    async def cancel(self, run_id: str) -> CancelResult: ...
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> AgentRunResult: ...
```

`ProviderCapabilities`: executable path; version; supported modes (`headless`, `json`, `resume_by_id`, `cwd`, `stdin_prompt`, `tool_mode`), probe result, health, account/login validation **without reading secrets**, timestamp.

`AgentRunRequest`: task/role/session/run IDs, working directory, prompt file/input, policy mode, output expectation, timeout, allowed paths, usage budget.

`AgentRunResult`: normalized status, provider+version, provider_session_id (neu doc duoc), start/end timestamps, stdout/stderr references, model response, parsed structured report, exit status, usage fields (if actually returned), errors.

### 8.2. Cac cau lenh mau tham khao, PHAI probe --help tren may dich

```powershell
# Kiem tra CLI da duoc Windows PATH nhan dien
Get-Command codex,claude,gemini -ErrorAction SilentlyContinue

# Codex: non-interactive; json event stream
codex exec --json "Phan tich README, khong sua file"

# Claude Code: print mode; JSON envelope
claude -p "Tom tat repo, khong sua file" --output-format json

# Gemini CLI: headless; JSON envelope
gemini -p "Tim rui ro trong yeu cau" --output-format json
```

- Codex event stream thuong la **JSONL**, khong duoc `json.loads(stdout)` nhu mot JSON object.
- Claude/Gemini cung co JSON, nhung schema wrapper **khac nhau**; adapter map ve `AgentRunResult`, khong gia dinh dong nhat.
- Resume phai dung dung session id do CLI tra ve (hoac tim duoc co chung cu), va dung directory/working context cua task; adapter can verify support theo version. Neu khong duoc, tao phien moi tu stored task brief.
- Phep role duoc dua qua prompt + context + config; `--dangerously-skip-permissions`, `--yolo` va cac co che auto-approval rong KHONG duoc bat mac dinh.
- Cac command trong tai lieu chi la minh hoa; khong cam ket option/prompt handling dung voi moi version. Tham khao official docs section 19.

### 8.3. Khai thac auth da co ma khong can credential handling

- Chay CLI theo **user Windows dang login**; khong doc file token, cookie, env secret cua CLI.
- `doctor` chi kiem tra path/version/help va chay mot READ-ONLY smoke prompt khi nguoi van hanh dong y.
- Phan biet `missing`, `not_authenticated`, `quota_exhausted`, `unsupported_version`, `unhealthy`, `ready`.
- Khong lay `quota remaining` neu CLI khong cung cap chinh thuc. Hien thi `unknown` thay vi bịa con so.
- Khong luu anh log co secret. Khong truyen xac thuc dang nhap qua framework khac.

### 8.4. Windows process launcher

- `cwd` phai la absolute path duoc registry phep; duong dan co khoang trang va Unicode phai chay dung.
- Resolve CLI executable qua `shutil.which` hoac `Get-Command`, nhung chi cho phep provider nam trong config allowlist. Windows CLI co the la `.exe`, `.cmd`, `.bat`, hoac shell shim. Implement launcher phu hop voi tung kieu; test tren Windows thay vi ap dat hanh vi Unix.
- Neu can di qua `cmd.exe /d /s /c` cho `.cmd`, chuong trinh chi truyen **argv duoc tao tu du lieu tin cay**: command template allowlisted, prompt va input qua stdin/file rieng. Tuyet doi khong ghép input khach vao command shell; validate metacharacters va co automated tests.
- `stdout` va `stderr` duoc doc bat dong bo de tranh deadlock khi buffer day; ho tro streaming JSONL va gioi han kich thuoc log. Khong ghi stdout chua thong tin nhay cam vao terminal mac dinh.
- Timeout co 2 cap: `startup_timeout` va `run_timeout`; khi cancel/timeout phai thu dong tien trinh con/process tree, wait va ghi exit status. Tren Windows co the can `psutil` hoac Job Object; han che cua tung cach phai co test.
- `exit_code==0` khong dong nghia output dung JSON, task thanh cong hay duoc QA chap nhan.
- KHONG cho AI tu cap them phep thong qua `--yolo`, `--dangerously-skip-permissions` hoac tu ghi config auto-approve. Neu cong viec can phep vuot policy, tao approval request; khong bypass de dat autonomous.
- Workspace path allowlist va Git Worktree chi la **kiem soat logic**, khong phai OS security boundary. MVP khong thiet ke sandbox theo yeu cau, nen phai minh bach gioi han va khong cho chay code khong tin cay voi quyen cao.

### 8.5. Session/resume semantics (bat buoc)

Khi mot role duoc phan cong cho task:

1. Tim `AgentSession` da co trong `(work_order_id, task_id, assignment_id, role_id, provider_id)` va trang thai con hop le.
2. Neu chua co: tao internal `agent_session_id` moi, provider session ID ban dau la `NULL`.
3. Goi adapter va luu `provider_session_id` **chi khi output duoc parser xac minh**. Khong doan ID bang ten thu muc hoac thu tu session.
4. Task bi QA tra lai cho cung role: dung session do neu provider ho tro resume theo dung ID va chua invalidated. Gui feedback ngu canh ngan gon, diff/test evidence moi.
5. Neu resume khong ho tro/that bai: luu reason, dong session cu, tao session moi voi `task_brief + decisions + evidence + unresolved issues`, khong do long raw conversation.
6. Khi task khac: new session bat ke role va provider trung nhau. QA reviewer luon co session rieng Developer.
7. Chuyen tu Codex sang Gemini/Claude: create **new** session va mot handoff minh bach. Tuyet doi khong truyen provider session ID cua CLI A sang CLI B.
8. Cac thao tac non-idempotent can recheck actual files/external state truoc khi retry do mat dien, timeout, crash.

**Resume policy:** `exact_session_id_only`; `resume latest` bi cam trong agent orchestration vi co the tiep tuc nham ngucanh.

---

## 9. DATA MODEL - SQLITE SOURCE OF TRUTH

### 9.1. Database design principles

- SQLite `WAL`, foreign keys ON, short transactions, single durable source of truth cho task state.
- Schema co migration theo version; dat file data ngoai source tree neu co the. Backup truoc migration.
- Dung ISO-8601 UTC timestamps, ULID/UUID IDs, enum string xac dinh ro; khong luu `datetime` naive.
- LLM output la **proposal**. Chi application service co quyen ghi trang thai sau khi validate transition va RBAC/policy.
- Ngu canh (JSON) duoc schema-validate; cac artifact lon la file references kem SHA-256, khong nhung raw output vao row khong gioi han.

### 9.2. Entities (toi thieu)

| Entity | Truong cot loi | Y nghia |
|---|---|---|
| `work_orders` | id, customer_request, status, current_scope_version, constraints_json, created_at | Ho so yeu cau va trang thai |
| `customer_messages` | id, work_order_id, direction, content, visibility, created_at | Chat voi khach va cau hoi clarification |
| `scopes` | id, work_order_id, version, spec_json, approved_by_customer, approved_at | Scope bat bien theo version |
| `features` | id, scope_id, category, benefit, effort_band, decision, justification | MUST / SHOULD / LATER / DROP |
| `plans` | id, work_order_id, version, status, created_by_run_id, created_at | Ke hoach DAG theo version |
| `tasks` | id, plan_id, title, role_hint, priority, risk, status, attempts, version | Don vi thuc thi |
| `task_dependencies` | task_id, depends_on_task_id | Canh DAG co kiem tra cycle |
| `assignments` | id, task_id, role_id, provider_id, assigned_at, status | Lien ket task va role |
| `agent_sessions` | id, assignment_id, provider_id, provider_session_id, state, created_at | Ngu canh provider theo task |
| `process_runs` | id, session_id, status, started_at, ended_at, exit_code, outcome_json | Moi lan goi CLI |
| `handoffs` | id, from_assignment_id, to_role_id, task_id, type, payload_json, created_at | Giao tiep noi bo co cau truc |
| `artifacts` | id, task_id, run_id, path, sha256, type, verified_at | San pham va chung cu |
| `reviews` | id, task_id, reviewer_assignment_id, decision, evidence_json | Review pass/fail/rework |
| `approvals` | id, work_order_id, task_id, kind, status, prompt, response, resolved_at | Xin phep khach |
| `decisions` | id, work_order_id, scope_version, actor, kind, rationale, details_json | Lich su quyet dinh |
| `usage_events` | id, run_id, source, tokens_in, tokens_out, estimate_cost, currency | Chi phi/hinh thuc do |
| `events` | id, aggregate_type, aggregate_id, event_type, payload_json, at | Audit + recovery |
| `provider_registry` | id, executable, version, capabilities_json, health, last_probe_at | CLI health |

### 9.3. Minimum schema example

```sql
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS work_orders (
  id TEXT PRIMARY KEY,
  customer_request TEXT NOT NULL,
  status TEXT NOT NULL,
  current_scope_version INTEGER NOT NULL DEFAULT 0,
  constraints_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(id),
  plan_version INTEGER NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  role_hint TEXT,
  priority INTEGER NOT NULL DEFAULT 50,
  risk TEXT NOT NULL DEFAULT 'low',
  attempts INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 0,
  acceptance_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_dependencies (
  task_id TEXT NOT NULL REFERENCES tasks(id),
  depends_on_task_id TEXT NOT NULL REFERENCES tasks(id),
  PRIMARY KEY(task_id, depends_on_task_id),
  CHECK (task_id <> depends_on_task_id)
);
CREATE TABLE IF NOT EXISTS assignments (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id),
  role_id TEXT NOT NULL,
  provider_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_sessions (
  id TEXT PRIMARY KEY,
  assignment_id TEXT NOT NULL REFERENCES assignments(id),
  provider_id TEXT NOT NULL,
  provider_session_id TEXT,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  closed_at TEXT,
  UNIQUE(assignment_id, provider_id, id)
);
CREATE TABLE IF NOT EXISTS process_runs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES agent_sessions(id),
  status TEXT NOT NULL,
  cwd TEXT NOT NULL,
  exit_code INTEGER,
  output_ref TEXT,
  error_ref TEXT,
  started_at TEXT,
  ended_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(work_order_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_session ON process_runs(session_id, started_at);
```

**Note:** Day la subset minh hoa de xac dinh semantic; migrations phai tao cac bang con lai va index. Khong copy schema vi du roi coi la full DB.

### 9.4. Atomic claims and idempotency

- Scheduler dung transaction: `UPDATE tasks SET status='CLAIMED', version=version+1 WHERE id=? AND status='READY' AND version=?`; khong co row affected -> mot scheduler khac da claim.
- Moi lan dispatch co `idempotency_key`/run ID duy nhat. Khi restart, khong tao hai process run cho cung dispatch.
- Event `RUN_DISPATCHED`, `RUN_STARTED`, `RUN_FINISHED`, `REVIEWED`, `TASK_COMPLETED` ghi cung state transition trong transaction neu co the.
- Neu `RUNNING` sau crash: verify process identity (pid + start timestamp) neu co, reconcile output/artifacts; `UNKNOWN_AFTER_CRASH` va manual review neu co tac dong ngoai khong biet.

---

## 10. STANDARD CONTRACTS GIUA CAC AGENT

### 10.1. Inbound work order

```json
{
  "id": "WO-2026-001",
  "customer_message": "Toi muon phan mem quan ly kho re, de su dung",
  "constraints": {
    "platform_preference": "unspecified",
    "budget_ceiling": null,
    "deadline": null,
    "deployment_scope": "local_only"
  },
  "attachments": [],
  "language": "vi"
}
```

### 10.2. Clarification contract

```json
{
  "summary_for_customer": "Ban muon quan ly nhap, xuat va ton kho don gian.",
  "known_facts": ["Muon su dung don gian"],
  "important_unknowns": ["Co bao nhieu cua hang?"],
  "need_customer_reply": true,
  "next_question": "Ban dung cho mot cua hang hay nhieu chi nhanh?",
  "why_it_matters_internal": "Anh huong scope va du lieu, khong nhat thiet hien cho khach",
  "assumptions": [],
  "confidence": "medium"
}
```

`next_question` toi da **mot** cau uu tien cao khi default; chi hoi nhieu hon neu khach yeu cau.

### 10.3. Feature advisory result

```json
{
  "options": [
    {"id":"lean", "label":"Tiet kiem", "features":["nhap kho","xuat kho","ton kho"], "omitted":["barcode","bao cao nang cao"], "estimated_effort":"S", "ongoing_cost":"thap", "assumptions":["mot cua hang"]},
    {"id":"balanced", "label":"Can bang", "features":["nhap kho","xuat kho","ton kho","tim kiem"], "omitted":["barcode"], "estimated_effort":"M", "ongoing_cost":"thap", "assumptions":["mot cua hang"]}
  ],
  "requires_scope_approval": true,
  "unsupported_price_claims": false
}
```

Neu khong du du lieu de tinh gia bang tien, he thong chi duoc dua ra effort band, chi phi dinh tinh va noi ro can xac minh.

### 10.4. Task plan contract

```json
{
  "work_order_id": "WO-2026-001",
  "scope_version": 1,
  "plan_version": 1,
  "tasks": [
    {"id":"TASK-1","title":"Dac ta chuc nang","role_id":"business_analyst","depends_on":[],"priority":10,"risk":"low","deliverables":["spec.md"],"acceptance":["xac nhan scope"]},
    {"id":"TASK-2","title":"Thiet ke luu tru","role_id":"system_architect","depends_on":["TASK-1"],"priority":20,"risk":"medium","deliverables":["architecture.md"],"acceptance":["co schema va luat du lieu"]},
    {"id":"TASK-3","title":"Cai dat chuc nang","role_id":"backend_engineer","depends_on":["TASK-2"],"priority":30,"risk":"medium","deliverables":["code"],"acceptance":["test pass"]}
  ]
}
```

Task Planner **khong duoc** tu truyen `DONE`, `approved`, `spent` hay `provider_session_id` trong proposal. Engine gan ID thuc neu can, validate DAG va permission.

### 10.5. Worker output contract

```json
{
  "task_id": "TASK-3",
  "run_status": "completed",
  "summary": "Da cai dat nhap/xuat kho",
  "files_modified": ["src/inventory.py"],
  "evidence": [
    {"type":"test_result","ref":"artifacts/TASK-3/pytest.txt","claimed_status":"passed"}
  ],
  "unresolved_issues": [],
  "requested_handoff": null,
  "recommendation": "ready_for_review"
}
```

Engine verify cac duong dan artifacts, hashes va test results; **khong tin `claimed_status` neu chua xac minh**.

### 10.6. Internal handoff

```json
{
  "from_role":"backend_engineer",
  "to_role":"frontend_engineer",
  "task_id":"TASK-3",
  "type":"contract_question",
  "question":"API tra truong `quantity` la int hay decimal?",
  "evidence_refs":["architecture.md"],
  "reply_required":true
}
```

## 11. BUDGET, CLI ROUTER VA TAI NGUYEN

### 11.1. Hai so tien can phan biet

1. **Customer budget:** ngan sach cho scope, tai nguyen/phu phi, chi phi su dung lau dai. Khong gan gia tien tuy tien cho token CLI da duoc subscription cap.
2. **Internal execution budget:** gioi han mot run, tong runs/task, total wall-clock, concurrency, CLI quota status, token usage *neu CLI bao cao*. Co the dung don vi proxy: run count/elapsed minutes/attempts khi chi phi tien thuc la unknown.

### 11.2. Configuration du kien

```toml
[office]
language = "vi"
concurrency = 1
max_replans_per_work_order = 3
max_handoffs_per_task = 6
max_rework_cycles_per_task = 2

[limits]
max_runs_per_task = 4
run_timeout_seconds = 900
max_total_runs_per_work_order = 40
max_reported_tokens_per_work_order = 300000

[routing]
strategy = "cheapest_capable_available"
provider_preference = ["codex", "gemini", "claude"]

[permissions]
allow_production_deploy = false
allow_delete_outside_workspace = false
allow_unreviewed_external_spend = false
```

Cac con so tren la **sample config**, chua phai gia tri toi uu da duoc do. `max_reported_tokens` chi hard-stop neu usage day du; neu unknown thi dua vao gioi han runs/time va hien canh bao.

### 11.3. CLI router - policy

- `capability fit`: chon provider co hanh vi/phien ban phu hop read-only, code-edit, test, resume.
- `health`: mat auth/quota thi khong dispatch; khong co `remaining quota` chinh thuc -> hien `unknown`.
- `cost`: khong khoi dong provider thu hai neu cai thu nhat du kha nang cho task don gian.
- `retry`: loi transient co backoff co gioi han. Loi validation task -> can plan/rework, khong goi lai y chang vo han.
- `fallback`: khi doi provider, tao handoff summary voi source evidence va new session.
- `quality`: khi QA ket luan khong dat, quay ve developer cu neu con phu hop; doi provider neu co bang chung repeat fail.
- Khong su dung bat ky cach nao de bypass quota, sharing authorization hoac violation terms.

### 11.4. Chi phi vong doi san pham

Scope advisor phai phan tich ca chi phi xay lan dau va chi phi sau nay: hosting, backup, database, dich vu ben thu ba, domain, bao tri, bien phi. Gia tri chua co nguon phai danh dau `unknown`, khong tao gia uoc tinh fake.

---
## 12. QUALITY GATES VA REVIEW

### 12.1. Evidence first

- `run.succeeded` -> `task.OUTPUT_READY`, KHONG phai `task.DONE`.
- QA/reviewer phai doi chieu output voi acceptance criteria va evidence: diff, command/test report, file, logs, behavior.
- `test pass` cua agent la claim; engine co gang tu chay test command da phe duyet hoac xac minh artifact goc, ghi `verified_by` va `verified_at`.
- Work item `research` co evidence la nguon, phuong phap, ket luan, rui ro/chua xac minh. Work item `design` co traceability voi yeu cau va decision record.
- RUI RO CAO: thao tac permission, auth, financial, xoá du lieu, security -> reviewer va approval kho hon; khong duoc cat de tiet kiem.

### 12.2. Review decisions

- `PASS`: evidence hop le va scope duoc dap ung.
- `REWORK`: issue_list actionable, assign lai role phu trach, tang rework cycle, dung/tao session theo quy tac.
- `NEEDS_CUSTOMER`: can xu ly conflict trong nhu cau, ngoai ranh gioi role; BA + Representative hoi khach.
- `BLOCKED`: service/test dependency/tool inaccessible; state, reason, owner ro rang.
- `FAIL`: khong the tiep tuc an toan/chi phi vuot nguong; PM bao cao, khong claim success.

### 12.3. Definition of Done - cac loai task

| Loai | Evidence bat buoc |
|---|---|
| Fix bug | Reproduction steps/expected behavior, diff, regression test |
| Them tinh nang | Acceptance criteria, source diff, relevant automated tests, usage notes |
| Refactor | Source diff, tests, explanation why behavior not changed |
| Design | Architecture decision record, interfaces, risks, trade-offs |
| Research | Sources checked, methodology, limitations, actionable conclusion |
| Packaging | Build command, build result, artifact/hash, run instructions |

Project/Work Order chi `DELIVERED` khi tat ca MUST features co ket qua da kiem chung hoac exception da duoc khach dong y, khong con blocker critical dang giau.

---

## 13. CO CHE TRAO DOI VOI KHACH HANG KHI PHAT SINH VAN DE

1. Ky su ghi `customer_clarification_required` trong handoff; BA xac dinh co thuc su can khach quyet dinh khong.
2. Neu chi la quyet dinh ky thuat noi bo (framework, schema, dependency): Architect quyet dinh theo rule, khong hoi khach.
3. Neu lien quan den nhu cau, thoi gian, gia, cam ket hoac cach su dung: Representative dich thanh **cau hoi doi thuong**, co giai thich de hieu va lua chon de xuat.
4. Ket qua tra loi luu vao decisions va scope version neu anh huong pham vi; cap nhat affected tasks.
5. Khi client noi `khong biet`: uu tien lua chon mac dinh an toan, de dung, it ton kem; neu van rui ro lon thi can hoi them mot van de cu the.
6. Chat text dung ngon ngu tu nhien; khong trao so do API, stack trace, JSON errors, schema cho khach tru khi ho chu dong yeu cau.

**Vi du:**

- Noi bo: `Transactional consistency khi offline sync phuc tap va tang chi phi`.
- Hoi khach: `Neu mat Internet, nhan vien co can tiep tuc su dung khong? Neu khong can, minh co the lam phien ban don gian va it ton kem hon.`

---

## 14. SECURITY, PRIVACY, PERMISSION MODEL (KHONG THIET KE SANDBOX)

### 14.1. Threat assumptions

- User input, repository, README, pull request, comments va file du an deu co the chua noi dung khong dang tin. AI phai coi day la **du lieu**, khong phai lenh cap quyen.
- Chay native Windows duoi tai khoan dang nhap co nhieu quyen OS; **path allowlist va Git Worktree khong cung cap cach ly OS**. Ban dau chi su dung repo tin cay, khong mo quyen admin.
- Nen co ban sao luu du lieu, file state truoc task co tac dong ghi; han che read/write buoc vao khu vuc cung cap cho CLI, biet rang no khong the chong mot CLI co quyen he dieu hanh.
- Tuyet doi khong lay credential trong auth storage cua Claude/Codex/Gemini; `doctor` xem readiness ma khong doc token.

### 14.2. Permission tiers

| Tier | Hanh dong | Xu ly |
|---|---|---|
| P0 | Phan tich, doc tai lieu trong project, de xuat | Cho phep |
| P1 | Ghi file source trong project, chay test duoc phep | Cho phep theo task/project config, phai log |
| P2 | Install packages, can network, chay migration du lieu dev | Xin phep theo policy/nguon cung cap va test thuc te |
| P3 | Xoa hang loat, production deployment, truy cap credentials, thu phi ngoai | Phai co approval ro rang; MVP khong tu dong |

**Khong co sandbox = khong co dam bao ngam chan thao tac OS.** Permission enforcement chua hoan chinh khong duoc duoc quang cao la an toan. Neu provider CLI khong the tu dong chay P1 ma khong pha policy, app tam dung va yeu cau operator thao tac/chap nhan, khong bat bypass mac dinh.

### 14.3. Logs and data governance

- Store progress summaries; raw prompts/outputs chi khi can debug va chi trong thu muc co quyen phu hop; redact obvious secrets/tokens trong logs va audit neu co the.
- Ho tro `purge work order` sau canh bao va backup, khong phai git rm tam thoi.
- Khong tu gui ma nguon/du lieu nhay cam sang provider ngoai khi khach chua chap nhan chinh sach xu ly du lieu cua CLI.
- Developer phai ghi ro su khac biet giua 'chay local CLI' va 'xu ly model tu xa'. Dang nhap local KHONG co nghia du lieu khong ra mang.
- License/terms cua tung provider phai duoc operator tu xac nhan; khong dam bao moi subscription cho phep cung cap dich vu cho ben thu ba.

---

## 15. PROJECT STRUCTURE CHO CODING AGENT

```text
aatpo/
  pyproject.toml
  README.md
  LICENSE                     # chi chon khi duoc owner quyet dinh
  .gitignore
  config/
    office.example.toml
    provider_profiles.example.toml
  roles/
    client_representative.md
    business_analyst.md
    office_manager.md
    system_architect.md
    frontend_engineer.md
    backend_engineer.md
    qa_engineer.md
    devops_engineer.md
  src/aatpo/
    __init__.py
    main.py                    # Typer commands
    config.py                  # Pydantic settings
    domain/
      models.py                # typed entities + enums
      transitions.py           # state transition policy
      policies.py              # approvals and resource limits
    db/
      connection.py
      repository.py
      migrations/
        0001_initial.sql
    customer/
      representative.py
      analyst.py
      discovery.py
      scope_advisor.py
    office/
      planner.py
      scheduler.py
      router.py
      manager.py
      quality.py
      cost.py
    agents/
      profiles.py
      prompt_builder.py
      session_manager.py
      handoff.py
    cli/
      base.py
      launcher_windows.py
      codex_adapter.py
      claude_adapter.py
      gemini_adapter.py
      parsers.py
      health.py
    workspace/
      git_workspace.py
      artifacts.py
      evidence.py
    telemetry/
      events.py
      redact.py
      reports.py
  tests/
    unit/
      test_state_transitions.py
      test_planner_validation.py
      test_session_isolation.py
      test_router_policy.py
      test_budget_caps.py
      test_prompt_boundary.py
      test_evidence.py
    integration/
      test_sqlite_recovery.py
      test_mock_adapter_workflow.py
      test_windows_launcher_fakecli.py
      test_cli_contract_parsers.py
    acceptance/
      test_small_task.py
      test_product_scope.py
      test_resume_rework.py
      test_quota_pause.py
    fixtures/
      fake_cli.py
      sample_work_orders.json
      sample_codex_events.jsonl
      sample_claude_response.json
      sample_gemini_response.json
  docs/
    architecture.md
    operations.md
    permissions.md
    customer_language_policy.md
    acceptance_matrix.md
    cli_compatibility.md
  .aatpo/                    # generated run state; gitignored
```

Nguon code khong duoc ghi auth data; `office.example.toml` chi la sample. `repo`, `.aatpo` va personal data paths duoc cau hinh rieng.

---

## 16. TERMINAL UX MVP - COMMAND CONTRACT

V1 chi can text TUI/CLI; chua phai giao dien web.

```powershell
# Kiem tra runtime/versions; mac dinh khong goi LLM
ato doctor

# Tao yeu cau moi tu text; customer la nguoi khong can biet ky thuat
ato request create "Toi muon phan mem quan ly kho don gian, it chi phi"

# Office advisor hoi khach neu can; --dry-run khong cho phep thao tac ghi nguy hiem
ato request discuss WO-2026-001

# Xem tinh nang NEED/SHOULD/LATER/DROP va lua chon tiet kiem
ato scope show WO-2026-001
ato scope approve WO-2026-001 --option lean

# Len plan sau khi duoc xac nhan
ato plan WO-2026-001
ato tasks WO-2026-001

# Tiep tuc van phong trong gioi han nguon luc
ato run WO-2026-001

# Kiem tra run, task, danh sach can duyet
ato status WO-2026-001
ato approvals WO-2026-001

# Resume workflow cua work order, KHONG phai 'resume latest' cua CLI
ato resume WO-2026-001

# Ket qua, log da loc secret, evidence
ato report WO-2026-001
ato doctor --smoke-readonly             # chi goi CLI khi operator chap nhan
```

`ato` la ten command mong muon, khong phai tool da co san. Tham so cu the co the tinh chinh trong implementation sau khi co integration tests, nhung **nhom hanh vi** va tinh chat non-destructive phai duoc giu.

**Default:** `doctor` khong thuc hien network request/model call; `--smoke-readonly` neu muon check CLI login bang request thuc, thong bao ro su dung quota.

---

## 17. ROLE PROFILE TEMPLATE VA PROMPT COMPOSITION

### 17.1. Profile chung

```yaml
role_id: backend_engineer
version: 1
purpose: "Implement backend tasks according to confirmed requirements"
customer_facing: false
responsibilities:
  - implement code within assigned task scope
  - add relevant tests
  - report evidence and limitations
permissions:
  - read_project
  - write_allowed_paths
  - run_approved_tests
prohibited:
  - approve_customer_scope
  - mark_task_done_without_review
  - access_unrelated_projects
expected_output_schema: "worker_result.v1"
```

### 17.2. Prompt assembly order

1. **Trusted system policy:** Rules cua van phong: role identity, task scope, safety, data boundaries, schema output, communication policy.
2. **Approved work order context:** confirmed scope version, business glossary, acceptance.
3. **Assigned task brief:** objective, allowed paths, expected artifacts, known dependencies.
4. **Relevant project knowledge:** architecture decisions, API contracts, short summaries.
5. **Tool/provider-specific hints:** parsed `--help` profile, permission behavior; no secret.
6. **Untrusted materials:** user files/repo/chat snippets duoc danh dau la DATA; khong cap chuc nang dieu hanh.
7. **Output contract:** schema, evidence requirements, action if blocked.

**Budget-aware:** prompt builder chi nap tai lieu can thiet va co gioi han; khong copy all office chat vao moi task. Trong MVP co the dung markdown context, chua can vector retrieval.

---

## 18. EXECUTION PLAN - MILESTONES VA ACCEPTANCE

### M0 - Project foundation (khong can CLI that)

Implement: package layout, configs, database migration, core entities, state transition validation, fake CLI adapter, event logger, tests.

Pass khi:
- `pytest` chay xanh tren Windows va CI-compatible environment.
- `work_order -> task -> assignment -> session -> run` co ID rieng va DB persistence.
- Fail-fast khi config invalid; backup/migration path hoat dong.

### M1 - Windows CLI runtime + exact session ledger

Implement: `ato doctor`, binary probing, launcher `.exe/.cmd`, Codex/Claude/Gemini adapters co the enable tung cai, standard output parser, timeout, run/retry, session resume-by-ID, log filtering.

Pass khi:
- Tren Windows user profile, phat hien CLI da installed; CLI missing duoc bao ro, khong crash.
- Mot **read-only** task qua 1 provider da login, nhan structured output, luu `provider_session_id` neu co, parse khac nhau JSONL/JSON.
- Mot provider la du; khong ep cai du 3.
- Fake CLI simulate hang/exit 1/malformed JSON/verbose log; app recover dung.
- New task KHONG tai su dung session cua task cu, du same role/provider.

### M2 - Customer gateway + low-cost scope advisory

Implement: Representative, BA, classification, `WAITING_CUSTOMER`, feature shortlist, lean/balanced proposals, approval flow, scope versioning.

Pass khi:
- `Toi muon app quan ly kho re` -> hoi lai de hieu ve 1 unknown quan trong, khong hoi stack.
- `Toi khong biet` -> de xuat default va giai thich tac dong.
- Scope co MUST/SHOULD/LATER/DROP; lean vs balanced co trade-offs.
- Chua approve thi khong thuc thi task viet code cho product scope moi.

### M3 - Office manager, task scheduler, handoffs

Implement: planner JSON contracts + DAG validator, scheduler, role routing, assignments, run engine, handoffs, approvals, pause/resume work order. LangGraph **chi chen vao neu co loi ich ro**, SQLite la source-of-truth.

Pass khi:
- 1 task don: work order -> 1 staff role -> results -> evidence.
- 1 product: BA/Architect -> Dev -> QA, bao gom dependencies.
- Task independent co the duoc queue, concurrency=1 default.
- Provider fail/quota -> PAUSED, tiep tuc khi ready hoac fallback provider neu operator allow.
- Worker khong duoc ghi `DONE` truc tiep; QA/review policy quyet dinh.

### M4 - Real production workflow

Implement: project workspace, Git diff, automated relevant tests, defect feedback loop, packaging, customer-friendly delivery report.

Pass khi:
- Thuc hien mot repo test nho, tao source diff, run tests, reviewer check; QA reject thi rework co limit.
- Thanh pham co artifact + hash + huong dan chay/thong tin chua hoan thanh.
- Khong co thao tac production deploy, network spend, credential reads without approved workflow.

### M5 - Reliability and optimization (sau khi M0-M4 on dinh)

Implement: provider routing based on actual success/fail metrics, smarter summary, plan recalc, optional graph checkpoint, workload/usage dashboard o terminal, parallel run=2 voi resource locks.

Pass khi:
- Kiem thu crash/restart, task status khong loi; khong replay non-idempotent action mu quang.
- Du lieu response tu provider bi thay doi schema -> adapter bao parse error, khong mislabel as success.
- Chi phi quan sat duoc qua run counts/time/tokens neu available; khong bịa so tien.

**Rule:** Chua dat acceptance milestone truoc, khong trien khai milestone tiep theo voi assumption la hoat dong.

---

## 19. TEST SCENARIOS BAT BUOC

| Test ID | Scenario | Pass conditions |
|---|---|---|
| T01 | Codex-only / Gemini-only / Claude-only | Chi mot CLI ready van xu ly duoc minimal task |
| T02 | Same CLI, 3 roles | 3 distinct AgentSessions, correct role profiles |
| T03 | Same role, 2 different tasks | 2 isolated CLI session IDs / fallback brief, no cross-task chat |
| T04 | Same task rework | Exact ID resume neu supported, khong dung `latest` |
| T05 | Switch CLI mid-task | Handoff summary, new session, preserved task history |
| T06 | Missing CLI/not logged in | Health = missing/not_authenticated; no silent failure |
| T07 | CLI quota exhausted | Pause and bounded fallback; no bypass quota |
| T08 | Malformed JSON / nonzero exit | Run failed/parse error; task not DONE |
| T09 | Windows `.cmd` path has spaces | Command works or explicit unsupported, never shell injection |
| T10 | Special chars in customer prompt | Input treated as data; no command shell evaluation |
| T11 | Crash after process start | Reconcile / UNKNOWN_AFTER_CRASH; no double write |
| T12 | DAG cycle / missing dependency | Planner rejected, deterministic error |
| T13 | QA finds bug | Rework with bounded attempts, verified evidence |
| T14 | Customer does not know technology | Plain language question with suggested default |
| T15 | Customer budget limited | Lean option, defer extras, never silently drop MUST |
| T16 | Customer scope changes | New version, affected tasks reprioritized, audit kept |
| T17 | Approval needed | Paused before destructive/paid/production actions |
| T18 | User tries to cause prompt injection | Repository data not elevated to trusted instructions |
| T19 | Back-to-back work orders | Project memory isolated; shared company rules retained |
| T20 | Final handover | Artifacts validated, test evidence, acceptance report |

Implement unit tests + fake CLI first. Tests T01/T06/T09/T11/T17 can require real Windows runner/manual smoke cases; mark exact evidence and status, khong tinh mock la chung minh Windows integration.

---

## 20. OFFICIAL REFERENCES TO VERIFY BEFORE IMPLEMENTING ADAPTERS

Yeu cau doc official docs va `--help` tren may dich; cac flag/version co the thay doi. Day la URL tham khao, khong duoc coi la cam ket flag se tu dong hoat dong tren moi version.

- OpenAI Codex CLI: https://github.com/openai/codex
- Codex CLI references: https://developers.openai.com/codex/cli/reference
- Codex non-interactive example: https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex
- Claude Code CLI/headless: https://code.claude.com/docs/en/headless
- Gemini CLI headless/JSON: https://geminicli.com/docs/cli/headless/
- Gemini CLI session/UUID resume: https://geminicli.com/docs/cli/session-management/
- Gemini CLI command flags: https://geminicli.com/docs/cli/cli-reference/
- LangGraph sqlite checkpoint (optional): https://reference.langchain.com/python/langgraph.checkpoint.sqlite
- SQLite transaction / WAL: https://www.sqlite.org/wal.html
- Git Worktree: https://git-scm.com/docs/git-worktree

**Verification at implementation:** install/version/login mechanism, subscription automated usage terms, headless output JSON, request permissions in noninteractive mode, resume-by-ID, stderr schema, exit codes, Windows path behavior.

---

## 21. HANDOFF INSTRUCTIONS FOR ANOTHER CODING AGENT

### 21.1. Source of truth and constraints

Doc nay la ban spec ky thuat doc lap. Neu co cac file V1.1/V2.0 thi chung la bo sung; truong hop conflict **yeu cau moi nhat: Windows native + logged-in CLI + separate task sessions + no sandbox design** va security gates cua file V3.1 la uu tien.

Coding agent phai:

1. Doc het spec nay. Tom tat nhung requirement da chot truoc khi coding.
2. Khong tu tao web UI; khong tu chuyen sang LLM API/paid gateway.
3. Khong tu them 8 processes luon chay; Role khong phai process.
4. Khong tu them sandbox project; nhung phai ton trong permission policy va thong bao security limitation.
5. Khong doc hoac xuat token cua CLI da login; dung official CLI process.
6. Khong tu bat permission-bypass CLI flags; timeout va pause khi can approval.
7. Khong tu y viet mot all-in-one monolith ko co contracts/tests.
8. Khong tu giai quyet bang cach thay Session ID bang history chung, 'resume latest'.
9. Bat dau bang M0, M1 voi mock/fake provider; huong dan real Windows smoke test tach biet.
10. Moi milestone giao source, tests, migration, sample config, run instructions, notes ve hang muc chua xac minh.

### 21.2. Exact starter instruction for coding agent

> Ban la coding agent duoc giao xay dung AATPO. Hay doc toan bo file `AATPO_Implementation_Blueprint_V3.1.md`. Khong can xem lich su chat. KHONG viet het he thong mot lan. Hay bat dau **M0**: tao repo Python, Pydantic domain, SQLite schema/migration, entities `CLIProvider`, `AgentRole`, `Task`, `AgentSession`, `ProcessRun`, state transitions, fake CLI adapter, unit tests. Bao dam CLI != Role != Task != Session != Run, co ID rieng va khong loai nao su dung lich su task khac. Chay pytest va bao cao ket qua. Sau M0 moi thuc hien M1 voi probe Windows native/official CLI. Khong buoc API key, khong giao dien web, khong sandbox, khong bypass auth/permission. Neu co phan spec mau thuan hoac khong the tu dong hoa an toan, bao ro thay vi doan.

### 21.3. Minimum delivery manifest for each milestone

- `README.md`: prerequisites, setup, config, exact commands, known limitations.
- Source code + pinned dependencies (`pyproject.toml` with lock as appropriate).
- Database migration + backup procedure.
- Tests + report showing executed tests, environment, failing/skipped cases.
- Example fixture workflow and sample report output.
- CHANGELOG of decisions made vs original spec.
- Unverified areas, risks, next step.

---

## 22. ACCEPTANCE GATE FOR COMPLETE AATPO MVP

System chi duoc coi la MVP khi minh chung **end-to-end** tren Windows voi it nhat mot CLI da authenticated:

1. Khach nhap mot mong muon bang tieng Viet, chua ro ky thuat.
2. Agent giao tiep dua ra cau hoi lam ro phu hop, tiep nhan cau tra loi `khong biet` va de xuat lua chon.
3. Agent de xuat pham vi tiet kiem vs can bang, giai thich tinh nang bo qua va cho khach xac nhan.
4. Office Manager tao task DAG nho co role, dependencies, acceptance.
5. He thong xu ly it nhat mot task bang official CLI headless tren Windows native, luu run logs/exit status.
6. Hai vai tro su dung cung mot CLI nhung **session khac nhau**; task thu hai cua cung role co session moi.
7. Ket qua task duoc QA/reviewer verify bang test/file evidence, co it nhat mot scenario rework.
8. Qua trinh bi tam dung/crash duoc tiep tuc tu SQLite state ma khong mat task, khong dung CLI `latest`.
9. Khi provider unavailable/quota, cong viec pause ro rang; chi fallback neu config/policy cho phep.
10. Khach nhan bao cao than thien, san pham va thong tin ve nhung chuc nang chua lam, khong bi hieu nham la da hoan thanh.

Neu mot trong cac dieu tren chua duoc kiem chung tren Windows **thi MVP chua duoc nghiem thu**.

---

## 23. GLOSSARY / CACH HIEU THONG NHAT

| Tu | Nghia trong AATPO |
|---|---|
| Customer / Khach hang | Nguoi noi mong muon; khong can biet tech |
| Work Order | Yeu cau dau vao, co the la task don hoac product project |
| Role / Nhan vien logic | Identity + instructions + permissions; khong phai 1 CLI subscription |
| Provider / CLI Runtime | Official command `codex`/`claude`/`gemini` dang login |
| Task | Cong viec co input/output/acceptance ro rang |
| AgentSession | Ngu canh 1 role trong 1 task; co internal ID va provider ID neu ho tro |
| ProcessRun | Mot lan bat CLI, co thoi gian, status, usage, logs |
| Handoff | Ket qua/cau hoi/decision giua role co traceability |
| Scope | Tap tinh nang da duoc khach lua chon va phe duyet |
| Evidence | Bang chung ket qua co the xac minh, khong phai loi tuyen bo cua AI |
| Quality gate | Kiem tra buoc phai vuot qua truoc khi Done/Delivered |
| Cost controller | Quan ly han muc thuc thi va scope, khong tu bịa gia |

---

## 24. END OF IMPLEMENTATION BLUEPRINT - V3.1

**One-line architecture:** `Customer -> Customer Gateway -> Office Manager/Task DAG -> Role profiles -> Task-scoped Sessions -> Windows authenticated CLI adapters -> Real artifacts -> QA/Delivery`, with `SQLite + Git + evidence + budget/approval policy` across all layers.

**Critical invariant:** `One installed logged-in CLI can execute many logical roles, but roles and tasks must not share one undifferentiated CLI conversation history.`

**Out of scope now:** web UI, SaaS multi-tenant, payment/business growth, public publishing, full OS sandboxing, credential sharing, additional LLM API billing.

**Document status:** Complete architecture and engineering requirements; *not* proof of a working system. Actual CLI compatibility must be established on the target Windows installation via explicit tests.
