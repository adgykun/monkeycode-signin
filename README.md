<div align="center">

<sub><strong>L0NE-6 · MONKEYCODE SIGNAL</strong></sub>

# MonkeyCode Daily

**MonkeyCode 国内版 / 国际版 · 多账号每日签到 · Cap PoW · 服务端回读**

> 当前版本：**v1.0.0**（2026-11-24） · CN 与 Intl 分别配置、分别执行，Cap 计算后再次读取签到状态

[简体中文](README.md) · [English](docs/README.en.md) · [繁體中文](docs/README.zh-Hant.md) · [日本語](docs/README.ja.md) · [한국어](docs/README.ko.md) · [Português (BR)](docs/README.pt-BR.md)

<img src="https://img.shields.io/badge/Features-CN%20%2F%20Intl-6F42C1?style=for-the-badge" alt="Features" />
<a href="https://github.com/L0NE-6/MonkeyCode-Daily/releases"><img src="https://img.shields.io/github/v/release/L0NE-6/MonkeyCode-Daily?style=for-the-badge&label=Release&color=2ea44f&logo=github" alt="Release" /></a>
<a href="https://github.com/L0NE-6/MonkeyCode-Daily/stargazers"><img src="https://img.shields.io/github/stars/L0NE-6/MonkeyCode-Daily?style=for-the-badge&label=Stars&color=FFC75F&logo=github" alt="Stars" /></a>
<img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Qinglong-4EAA25?style=for-the-badge&logo=linux&logoColor=white" alt="Platform" />
<img src="https://img.shields.io/badge/License-MIT-F472B6?style=for-the-badge" alt="License" />

🔐 Cookie 隔离 · 🌍 CN / Intl · 🧠 Cap PoW · ✅ 服务端回读 · 📢 推送 · 🐧 青龙 · ☁️ Actions

[⚡ 30 秒速览](#quick-look) · [🔁 协议与回读](#protocol) · [🔐 凭据](#credentials) · [🐧 青龙](#qinglong) · [☁️ Actions](#actions) · [⌨️ CLI](#cli-json) · [✅ 成功判据](#success) · [✦ 星轨](#star-trail)

</div>

---

<a id="usage-policy"></a>
## 🚫 使用边界与禁止倒卖

> [!IMPORTANT]
> **官方版本永久免费。** 未经作者书面许可，禁止倒卖、付费包装、搬运引流、冒充作者，或使用作者身份与二维码制造官方授权假象。

本仓库、脚本、部署说明和 Release 下载保持免费公开。禁止将本项目或其轻度改名版本包装为付费资源、内部版、独家版、会员权益、收费课程、代部署服务或包更新服务；禁止搬运到其他账号、群组、频道、网盘、电商平台或付费社群进行涨粉、截流、倒卖和引流；禁止删除作者与版权信息后冒充原创。

完整规则见 [NOTICE.md](NOTICE.md)。第三方以“下载费 / 激活费 / 内部版 / 代部署 / 会员门槛”等名义收费，均与作者无关，请停止付款并保留证据。

---

<a id="quick-look"></a>
## ⚡ 30 秒速览

| 维度 | 说明 |
| :--- | :--- |
| **做什么** | 为 MonkeyCode 国内版和国际版账号执行每日签到。 |
| **输入** | `MONKEYCODE_CN_TOKENS`、`MONKEYCODE_INTL_TOKENS`，每条是 Session 或完整 Cookie。 |
| **流程** | 查询状态 → Cap challenge → 本地求解 → redeem → 提交签到 → 再查状态。 |
| **成功判据** | 提交后 `GET /api/v1/users/wallet/checkin` 返回 `checked_in=true`。 |
| **输出** | 中文文本摘要；当前版本没有 JSON/JSONL 模式。 |
| **依赖** | Python 3.8+，仅 `requests`。 |

---

## 🧭 这是什么 / 覆盖范围

MonkeyCode 脚本同时支持 `monkeycode-ai.com` 国内版和 `monkeycode-ai.net` 国际版。两个站点分别解析账号、分别创建 Session，并按站点域隔离 Cookie。

### 覆盖范围

- 国内版 / 国际版多账号与单账号变量。
- Cookie 或裸 Session。
- Cap challenge、PRNG 向量、本地 PoW 求解和 redeem。
- `checked_in` 严格布尔回读。
- 已签到短路、业务错误、过期 challenge 和未确认状态。
- 可选 PushPlus / Bark / Server酱 / WxPusher / 企业微信 / 钉钉。
- 当前输出为中文摘要文本，不提供机器 JSON 输出。

---

<a id="protocol"></a>
## 🔁 协议与回读流程

### 请求链

```http
GET  /api/v1/users/wallet/checkin
POST /api/v1/public/captcha/challenge
POST /api/v1/public/captcha/redeem
POST /api/v1/users/wallet/checkin
GET  /api/v1/users/wallet/checkin
```

### Cap 字段

| 字段 | 说明 |
| :--- | :--- |
| `challenge.c` | 需要求解的条目数量。 |
| `challenge.s` | PRNG 输出长度。 |
| `challenge.d` | 目标十六进制位数。 |
| `token` | challenge token。 |
| `expires` | 过期时间，秒或毫秒自动识别。 |
| `solutions` | 本地 nonce 解数组。 |
| `captcha_token` | redeem 后提交签到使用的 token。 |

签到 POST body 为 `{"captcha_token":"<redeemed token>"}`。提交后再次 GET，只有 `checked_in=true` 才报告 `claimed`。

---

<a id="credentials"></a>
## 🔐 凭据与环境变量

### 账号格式

```text
主号|monkeycode_ai_session=xxxxx
备用|yyyyy
```

| 变量 | 必填 | 说明 |
| :--- | :---: | :--- |
| `MONKEYCODE_CN_TOKENS` | 二选一 | 国内版多账号。 |
| `MONKEYCODE_INTL_TOKENS` | 二选一 | 国际版多账号。 |
| `MONKEYCODE_CN_TOKEN` | 否 | 国内版单账号。 |
| `MONKEYCODE_INTL_TOKEN` | 否 | 国际版单账号。 |
| `MONKEYCODE_NOTIFY` | 否 | `always` / `fail` / `0`。 |
| `PUSHPLUS_TOKEN` / `BARK_URL` | 否 | 推送。 |
| `SERVERCHAN_SENDKEY` | 否 | Server酱。 |
| `WXPUSHER_APP_TOKEN` / `WXPUSHER_UID` | 否 | WxPusher。 |
| `WECOM_WEBHOOK` | 否 | 企业微信机器人。 |
| `FEISHU_WEBHOOK` | 否 | 飞书自定义机器人 Webhook。 |
| `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` | 否 | 钉钉机器人。 |

---

## 💻 本地快速开始

### PowerShell

```powershell
python -m pip install -r requirements.txt
$env:MONKEYCODE_CN_TOKEN = "monkeycode_ai_session=xxxxx"
python monkeycode_daily.py
```

### Bash

```bash
python -m pip install -r requirements.txt
export MONKEYCODE_CN_TOKEN='monkeycode_ai_session=xxxxx'
python monkeycode_daily.py
```

常用参数：`--only 2`、`--no-notify`、`--version`。

---

<a id="qinglong"></a>
## 🐧 青龙

1. 在青龙依赖管理中安装 `requests`，或执行 `pip3 install -r requirements.txt`。
2. 上传 `monkeycode_daily.py` 到脚本目录。
3. 在环境变量中配置 `MONKEYCODE_CN_TOKENS` / `MONKEYCODE_INTL_TOKENS`，或对应单账号变量。
4. 新建定时任务，命令使用 `task monkeycode_daily.py`，不要直接写裸 `python`。
5. 建议北京时间：`23 7 * * *`。青龙按面板本地时间执行。

```bash
pip3 install -r requirements.txt
task monkeycode_daily.py
```

---

<a id="actions"></a>
## ☁️ GitHub Actions、Secrets 与定时

工作流：`.github/workflows/monkeycode.yml`；测试工作流：`.github/workflows/test.yml`。

| 事件 | 行为 |
| :--- | :--- |
| `schedule` | 每天执行离线测试和 CN / Intl 签到。 |
| `workflow_dispatch` | 手动执行。 |
| 未配置账号 | 输出 warning 并跳过在线签到。 |

### Secrets

| Secret | 说明 |
| :--- | :--- |
| `MONKEYCODE_CN_TOKENS` / `MONKEYCODE_CN_TOKEN` | 国内版账号。 |
| `MONKEYCODE_INTL_TOKENS` / `MONKEYCODE_INTL_TOKEN` | 国际版账号。 |
| `MONKEYCODE_NOTIFY` | 推送策略。 |
| `PUSHPLUS_TOKEN` / `BARK_URL` / `SERVERCHAN_SENDKEY` | 推送。 |
| `WXPUSHER_APP_TOKEN` / `WXPUSHER_UID` | WxPusher。 |
| `WECOM_WEBHOOK` | 企业微信机器人。 |
| `FEISHU_WEBHOOK` | 飞书自定义机器人 Webhook。 |
| `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` | 钉钉机器人。 |

内置定时为 UTC `23 23 * * *`，对应北京时间约 07:23。工作流不单独上传 artifact，运行结果保留在 Actions 日志。

---

<a id="cli-json"></a>
## ⌨️ CLI 与 JSON 输出

```powershell
python monkeycode_daily.py
python monkeycode_daily.py --only 2
python monkeycode_daily.py --no-notify
python monkeycode_daily.py --version
```

当前版本输出中文摘要文本，不生成 JSON/JSONL。示例：

```text
🐒 MonkeyCode Daily v1.0.0
账号数: 2
✅ CN-1 · MonkeyCode 国内版 · claimed · 服务端已确认签到
   {"checked_in": true, "streak": 1}
✅ INTL-1 · MonkeyCode 国际版 · done · 服务端确认今天已经签到，未重复提交
   {"checked_in": true}
结果: 2/2 成功
```

| 输出内容 | 说明 |
| :--- | :--- |
| 账号行 | 备注、站点、outcome 与说明。 |
| 状态行 | 仅保留 `checked_in`、`streak`、`continuous_days`、`reward`、`points`。 |
| 汇总行 | 成功账号数 / 总账号数。 |
| 退出码 | 全部成功为 0，否则为 1。 |

---

<a id="result-codes"></a>
## 🧾 结果码

| 结果码 | 成功 | 含义 |
| :--- | :---: | :--- |
| `done` | 是 | 执行前服务端已确认今日签到。 |
| `claimed` | 是 | 提交后服务端回读 `checked_in=true`。 |
| `failed` | 否 | 网络、协议、Cap、提交或回读未通过。 |

底层错误类别包括 `NetworkError`、`ProtocolError` 和 `ApiError`。进程退出码为 0 表示全部账号成功，否则为 1。

---

<a id="success"></a>
## ✅ 成功判据

| 场景 | 必须满足 |
| :--- | :--- |
| 今日已签到 | 运行前 `checked_in=true`。 |
| 本次签到 | Cap redeem 成功、签到 POST 完成，且再次 GET `checked_in=true`。 |
| Cap 失败 | challenge 形状、预算、过期或 redeem 任一失败。 |
| 回读失败 | POST 返回后状态仍为 false 时失败。 |

---

## 🧪 测试与静态检查

```bash
python -m unittest discover -s tests -v
python -m compileall -q monkeycode_daily.py tests
python -m ruff check .
```

离线测试覆盖账号解析、`&` 分隔、PRNG 固定向量、多条目求解、站点 Cookie 隔离、过期 challenge、已签到短路、完整 Cap 流程、回读 false、业务错误、Session 脱敏和单账号失败后继续。

---

## 🧱 设计原则

- **站点隔离**：CN 与 Intl 的 Origin 和 Cookie 独立。
- **Cap 本地求解**：不依赖浏览器或外部求解服务。
- **预算明确**：最大哈希数、challenge 时长和 Session 长度都有上限。
- **回读定成功**：POST 与 redeem 都不能单独证明签到完成。
- **日志最小化**：只保留非敏感状态字段。

---

## 🔒 隐私

仓库不包含 Cookie、Session、账号、手机号、设备信息、日志或真实响应。`monkeycode_state.json`、`monkeycode_tokens.json`、`.env`、日志和缓存已由 `.gitignore` 排除。

---

## 📁 目录结构

```text
MonkeyCode-Daily/
├── .github/workflows/monkeycode.yml
├── .github/workflows/test.yml
├── assets/
│   ├── donate-alipay.jpg
│   └── donate-wechat.png
├── docs/
│   ├── README.en.md
│   ├── README.zh-Hant.md
│   ├── README.ja.md
│   ├── README.ko.md
│   └── README.pt-BR.md
├── tests/test_monkeycode_daily.py
├── CHANGELOG.md
├── LICENSE
├── NOTICE.md
├── THIRD_PARTY_NOTICES.md
├── monkeycode_daily.py
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## 📦 版本与发布

- 当前清单版本：`v1.0.0`，日期 `2026-11-24`。
- 脚本版本与 `monkeycode_daily.py` 内的 `VERSION` 保持一致。
- 更新记录见 [CHANGELOG.md](CHANGELOG.md)，下载入口见 [Releases](https://github.com/L0NE-6/MonkeyCode-Daily/releases)。
- Release 徽标由 GitHub 实时生成；如果页面尚未创建对应 Release，以 `CHANGELOG.md` 和仓库提交为准。

---

## ⚠️ 免责声明

本项目用于个人学习与个人自动化。MonkeyCode 的活动规则、接口、奖励、风控策略和账号资格由服务方决定。使用前请确认对应服务条款，并自行承担接口变化、账号限制和网络环境带来的风险。

---

## ☕ 支持与投喂

脚本完全免费，赞赏纯自愿，不影响任何功能，也不影响 Issue 响应。

<p align="center">
  <img src="assets/donate-wechat.png" width="260" alt="微信赞赏码" />
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/donate-alipay.jpg" width="260" alt="支付宝收款码" />
</p>
<p align="center"><sub>💚 微信支付（左） &nbsp;|&nbsp; 💙 支付宝（右，支持信用卡 / 花呗）</sub></p>

> 收款码仅用于向作者自愿赞赏。任何第三方以代下载、代部署、内部资源或会员群为由收费，均与作者无关。

---

## 💬 反馈与贡献

- 提交 [Issue](https://github.com/L0NE-6/MonkeyCode-Daily/issues) 时附运行日志、脱敏后的错误字段和复现步骤。
- 发起 [Pull Request](https://github.com/L0NE-6/MonkeyCode-Daily/pulls) 时保持单文件运行、离线测试和凭据脱敏约束。
- 不要在任何 Issue、PR、截图或日志中粘贴真实 Token、Cookie、密码、UID、手机号或邮箱。

---

<a id="star-trail"></a>
## ✦ Star History / 星轨

<a href="https://star-history.com/#L0NE-6/MonkeyCode-Daily&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=L0NE-6/MonkeyCode-Daily&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=L0NE-6/MonkeyCode-Daily&type=Date" />
    <img alt="MonkeyCode-Daily Star History" src="https://api.star-history.com/svg?repos=L0NE-6/MonkeyCode-Daily&type=Date" />
  </picture>
</a>

<div align="center">
  <sub>L0NE-6 · DAILY SIGNAL &nbsp;|&nbsp; 点个 <b>Star</b>，让下一轮自动化有迹可循</sub>
</div>
