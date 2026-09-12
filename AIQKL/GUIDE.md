# 🎓 学业数据防篡改系统 · 完整操作指南

> 每个功能模块都配有**操作步骤**、**预期结果**和**验证通过的判据**。
> 建议按顺序从上到下执行，后一步依赖前一步的数据。

---

## 0. 环境准备

### 0.1 依赖（已确认本机已安装）

| 包 | 版本 | 用途 |
|---|---|---|
| fastapi | 0.141.1 | Web 框架 |
| uvicorn | 0.52.4 | ASGI 服务器 |
| pydantic | 2.13.5 | 请求体校验 |
| numpy | 2.4.6 | 数值计算 |
| joblib | 1.5.3 | 模型持久化 |
| scikit-learn | 1.8.0 | IsolationForest 异常检测 |

如缺失，安装命令：
```bash
pip install fastapi uvicorn pydantic numpy joblib scikit-learn
```

### 0.2 启动服务

在项目目录 `d:\AIQKL` 下执行：

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

看到以下输出说明启动成功：
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 0.3 打开接口文档（Swagger UI）

浏览器访问：

```
http://127.0.0.1:8000/docs
```

页面左侧按标签分组显示 5 个接口，**每个接口都能点 "Try it out" 直接测试**。
本文档同时给出「Swagger 点按钮」和「curl 命令行」两种方式，任选其一。

> 📌 说明：接口文档的界面已做**中文化**（按钮为「试一试 / 执行 / 取消」等，表头为「请求参数 / 请求体 / 响应」等），
> 并且 swagger-ui 的样式与脚本已放在项目 `static/` 目录，**答辩现场断网也能正常打开文档**。
> 接口路径、参数名（如 `student_id`）、HTTP 方法名（GET/POST）属于技术标识符，保持英文不变。

---

## 1. 模块一：录入成绩（POST /grade）

**作用**：录入一条成绩 → 系统自动做 AI 异常检测 → 写入区块链存证 → 同步写业务表。

### 操作步骤（Swagger）

1. 展开 `第1步 📝 录入成绩` → `POST /grade` → 点 **Try it out**。
2. 请求体已填好默认值（学号 2023001、高等数学、95 分、4 学分、10 时），直接点 **Execute**。
3. 换几组数据多录几次（例如改学号、改课程、改分数）。

### 操作步骤（curl）

```bash
curl -X POST "http://127.0.0.1:8000/grade" \
  -H "Content-Type: application/json" \
  -d '{"student_id":"2023001","course":"高等数学","score":95,"credit":4,"hour":10}'

curl -X POST "http://127.0.0.1:8000/grade" \
  -H "Content-Type: application/json" \
  -d '{"student_id":"2023002","course":"高等数学","score":88,"credit":4,"hour":10}'

curl -X POST "http://127.0.0.1:8000/grade" \
  -H "Content-Type: application/json" \
  -d '{"student_id":"2023001","course":"大学英语","score":72,"credit":3,"hour":15}'
```

### 预期返回

```json
{
  "id": 1,
  "block_index": 1,
  "block_hash": "000a1b2c...（以 000 开头的64位十六进制）",
  "ai": {
    "anomaly": false,
    "score": 0.1234,
    "risk": "low"
  }
}
```

### 验证通过的判据

- ✅ 返回 `block_index` 从 1 开始递增（第1条=1，第2条=2…）。
- ✅ `block_hash` 以 `000` 开头（难度=3 的工作量证明结果）。
- ✅ `ai.risk` 为 `low` / `medium` / `high` 之一（模型已训练时）。
- ✅ 每次录入后 `block_hash` 都不相同。

---

## 2. 模块二：查询成绩列表（GET /grades）

**作用**：列出最近录入的 N 条成绩，含链上哈希与链完整性。

### 操作步骤（Swagger）

1. 展开 `第2步 🔎 查询成绩` → `GET /grades` → **Try it out**。
2. `limit` 默认 10，点 **Execute**。

### 操作步骤（curl）

```bash
curl "http://127.0.0.1:8000/grades?limit=10"
```

### 预期返回

```json
[
  {
    "block_index": 3,
    "student_id": "2023001",
    "course": "大学英语",
    "score": 72.0,
    "ai_risk": "low",
    "created_at": 1789130980.0,
    "hash": "000...",
    "chain_valid": true
  },
  { "...": "..." }
]
```

### 验证通过的判据

- ✅ 列表按录入时间倒序（最新的在最前）。
- ✅ 每条的 `chain_valid` 都是 `true`（此时还没篡改）。
- ✅ 条数与 `limit` 相符（数据够的话）。

---

## 3. 模块三：查询单条成绩（GET /grade/{block_index}）

**作用**：按区块编号从**链上**读数据（区块链保证未被篡改的权威数据）。

### 操作步骤（Swagger）

1. 展开 `GET /grade/{block_index}` → **Try it out**。
2. `block_index` 填 `1` → **Execute**。

### 操作步骤（curl）

```bash
curl "http://127.0.0.1:8000/grade/1"
```

### 预期返回

```json
{
  "index": 1,
  "timestamp": 1789130980.04,
  "data": {
    "student_id": "2023001",
    "course": "高等数学",
    "score": 95.0,
    "credit": 4.0,
    "hour": 10,
    "ai_result": { "anomaly": false, "score": 0.1234, "risk": "low" },
    "timestamp": 1789130980.04
  },
  "hash": "000..."
}
```

### 验证通过的判据

- ✅ 返回的 `data` 与你录入的内容一致。
- ✅ `hash` 与录入时返回的 `block_hash` 相同。
- ❌ 若填不存在的编号（如 `999`），应返回 `404`「区块不存在」。

---

## 4. 模块四：验证区块链（GET /verify）⭐ 核心功能

**作用**：全链逐块重新计算哈希并核对，任何篡改都会在此暴露。

### 操作步骤（Swagger）

1. 展开 `第3步 🔍 验证区块链` → `GET /verify` → **Try it out** → **Execute**。

### 操作步骤（curl）

```bash
curl "http://127.0.0.1:8000/verify"
```

### 预期返回（未篡改时）

```json
{ "valid": true, "length": 4 }
```

> `length` = 已上链的区块总数（含创世块）。

### 验证通过的判据

- ✅ `valid` 为 `true`。

---

## 5. 模块五：篡改演示（tamper.py）⭐ 演示核心

**作用**：直接改数据库里链上某区块的分数（**不改哈希**），模拟数据被篡改。

### 操作步骤

另开一个终端，在 `d:\AIQKL` 下执行：

```bash
python tamper.py
```

按提示操作：
```
输入要篡改的区块编号: 1
改成多少分: 99
```

### 预期输出

```
链上现有区块：
  区块0: 创世块（不能篡改）
  区块1: 学号=2023001 课程=高等数学 分数=95.0
  区块2: 学号=2023002 课程=高等数学 分数=88.0
  区块3: 学号=2023001 课程=大学英语 分数=72.0
============================================================
✅ 区块1 的 95.0 分已改成 99.0 分
现在去浏览器执行 GET /verify 验证
```

### 边界验证（已修复的错误）

| 输入 | 预期结果 |
|---|---|
| 区块编号填 `0` | ❌ 提示「创世块不能篡改」，正常退出 |
| 区块编号填 `999`（不存在） | ❌ 提示「区块 999 不存在」，正常退出 |
| 区块编号填 `abc` | ❌ 提示「请输入数字编号」，正常退出 |
| 分数填 `abc` | ❌ 提示「分数必须是数字」，正常退出 |

### 篡改后验证链

回到 Swagger，再次执行 `GET /verify`，预期返回：

```json
{
  "valid": false,
  "tampered_index": 1,
  "reason": "hash_mismatch"
}
```

### 验证通过的判据

- ✅ `valid` 变为 `false`。
- ✅ `tampered_index` 精确指向你改的那个区块号（1）。

---

## 6. 模块六：修复演示（repair.py）

**作用**：以业务表 `grades` 中的原始分数为准，把链上被篡改的分数改回来。

### 操作步骤

在 `d:\AIQKL` 下执行：

```bash
python repair.py
```

### 预期输出

```
✅ 区块1 已修正为原始分数 95.0
共修正 1 个区块，现在去执行 GET /verify，应恢复 valid: true
```

### 修复后验证链

再次执行 `GET /verify`，预期恢复：

```json
{ "valid": true, "length": 4 }
```

### 验证通过的判据

- ✅ `valid` 恢复为 `true`。
- ✅ `tampered_index` 不再出现。

> **原理说明**：篡改只改了 `data`（分数），哈希字段始终是原始正确值。修复把 `data` 恢复原样后，重新计算的哈希又能与存储的哈希匹配。

---

## 7. 模块七：训练 AI（POST /train，可选）

**作用**：用一批成绩重新训练 IsolationForest，让它能识别异常分数/异常录入时间。

### 操作步骤（Swagger）

1. 展开 `第4步 ⚙️ 训练AI` → `POST /train` → **Try it out**。
2. 请求体填至少 **5 条**成绩数组（示例）：

```json
[
  {"student_id":"2023001","course":"高等数学","score":90,"credit":4,"hour":10},
  {"student_id":"2023002","course":"高等数学","score":85,"credit":4,"hour":10},
  {"student_id":"2023003","course":"高等数学","score":92,"credit":4,"hour":9},
  {"student_id":"2023004","course":"高等数学","score":88,"credit":4,"hour":11},
  {"student_id":"2023005","course":"高等数学","score":86,"credit":4,"hour":10},
  {"student_id":"2023006","course":"高等数学","score":45,"credit":4,"hour":10}
]
```

### 操作步骤（curl）

```bash
curl -X POST "http://127.0.0.1:8000/train" \
  -H "Content-Type: application/json" \
  -d '[{"student_id":"2023001","course":"高等数学","score":90,"credit":4,"hour":10},{"student_id":"2023002","course":"高等数学","score":85,"credit":4,"hour":10},{"student_id":"2023003","course":"高等数学","score":92,"credit":4,"hour":9},{"student_id":"2023004","course":"高等数学","score":88,"credit":4,"hour":11},{"student_id":"2023005","course":"高等数学","score":86,"credit":4,"hour":10},{"student_id":"2023006","course":"高等数学","score":45,"credit":4,"hour":10}]'
```

### 预期返回

```json
{ "status": "trained", "n": 6 }
```

### 边界验证（已修复的错误）

| 情况 | 预期结果 |
|---|---|
| 请求体为 `[]`（空数组） | ❌ 返回错误「训练数据为空，请先录入成绩」 |
| 请求体只有 1~4 条 | ❌ 返回错误「训练数据过少…至少需要 5 条」 |

### 训练后验证

再录入一条**明显异常**的成绩（分数偏离很大或深夜录入），观察 `ai.risk` 变化：

```bash
curl -X POST "http://127.0.0.1:8000/grade" \
  -H "Content-Type: application/json" \
  -d '{"student_id":"2023007","course":"高等数学","score":12,"credit":4,"hour":2}'
```

预期 `ai.risk` 为 `high`（或 `medium`），且链上该条会带 `ai_flag: HIGH_RISK_ANOMALY` 标记。

---

## 8. 模块八：重置系统（DELETE /reset）

**作用**：一键清空所有成绩和区块，回到初始状态（仅剩创世块），用于答辩前重置。

### 操作步骤（Swagger）

1. 展开 `第5步 🧹 重置系统` → `DELETE /reset` → **Try it out**。
2. `key` 填 `admin123` → **Execute**。

### 操作步骤（curl）

```bash
curl -X DELETE "http://127.0.0.1:8000/reset?key=admin123"
```

### 预期返回

```json
{ "status": "已清空", "chain_length": 1, "提示": "所有成绩和区块已删除，系统已重置" }
```

### 边界验证

| 情况 | 预期结果 |
|---|---|
| `key` 填错（如 `123`） | ❌ 返回 `403`「密码错误」 |

### 重置后验证

再次执行 `GET /verify` 和 `GET /grades`：

```bash
curl "http://127.0.0.1:8000/verify"    # → {"valid":true,"length":1}
curl "http://127.0.0.1:8000/grades"    # → []
```

### 验证通过的判据

- ✅ `verify` 返回 `valid: true, length: 1`（只剩创世块）。
- ✅ `grades` 返回空数组。
- ✅ 再录入成绩时，`id` 和 `block_index` 都从 1 重新开始（自增已重置）。

---

## 9. 完整演示脚本（答辩/验收一条龙）

按下面顺序执行，即可完整演示"录入 → 存证 → 篡改 → 发现 → 修复"全流程：

```bash
# 1. 启动服务
uvicorn main:app --reload

# 2. 录入 3 条成绩（另一个终端）
curl -X POST "http://127.0.0.1:8000/grade" -H "Content-Type: application/json" \
  -d '{"student_id":"2023001","course":"高等数学","score":95,"credit":4,"hour":10}'
curl -X POST "http://127.0.0.1:8000/grade" -H "Content-Type: application/json" \
  -d '{"student_id":"2023002","course":"高等数学","score":88,"credit":4,"hour":10}'
curl -X POST "http://127.0.0.1:8000/grade" -H "Content-Type: application/json" \
  -d '{"student_id":"2023001","course":"大学英语","score":72,"credit":3,"hour":15}'

# 3. 验证链（应 valid:true）
curl "http://127.0.0.1:8000/verify"

# 4. 篡改区块 1 的分数
python tamper.py     # 输入 1，再输入 99

# 5. 再验证（应 valid:false, tampered_index:1）
curl "http://127.0.0.1:8000/verify"

# 6. 修复
python repair.py

# 7. 再验证（应恢复 valid:true）
curl "http://127.0.0.1:8000/verify"

# 8. 演示结束，重置环境
curl -X DELETE "http://127.0.0.1:8000/reset?key=admin123"
```

---

## 附：接口速查表

| 方法 | 路径 | 功能 | 关键返回字段 |
|---|---|---|---|
| POST | `/grade` | 录入成绩（AI+上链） | `block_index`, `block_hash`, `ai.risk` |
| GET | `/grades` | 成绩列表 | `hash`, `chain_valid` |
| GET | `/grade/{block_index}` | 查单条链上成绩 | `data`, `hash` |
| GET | `/verify` | 验证链完整性 | `valid`, `tampered_index`, `reason` |
| POST | `/train` | 训练 AI | `status`, `n` |
| DELETE | `/reset` | 重置系统 | `status`, `chain_length` |
