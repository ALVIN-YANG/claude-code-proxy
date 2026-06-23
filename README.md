# Claude Code Proxy (for Gemini 3.5)

这是一个高性能、高兼容性的本地大模型中转代理服务。专门用于解决在使用 **Claude Code CLI** 时，将后端供应商热切换至 **Gemini 3.5 Flash / Pro** 时所面临的多轮工具调用挂流、断流、或者是 RECT-001/RECT-002 思考整流错误问题。

---

## 🌟 解决的痛点

在使用 `cc-switch` 转换 Claude Code 流量到 Google Gemini 官方 OpenAI 兼容端点（Generative Language API）时，主要会遇到以下阻碍：

1. **RECT-001/002 异常断流**：Gemini 3.x 模型的响应流中包含了大量的 `extra_content.google.thought_signature` 字段和空的思考整流块。这会触发 `cc-switch` 自带的整流 validator，导致流式传输在中途被掐断，客户端显示 `stream hung up` 或直接退回/切换。
2. **多轮工具调用挂起**：Gemini 3.x 强校验多轮对话中的 `thought_signature`。在后续的多轮请求中，如果 `assistant` 角色的 `tool_calls` 没有携带先前生成的 `thought_signature`，上游 API 会直接拒绝请求。
3. **报文协议不兼容**：Anthropic 协议中的 `tool_result` 字段若被简单地拼接为 `user` 文本，会导致 Gemini 拒绝在第二轮继续执行，提示 “You should have executed the tool call...”，进而导致任务中断。
4. **首字延迟 (TTFB) 偏高**：传统的代理为每次流请求新建 HTTP 客户端连接，导致大量的 TLS/SSL 握手网络开销（尤其在跨境网络下耗时可达 1-2 秒）。

---

## 🚀 核心特性

- **直接 SSE 流式中转（绕过 LiteLLM）**：摒弃不稳定的中间件，直接用极简的 `httpx` 处理 SSE 流。精细化过滤纯文本思考包装块（Thinking Wrappers）并剥离 `extra_content`，向下游输出绝对干净、标准的原生 Anthropic SSE 格式。
- **自动 Thought Signature 注入**：高度还原 `Openclaw` 架构下的注入机制。自动在多轮对话的 `assistant` 工具调用节点中，补全 `skip_thought_signature_validator`，避免 Google 端多轮请求拒绝。
- **高合规的多轮工具链映射**：重构请求转换状态机。将 Anthropic 协议下的 `tool_result` 转换为 OpenAI 最严格、最合规的 `role: "tool"` + `tool_call_id` 形式，彻底解决多轮工具链的断点挂起。
- **HTTPX 全局连接池复用 (Keep-Alive)**：通过全局维护异步 HTTP 客户端 pool，消除了每一次 API 调用的 SSL 握手延迟，极大提升了首字响应速度（TTFB）。

---

## 🛠️ 快速开始

### 1. 克隆并进入目录
确保将本项目放置于持久存放的目录：
```bash
cd "/Users/ylq/Documents/AI编程技巧/claude-code-proxy"
```

### 2. 创建并激活虚拟环境
使用 `uv`（推荐）或 `venv` 创建 Python 虚拟环境并安装依赖：
```bash
# 使用 uv (极速)
uv venv
source .venv/bin/activate
uv pip install fastapi uvicorn httpx pydantic python-dotenv litellm

# 或使用标准 venv
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx pydantic python-dotenv litellm
```

### 3. 配置环境变量
复制模板生成私有的配置文件 `.env`：
```bash
cp .env.template .env
```
编辑 `.env` 填入你的 Google AI Studio 的 Gemini API Key：
```env
ANTHROPIC_API_KEY="dummy-anthropic-key"
OPENAI_API_KEY="YOUR_GEMINI_API_KEY"      # 填入你的 AIzaSy... Key
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"      # 填入你的 AIzaSy... Key

PREFERRED_PROVIDER="openai"
BIG_MODEL="gemini-3.5-flash"
SMALL_MODEL="gemini-3.5-flash"
OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
```

### 4. 本地启动服务
在开发环境启动调试，或者在后台常驻运行：

- **前台调试运行**：
  ```bash
  python -m uvicorn server:app --host 127.0.0.1 --port 8082 --reload
  ```
- **后台常驻运行 (生产)**：
  ```bash
  nohup uv run uvicorn server:app --host 127.0.0.1 --port 8082 > /tmp/uvicorn-proxy.log 2>&1 &
  ```

---

## 🔗 对接 cc-switch

### 1. 注册本地供应商
在 `cc-switch` 托盘或命令行中添加/注册一个自定义的 Provider（或者通过修改 `~/.cc-switch/cc-switch.db` 注入），将其上游中转地址指向本地代理：

- **名称**：`Gemini 3.5 Flash Proxy`
- **上游 Base URL (ANTHROPIC_BASE_URL)**：`http://127.0.0.1:8082`
- **模型映射**：
  - `claude-opus-4-8` ➡️ `openai/gemini-3.5-flash`
  - `claude-haiku-4-5` ➡️ `openai/gemini-3.5-flash`

### 2. 进行热切换
配置完成后，在 `cc-switch` 菜单中一键热切换到此供应商。

你也可以在 `~/.cc-switch/settings.json` 中，将 `currentProviderClaude` 指定为对应的 Provider ID。切换后，Claude Code CLI 发出的所有请求都会瞬间、无缝地通过本地代理直连 Gemini 3.5 引擎。

---

## 📋 运维和调试

- **检查代理运行状态**：
  ```bash
  ps aux | grep "uvicorn.*8082" | grep -v grep
  ```
- **查看实时中转日志**：
  ```bash
  tail -f /tmp/uvicorn-proxy.log
  ```
- **停止后台服务**：
  ```bash
  pkill -f "uvicorn.*8082"
  ```
