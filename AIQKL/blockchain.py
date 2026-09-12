import hashlib
import json
import time
import sqlite3

DB = "academic.db"

def _hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

class Block:
    def __init__(self, index, timestamp, data, prev_hash, nonce=0):
        self.index = index
        self.timestamp = timestamp
        self.data = data          # 学业数据（成绩、GPA等）
        self.prev_hash = prev_hash
        self.nonce = nonce
        self.hash = self.compute_hash()

    def compute_hash(self):
        payload = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "prev_hash": self.prev_hash,
            "nonce": self.nonce
        }, sort_keys=True)
        return _hash(payload)

    def mine(self, difficulty=3):
        """PoW：简单工作量证明"""
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()


class Blockchain:
    def __init__(self, difficulty=3):
        self.difficulty = difficulty
        self.conn = sqlite3.connect(DB, check_same_thread=False)
        self._init_db()
        if self.get_latest_block() is None:
            self._create_genesis()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chain(
                idx INTEGER PRIMARY KEY,
                timestamp REAL,
                data TEXT,
                prev_hash TEXT,
                nonce INTEGER,
                hash TEXT UNIQUE
            )""")

    def _create_genesis(self):
        genesis = Block(0, time.time(), {"msg": "genesis"}, "0")
        genesis.mine(self.difficulty)
        self._save(genesis)

    def _save(self, block: Block):
        self.conn.execute(
            "INSERT INTO chain VALUES(?,?,?,?,?,?)",
            (block.index, block.timestamp, json.dumps(block.data, ensure_ascii=False),
             block.prev_hash, block.nonce, block.hash))
        self.conn.commit()

    def get_latest_block(self):
        row = self.conn.execute(
            "SELECT * FROM chain ORDER BY idx DESC LIMIT 1").fetchone()
        if not row:
            return None
        return Block(row[0], row[1], json.loads(row[2]), row[3], row[4])

    def add_record(self, data: dict) -> Block:
        """学业数据上链，返回区块"""
        prev = self.get_latest_block()
        block = Block(prev.index + 1, time.time(), data, prev.hash)
        block.mine(self.difficulty)
        self._save(block)
        return block

    def verify(self) -> dict:
        """全链校验：任何篡改都会在此处被发现"""
        rows = self.conn.execute("SELECT * FROM chain ORDER BY idx").fetchall()
        for i, row in enumerate(rows):
            try:
                data = json.loads(row[2])
            except (json.JSONDecodeError, TypeError):
                return {"valid": False, "tampered_index": row[0], "reason": "invalid_json"}
            block = Block(row[0], row[1], data, row[3], row[4])
            if block.hash != row[5]:
                return {"valid": False, "tampered_index": row[0], "reason": "hash_mismatch"}
            if i > 0 and block.prev_hash != rows[i-1][5]:
                return {"valid": False, "tampered_index": row[0], "reason": "chain_broken"}
        return {"valid": True, "length": len(rows)}

    def get_record(self, idx: int):
        row = self.conn.execute(
            "SELECT * FROM chain WHERE idx=?", (idx,)).fetchone()
        if not row:
            return None
        return {"index": row[0], "timestamp": row[1],
                "data": json.loads(row[2]), "hash": row[5]}