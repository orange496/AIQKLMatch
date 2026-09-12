import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "academic.db")

conn = sqlite3.connect(DB_PATH)

# 1. 找出被篡改的区块（用 grades 业务表里的原始成绩作为"正确答案"）
rows = conn.execute("""
    SELECT g.block_index, g.score, c.data
    FROM grades g JOIN chain c ON g.block_index = c.idx
""").fetchall()

fixed = 0
for idx, orig_score, data in rows:
    try:
        d = json.loads(data)
    except json.JSONDecodeError:
        print(f"⚠️ 区块{idx} 的 data 不是合法 JSON，跳过")
        continue
    # 只修正顶层的 score 字段；绝不能动 ai_result 里的 score（那是 AI 异常分数），
    # 否则 data 无法恢复原样，哈希永远对不上。
    if d.get("score") != orig_score:
        d["score"] = orig_score
        conn.execute("UPDATE chain SET data=? WHERE idx=?",
                     (json.dumps(d, ensure_ascii=False), idx))
        print(f"✅ 区块{idx} 已修正为原始分数 {orig_score}")
        fixed += 1

conn.commit()
conn.close()

if fixed == 0:
    print("没有发现需要修正的区块（数据本来就是对的）")
else:
    print(f"共修正 {fixed} 个区块，现在去执行 GET /verify，应恢复 valid: true")
