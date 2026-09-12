import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import os

MODEL_PATH = "if_model.pkl"
SCALER_PATH = "scaler.pkl"

class AcademicAIEngine:
    """
    学业数据异常检测引擎：
    - IsolationForest 检测异常成绩记录（异常值、疑似篡改的录入行为）
    - 结合历史数据统计特征做特征工程
    """
    FEATURES = ["score", "credit", "course_avg", "student_avg",
                "dev_from_course", "dev_from_student", "hour"]

    def __init__(self):
        self.model = IsolationForest(
            n_estimators=200, contamination=0.05, random_state=42)
        self.scaler = StandardScaler()
        self._trained = False
        self._load()

    def _load(self):
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self._trained = True

    def extract_features(self, record: dict, stats: dict) -> list:
        """从单条成绩记录提取特征向量"""
        return [[
            record["score"],
            record["credit"],
            stats.get("course_avg", record["score"]),
            stats.get("student_avg", record["score"]),
            record["score"] - stats.get("course_avg", record["score"]),
            record["score"] - stats.get("student_avg", record["score"]),
            record.get("hour", 12),   # 录入时间（异常录入时间常是深夜）
        ]]

    def train(self, records: list, stats_list: list):
        """用历史正常数据训练"""
        if not records:
            raise ValueError("训练数据为空，请先录入成绩")
        if len(records) < 5:
            raise ValueError(f"训练数据过少（当前 {len(records)} 条），至少需要 5 条")
        X = np.vstack([self.extract_features(r, s)
                       for r, s in zip(records, stats_list)])
        X = self.scaler.fit_transform(X)
        self.model.fit(X)
        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.scaler, SCALER_PATH)
        self._trained = True

    def predict(self, record: dict, stats: dict) -> dict:
        """
        返回: {"anomaly": bool, "score": float(-1~1), "risk": str}
        score 越接近 -1 越异常
        """
        if not self._trained:
            return {"anomaly": False, "score": 0.0, "risk": "untrained"}
        X = self.scaler.transform(self.extract_features(record, stats))
        raw = self.model.decision_function(X)[0]   # [-0.5, 0.5] 越大越正常
        label = self.model.predict(X)[0]           # -1 异常 / 1 正常
        # label == -1 得到的是 numpy.bool_，json.dumps 无法序列化，必须转成 Python bool
        anomaly = bool(label == -1)
        risk = "high" if raw < -0.15 else ("medium" if anomaly else "low")
        return {"anomaly": anomaly, "score": round(float(raw), 4), "risk": risk}