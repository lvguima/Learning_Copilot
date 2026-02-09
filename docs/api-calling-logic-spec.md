# API 调用逻辑与规范（v0.1.1）

最后更新：2026-02-09

本文档说明 Local Review Copilot 的端到端 API 调用链路、运行时接口契约，以及常见排障规则。

## 1) 端到端架构

请求路径如下：

1. 桌面端（Tauri + React）向本地后端 `http://127.0.0.1:8008` 发起 HTTP 请求。
2. 后端（FastAPI）执行扫描、解析、上下文构建，并调用 LLM。
3. LLM 调用有两种 provider：
   - `echo`：调试模式，不发起真实远程请求；
   - `openai_compat`：按 OpenAI 兼容接口 `/chat/completions` 调用。
4. 后端返回 `trace_id` 以及可选的 `citations`/`warnings`。
5. 后端把会话与导出结果落盘到本地 `outputs/`。

## 2) 桌面端启动与 sidecar 生命周期

桌面端 sidecar 逻辑（`src-tauri/src/main.rs`）：

1. 启动时先探测 `127.0.0.1:8008` 是否可用。
2. 若不可用，则启动后端：
   - `python -m uvicorn local_review_copilot.server:app --host 127.0.0.1 --port 8008`
3. 应用退出时，关闭本次桌面端拉起的 sidecar 进程。

Python 解释器选择顺序：

1. `backend/.venv/Scripts/python.exe`（若存在）
2. 环境变量 `LRC_PYTHON_EXEC`
3. 回退到 `python`

## 3) 后端配置模型

运行时配置来源：

- `backend/config.yaml`（由模块路径解析，不依赖当前 shell cwd）

LLM 关键字段：

- `provider`：`echo` 或 `openai_compat`
- `endpoint`：基础地址，例如 `https://api.siliconflow.cn/v1`
- `model`：模型 ID（由服务商定义）
- `api_key_env`：环境变量名（不是密钥明文）
- `timeout_seconds`
- `max_context_tokens`

## 4) Provider 行为规范

### 4.1 `echo`

- 不发起任何远程 API 调用。
- 返回最后一条用户消息，前缀为 `[echo]`。
- 用于本地链路调试。

### 4.2 `openai_compat`

后端组装请求规则：

- URL：`{endpoint.rstrip('/')}/chat/completions`
- Method：`POST`
- Headers：
  - `Authorization: Bearer <env(api_key_env) 的值>`
  - `Content-Type: application/json`
- Body：
  - `model`
  - `messages`
  - `temperature: 0.2`

期望响应格式：

- `choices[0].message.content`

若缺少密钥环境变量，后端报错：

- `Missing API key in env var: <api_key_env>`

## 5) 上下文构建流水线

对 `chat/review/quiz-generate`，流程如下：

1. 扫描工作区（`scan_workspace`），应用：
   - ignore 规则
   - 单文件大小上限
   - 单次文件数上限
   - 支持类型：`md/txt/pdf/png/jpg/jpeg/webp`
2. 文件解析：
   - 文本：utf-8 读取
   - PDF：提取 text layer（`ok`/`degraded`/`failed`）
   - 图片：仅元数据（`image_only`）
3. 上下文切片：
   - 若传入 `selected_paths`，仅使用被选中文件
   - 跳过 `failed` 文档
   - 按 `max_context_tokens * 3` 字符预算裁剪
4. 汇总解析告警，作为 `warnings` 返回前端。

`warnings` 常见示例：

- `图片文件未提取正文：... -> Image metadata only (...)`
- `降级解析：... -> No text layer extracted...`
- `已勾选文件未出现在扫描结果中，请先重新扫描。`
- `未提取到可用文本上下文，结果可能不完整。`

## 6) 对外 API 契约

### 6.1 `GET /health`

- 响应：
  - `{ "status": "ok" }`

### 6.2 `GET /config`

- 响应：
  - `workspace_root_dir`
  - `llm` 对象

### 6.3 `POST /config`

- 请求：
  - `workspace_root_dir`（可选）
  - `llm`（可选）
- 校验：
  - `workspace_root_dir` 必须存在且是目录
  - `llm` 必须通过 schema 校验
- 保存语义：
  - 先更新内存配置
  - 再持久化到 `backend/config.yaml`
  - 持久化失败会回滚内存配置
- 响应：
  - `saved_to`（绝对路径）
  - `workspace_root_dir`
  - `llm`
- 错误码：
  - `400`：无效工作目录或无效 llm 配置
  - `500`：配置保存失败

### 6.4 `POST /scan`

- 请求：
  - `root_dir`（可选；未传则用配置中的工作目录）
- 响应：
  - `trace_id`
  - `count`
  - `documents[]`（`doc_id/path/mtime/size/file_hash/file_type`）
- 错误码：
  - `404`：工作目录不存在
  - `500`：扫描失败

### 6.5 `POST /chat/session`

- 请求：
  - `root_dir`（可选）
  - `message`（必填）
  - `selected_paths`（可选）
- 响应：
  - `trace_id`
  - `answer`
  - `citations[]`
  - `warnings[]`
- 错误码：
  - `502`：LLM 调用失败
  - 扫描相关的 `404`/`500`

### 6.6 `POST /review/run`

- 请求：
  - `root_dir`（可选）
  - `topic`（可选）
  - `selected_paths`（可选）
- 行为：
  - 即使 LLM 失败，也会返回 fallback 复盘结果
- 响应：
  - `trace_id`
  - `report`
  - `exports`（启用时返回 `markdown/json` 路径）
  - `warnings[]`

### 6.7 `POST /quiz/generate`

- 请求：
  - `root_dir`（可选）
  - `count`（默认 `3`）
  - `selected_paths`（可选）
- 行为：
  - 即使 LLM 失败，也会返回 fallback 题目
- 响应：
  - `trace_id`
  - `items[]`
  - `warnings[]`

### 6.8 `POST /quiz/evaluate`

- 请求：
  - `trace_id`
  - `answers[]`
- 响应：
  - `trace_id`
  - `items[]`（含 score/feedback）
  - `exports`
- 错误码：
  - `404`：`trace_id` 不在内存缓存里

### 6.9 `GET /session/{trace_id}`

- 返回指定会话 JSON。
- 若会话文件不存在，返回 `404`。

## 7) 持久化与可追溯性

存储模块（`backend/local_review_copilot/storage.py`）：

- 会话文件：
  - `outputs/sessions/{trace_id}.json`
- 导出文件：
  - `outputs/exports/{YYYY-MM-DD}_{suffix}.md|json`
- 编码规则：
  - UTF-8
  - JSON 使用 `ensure_ascii=False`

## 8) 前端请求行为

前端（`frontend/src/AppV2.jsx`）：

- API 基地址固定为 `http://127.0.0.1:8008`
- 统一超时：`REQUEST_TIMEOUT_MS = 60000`
- 统一错误归一化处理：
  - 后端不可达
  - 请求超时
  - API Key 缺失
  - 工作目录不存在
- 后端 `warnings` 会显示在独立告警面板。

## 9) 运行规则与常见坑

1. `api_key_env` 必须是环境变量名（例如 `SILICONFLOW_API_KEY`），不能填 key 明文。
2. 环境变量必须在后端进程启动时可见。
3. 若环境变量变更，需重启桌面端（或后端）让 sidecar 继承新环境。
4. 若 sidecar 用错 Python，请设置：
   - `LRC_PYTHON_EXEC=D:\anaconda3\envs\learning-copilot\python.exe`
5. `quiz/evaluate` 依赖内存缓存；后端重启后旧 quiz `trace_id` 会失效。

## 10) 推荐冒烟检查（快速）

1. 启动桌面端（`cargo tauri dev`）。
2. 在模型设置中配置：
   - provider：`openai_compat`
   - endpoint：`https://api.siliconflow.cn/v1`
   - model：可用模型 ID
   - api key env：`SILICONFLOW_API_KEY`
3. 保存配置。
4. 扫描目录并勾选文件。
5. 运行 chat/review/quiz，确认：
   - answer/report/items 非空
   - `trace_id` 正常返回
   - citations 存在
   - warnings 仅包含预期的降级/图片提示

## 11) 关键源码位置

- 后端 API：`backend/local_review_copilot/server.py`
- 后端配置：`backend/local_review_copilot/config.py`
- LLM 客户端：`backend/local_review_copilot/llm/client.py`
- 扫描/解析/上下文：
  - `backend/local_review_copilot/scanner.py`
  - `backend/local_review_copilot/loaders/`
  - `backend/local_review_copilot/context_builder.py`
- 持久化：`backend/local_review_copilot/storage.py`
- 前端请求：`frontend/src/AppV2.jsx`
- 桌面 sidecar：`src-tauri/src/main.rs`
