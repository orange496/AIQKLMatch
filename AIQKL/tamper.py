import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "academic.db")

conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT idx, data FROM chain ORDER BY idx").fetchall()

print("=" * 60)
print("链上现有区块：")
for idx, data in rows:
    if idx == 0:
        print(f"  区块0: 创世块（不能篡改）")
    else:
        d = json.loads(data)
        print(f"  区块{idx}: 学号={d.get('student_id')} "
              f"课程={d.get('course')} 分数={d.get('score')}")
print("=" * 60)

try:
    target = int(input("输入要篡改的区块编号: "))
except ValueError:
    print("❌ 请输入数字编号")
    conn.close()
    raise SystemExit(1)

if target == 0:
    print("❌ 创世块不能篡改")
    conn.close()
    raise SystemExit(1)

row = conn.execute(
    "SELECT data FROM chain WHERE idx=?", (target,)).fetchone()
if row is None:
    print(f"❌ 区块{target} 不存在")
    conn.close()
    raise SystemExit(1)

new_score = input("改成多少分: ")

d = json.loads(row[0])
if "score" not in d:
    print(f"❌ 区块{target} 没有 score 字段")
    conn.close()
    raise SystemExit(1)

old = d["score"]
try:
    d["score"] = float(new_score)
except ValueError:
    print("❌ 分数必须是数字")
    conn.close()
    raise SystemExit(1)

conn.execute("UPDATE chain SET data=? WHERE idx=?",
             (json.dumps(d, ensure_ascii=False), target))
conn.commit()
conn.close()
print(f"✅ 区块{target} 的 {old} 分已改成 {new_score} 分")
print("现在去浏览器执行 GET /verify 验证")
