import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from blockchain import Blockchain
from ai_engine import AcademicAIEngine
from db import get_conn, course_stats, student_stats
from docs_zh import setup_chinese_docs

# ========== 说明文字集中在这里 ==========
DESC = """
## 🎓 学业数据防篡改系统（三步上手）

| 步骤 | 点哪个按钮 | 干什么 |
|---|---|---|
| 第1步 | 📝 录入成绩 | 输入学号、课程、分数 → 系统自动AI检测 + 区块链存证 |
| 第2步 | 📝 再录一条 | 多录几条，方便后面演示对比 |
| 第3步 | 🔍 验证区块链 | 显示链是否被篡改，这是本系统的核心功能 |

**演示防篡改效果**：用 DB Browser 或篡改脚本改掉数据库里的分数，再点 🔍 验证区块链，
会看到 `valid: false` 并精确定位被改的区块号。
"""

app = FastAPI(
    title="学业数据防篡改系统",
    description=DESC,
    version="1.0.0",
    docs_url=None,    # 关闭英文默认文档
    redoc_url=None,   # 关闭英文 Redoc
)

# 挂载汉化后的中文接口文档（访问 /docs）
setup_chinese_docs(app)

chain = Blockchain(difficulty=3)
ai = AcademicAIEngine()
conn = get_conn()


# ========== 根路径：自动跳转到接口文档 ==========
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

# ========== 输入表单：每个字段都有中文说明和示例 ==========
class GradeIn(BaseModel):
    student_id: str = Field(
        description="学号，例如 2023001",
        json_schema_extra={"example": "2023001"})
    course: str = Field(
        description="课程名称",
        json_schema_extra={"example": "高等数学"})
    score: float = Field(
        description="分数 0-100",
        ge=0, le=100,
        json_schema_extra={"example": 95})
    credit: float = Field(
        default=3.0,
        description="学分（不用改）",
        ge=0, le=10)
    hour: int = Field(
        default=12,
        description="录入时的小时 0-23（用于AI检测异常录入时间）",
        ge=0, le=23)


# ========== 第1步：录入成绩 ==========
@app.post("/grade",
          tags=["第1步 📝 录入成绩"],
          summary="录入一条成绩（自动AI检测+上链存证）",
          description="""
**傻瓜操作**：点 Try it out → 所有内容已经帮你填好了，直接点 Execute 就行。

返回结果说明：
- `block_index`：这条成绩在区块链上的编号，后面查成绩要用
- `block_hash`：这条数据的"指纹"，改了任何内容指纹都会变
- `ai.risk`：AI 判定的风险等级（low/medium/high）
""")
def submit_grade(g: GradeIn):
    stats = {"course_avg": course_stats(conn, g.course),
             "student_avg": student_stats(conn, g.student_id)}
    record = g.model_dump()

    result = ai.predict(record, stats)
    if result["risk"] == "high":
        record["ai_flag"] = "HIGH_RISK_ANOMALY"

    record["ai_result"] = result
    record["timestamp"] = time.time()
    block = chain.add_record(record)

    cur = conn.execute(
        "INSERT INTO grades(student_id,course,score,credit,hour,block_index,ai_risk,created_at)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (g.student_id, g.course, g.score, g.credit, g.hour,
         block.index, result["risk"], time.time()))
    conn.commit()

    return {"id": cur.lastrowid, "block_index": block.index,
            "block_hash": block.hash, "ai": result}


# ========== 第2步：验证区块链 ==========
@app.get("/verify",
         tags=["第3步 🔍 验证区块链（核心功能）"],
         summary="检查区块链是否被篡改",
         description="""
**傻瓜操作**：点 Try it out → 点 Execute。

看返回值：
- `valid: true` → ✅ 链完好，没有任何数据被改过
- `valid: false` → ❌ 发现篡改！`tampered_index` 告诉你被改的是第几个区块

想演示篡改：先用 DB Browser for SQLite 打开 academic.db，
把 chain 表里某行的分数改一下，再来点这个按钮。
""")
def verify_chain():
    return chain.verify()


# ========== 查询成绩 ==========
@app.get("/grade/{block_index}",
         tags=["第2步 🔎 查询成绩"],
         summary="按区块编号查询链上成绩",
         description="""
**傻瓜操作**：点 Try it out → block_index 填录入成绩时返回的编号（第1条成绩是1）→ Execute。

从链上读出来的数据就是权威数据——区块链保证了它没被改过。
""")
def get_grade(block_index: int):
    rec = chain.get_record(block_index)
    if not rec:
        raise HTTPException(404, "区块不存在")
    return rec


# ========== 训练AI（放在最后，可选） ==========
@app.post("/train",
          tags=["第4步 ⚙️ 训练AI（可选）"],
          summary="用一批历史数据训练AI检测模型",
          description="""
**一般不用管这个**。AI 模型没训练过时也能用（返回 untrained），
想让它更聪明就录 20 条以上正常成绩后来这里训练一次。

body 格式：一组成绩数组，例如：
[{"student_id":"2023001","course":"高等数学","score":90,"credit":4,"hour":10},
{"student_id":"2023002","course":"高等数学","score":85,"credit":4,"hour":10}]
""")
def train_ai(samples: list[GradeIn]):
    records = [s.model_dump() for s in samples]
    stats_list = [{"course_avg": course_stats(conn, r["course"]),
                   "student_avg": student_stats(conn, r["student_id"])}
                  for r in records]
    ai.train(records, stats_list)
    return {"status": "trained", "n": len(records)}
# ========== 查询已录入的成绩列表 ==========
@app.get("/grades",
         tags=["第2步 🔎 查询成绩"],
         summary="显示最近录入的 N 条成绩",
         description="""
**傻瓜操作**：点 Try it out → limit 已默认填 10 → Execute。

返回最近录入的成绩列表，每条包含：
- `block_index`：链上区块编号
- `student_id / course / score`：学号、课程、分数
- `hash`：该区块哈希
- `ai_risk`：AI 判定的风险等级
- `valid`：该区块及其之前的链是否完好
""")
def list_grades(limit: int = 10):
    rows = conn.execute(
        "SELECT block_index, student_id, course, score, ai_risk, created_at"
        " FROM grades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    chain_valid = chain.verify()["valid"]
    result = []
    for r in rows:
        block = chain.get_record(r[0])
        result.append({
            "block_index": r[0],
            "student_id": r[1],
            "course": r[2],
            "score": r[3],
            "ai_risk": r[4],
            "created_at": r[5],
            "hash": block["hash"] if block else None,
            "chain_valid": chain_valid,
        })
    return result


# ========== 后门：一键清空所有数据（重置演示环境） ==========
RESET_KEY = "admin123"   # 后门密码，自己改

@app.delete("/reset",
            tags=["第5步 🧹 重置系统（演示后门）"],
            summary="清空链上所有数据和成绩（用于答辩演示重置）",
            description="""
**警告：此操作会删除所有区块和成绩，不可恢复！** 仅用于答辩演示前重置环境。

**操作**：点 Try it out → key 填入密码（默认 admin123）→ Execute。

清空后系统回到初始状态（只有创世块），可以重新演示完整流程。
""")
def reset_all(key: str):
    if key != RESET_KEY:
        raise HTTPException(403, "密码错误")
    conn.execute("DELETE FROM grades")
    conn.execute("DELETE FROM chain")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='grades'")
    conn.commit()
    chain._create_genesis()          # 重新生成创世块
    return {"status": "已清空", "chain_length": 1,
            "提示": "所有成绩和区块已删除，系统已重置"}