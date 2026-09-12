import sqlite3

def get_conn():
    conn = sqlite3.connect("academic.db", check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            course TEXT,
            score REAL,
            credit REAL,
            hour INTEGER,
            block_index INTEGER,          -- 对应链上区块
            ai_risk TEXT,
            created_at REAL
        )""")
    return conn

def course_stats(conn, course):
    row = conn.execute(
        "SELECT AVG(score) FROM grades WHERE course=?", (course,)).fetchone()
    return row[0] or 0

def student_stats(conn, sid):
    row = conn.execute(
        "SELECT AVG(score) FROM grades WHERE student_id=?", (sid,)).fetchone()
    return row[0] or 0