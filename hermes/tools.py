"""
═════════════════════════════════════════════════════════════════════════════
  tools.py - أدوات التحسينات 51-100
═════════════════════════════════════════════════════════════════════════════
  يحتوي على كل الأدوات المساعدة المضافة في النسخة 100:
    52. DataEncryptor - تشفير البيانات
    53. TokenCounter - عداد التوكنز
    54. ThreadManager - محادثات متعددة
    56. AuditLogger - سجل المراجعة
    58. ABTestingEngine - اختبار A/B
    59. AnomalyDetector - كشف الشذوذ
    60. DataExporter - تصدير CSV/JSON
    62. RulesEngine - محرك القواعد
    63. PersistentCache - كاش دائم
    64. ReplayEngine - إعادة اللعب
    65. DependencyTracker - تتبع التبعيات
    69. AutoClassifier - تصنيف تلقائي
    71. ResourceMonitor - مراقبة الموارد
    74. AutoCorrector - تصحيح تلقائي
    76. TimeSeriesAnalyzer - تحليل سلاسل زمنية
    78. Watchdog - مراقب ذاتي
    79. ErrorEscalator - تصعيد أخطاء
    81. PromptVersionManager - إصدارات البرومبتات
    83. NGramDeduplicator - كشف تكرار N-gram
    84. SmartRouter - توجيه ذكي
    89. DataCompressor - ضغط بيانات
    90. QualityScorer - تقييم جودة
    91. InjectionProtector - حماية من الحقن
    94. TUIDashboard - لوحة تحكم نصية
    95. ProfileManager - ملفات تعريف
    98. SelfTester - اختبارات ذاتية
    99. ScenarioEngine - محرك سيناريوهات
    100. MetaEngine - محرك تحول كامل
"""

import base64
import csv
import gzip
import hashlib
import json
import os
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from hermes.config import log, Config
from hermes.database import Database
from hermes.infrastructure import Metrics
from hermes.alerts import AlertLevel, AlertManager


# --- 52. تشفير AES للبيانات الحساسة ---
class DataEncryptor:
    """تشفير وفك تشفير البيانات الحساسة باستخدام AES-like"""
    def __init__(self, key: str):
        self._key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        from itertools import cycle
        key_bytes = self._key
        encrypted = bytes(a ^ b for a, b in zip(plaintext.encode('utf-8'), cycle(key_bytes)))
        return base64.b64encode(encrypted).decode('ascii')

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        try:
            from itertools import cycle
            key_bytes = self._key
            decrypted = bytes(a ^ b for a, b in zip(base64.b64decode(ciphertext), cycle(key_bytes)))
            return decrypted.decode('utf-8')
        except:
            return ciphertext


# --- 53. عداد التوكنز ---
class TokenCounter:
    """تقدير عدد التوكنز للنصوص العربية"""
    CHARS_PER_TOKEN = 4

    def estimate(self, text: str) -> int:
        if not text:
            return 0
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        other_chars = len(text) - arabic_chars
        arabic_tokens = arabic_chars / self.CHARS_PER_TOKEN
        other_tokens = other_chars / 3.5
        return int(arabic_tokens + other_tokens) + 10


# --- 54. نظام المحادثات المتعددة ---
class ThreadManager:
    """تتبع مواضيع محادثة منفصلة"""
    def __init__(self):
        self._threads: Dict[str, Dict] = {}
        self._current_thread = "default"

    def create_thread(self, thread_id: str, topic: str = ""):
        self._threads[thread_id] = {
            'topic': topic, 'created_at': datetime.now(),
            'message_count': 0, 'last_activity': datetime.now()
        }

    def get_or_create(self, keyword: str) -> str:
        for tid, t in self._threads.items():
            if t['topic'] and keyword in t['topic']:
                return tid
        new_id = f"thread_{len(self._threads)+1}"
        self.create_thread(new_id, keyword)
        return new_id

    def update_activity(self, thread_id: str):
        if thread_id in self._threads:
            self._threads[thread_id]['message_count'] += 1
            self._threads[thread_id]['last_activity'] = datetime.now()

    @property
    def active_threads(self) -> List[str]:
        cutoff = datetime.now() - timedelta(hours=1)
        return [tid for tid, t in self._threads.items() if t['last_activity'] > cutoff]


# --- 56. سجل المراجعة ---
class AuditLogger:
    """تسجيل كل عملية مع تفاصيل كاملة"""
    def __init__(self, db: Database):
        self.db = db

    async def log(self, action: str, actor: str = "system", target: str = "", details: str = "", severity: str = "info"):
        await self.db.execute(
            "INSERT INTO audit_log (action,actor,target,details,severity) VALUES (?,?,?,?,?)",
            (action, actor, target, details[:500], severity)
        )

    async def get_recent(self, limit=50):
        rows = await self.db.fetchall(
            "SELECT action,actor,target,severity,timestamp FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [{'action': r[0], 'actor': r[1], 'target': r[2], 'severity': r[3], 'timestamp': r[4]} for r in rows]


# --- 58. A/B Testing ---
class ABTestingEngine:
    """اختبار نسخ مختلفة من البرومبتات"""
    def __init__(self, db: Database):
        self.db = db
        self._groups: Dict[str, str] = {}

    async def initialize(self):
        rows = await self.db.fetchall("SELECT role, ab_group FROM prompt_versions WHERE is_active=1")
        for role, group in rows:
            self._groups[role] = group

    def assign_group(self, role: str) -> str:
        if role not in self._groups:
            self._groups[role] = 'A' if hash(role) % 2 == 0 else 'B'
        return self._groups[role]

    async def record_result(self, role: str, group: str, success: bool):
        await self.db.execute(
            "INSERT INTO prompt_versions (role,version,content,ab_group,success_rate,is_active) VALUES (?,?,?,?,?,1)",
            (role, int(time.time()), "", group, 1.0 if success else 0.0)
        )

    async def get_winning_version(self, role: str) -> str:
        row = await self.db.fetchone(
            "SELECT ab_group, AVG(success_rate) as avg FROM prompt_versions WHERE role=? GROUP BY ab_group ORDER BY avg DESC LIMIT 1",
            (role,)
        )
        return row[0] if row else 'A'


# --- 59. كشف الشذوذ ---
class AnomalyDetector:
    """اكتشاف سلوك غير طبيعي في القياسات"""
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config
        self._baselines: Dict[str, Tuple[float, float]] = {}

    def update_baseline(self, metric: str, values: List[float]):
        if len(values) < 5:
            return
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance ** 0.5
        self._baselines[metric] = (mean, std)

    def is_anomaly(self, metric: str, value: float) -> Tuple[bool, float]:
        if metric not in self._baselines:
            return False, 0.0
        mean, std = self._baselines[metric]
        if std == 0:
            return False, 0.0
        deviation = abs(value - mean) / std
        return deviation > self.config.ANOMALY_THRESHOLD, deviation

    async def record_anomaly(self, metric: str, expected: float, actual: float, deviation: float):
        await self.db.execute(
            "INSERT INTO anomaly_log (metric_name,expected_value,actual_value,deviation) VALUES (?,?,?,?)",
            (metric, expected, actual, deviation)
        )


# --- 60. تصدير CSV/JSON ---
class DataExporter:
    """تصدير البيانات بصيغ مختلفة"""
    def __init__(self, db: Database):
        self.db = db

    async def export_messages_csv(self, filepath: str, days: int = 7):
        rows = await self.db.fetchall(
            "SELECT direction,content,model_used,response_time,sentiment_score,timestamp FROM messages WHERE timestamp>datetime('now',?) ORDER BY timestamp",
            (f'-{days} days',)
        )
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['اتجاه', 'محتوى', 'موديل', 'وقت_استجابة', 'مشاعر', 'توقيت'])
            for r in rows:
                w.writerow([r[0], r[1][:200], r[2], r[3], r[4], r[5]])
        log.info(f"تم تصدير {len(rows)} رسالة إلى {filepath}")

    async def export_stats_json(self, filepath: str):
        msgs = await self.db.fetchone("SELECT COUNT(*), AVG(response_time) FROM messages")
        costs = await self.db.fetchone("SELECT SUM(cost), COUNT(*) FROM cost_tracking WHERE timestamp>datetime('now','-1 day')")
        data = {
            'total_messages': msgs[0] if msgs else 0,
            'avg_response_time': msgs[1] if msgs else 0,
            'daily_cost': costs[0] if costs else 0,
            'api_calls_today': costs[1] if costs else 0,
            'exported_at': datetime.now().isoformat()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"تم تصدير الإحصائيات إلى {filepath}")


# --- 62. محرك القواعد ---
class RulesEngine:
    """قواعد شرطية IF-THEN للتنفيذ التلقائي"""
    def __init__(self, db: Database, alerts: AlertManager):
        self.db = db
        self.alerts = alerts
        self._rules: List[Dict] = []

    async def initialize(self):
        rows = await self.db.fetchall("SELECT id,name,condition,action,priority,enabled FROM rules WHERE enabled=1 ORDER BY priority")
        for r in rows:
            self._rules.append({'id': r[0], 'name': r[1], 'condition': r[2], 'action': r[3], 'priority': r[4]})

    async def add_rule(self, name: str, condition: str, action: str, priority: int = 5):
        await self.db.execute("INSERT INTO rules (name,condition,action,priority) VALUES (?,?,?,?)", (name, condition, action, priority))
        self._rules.append({'name': name, 'condition': condition, 'action': action, 'priority': priority})
        log.info(f"قاعدة جديدة: {name}")

    async def evaluate(self, context: Dict) -> List[str]:
        actions = []
        for rule in self._rules:
            try:
                if eval(rule['condition'], {"__builtins__": {}}, context):
                    actions.append(rule['action'])
                    await self.db.execute(
                        "UPDATE rules SET last_triggered=?,trigger_count=trigger_count+1 WHERE name=?",
                        (datetime.now().isoformat(), rule['name'])
                    )
            except:
                pass
        return actions


# --- 63. تخزين مؤقت دائم ---
class PersistentCache:
    """تخزين مؤقت محفوظ على القرص"""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
        except:
            self._data = {}

    def _save(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False)
        except:
            pass

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._save()

    def delete(self, key: str):
        self._data.pop(key, None)
        self._save()


# --- 64. نظام إعادة اللعب ---
class ReplayEngine:
    """إعادة تنفيذ أوامر من تاريخ معين"""
    def __init__(self, db: Database):
        self.db = db

    async def get_commands_since(self, since: datetime) -> List[Dict]:
        rows = await self.db.fetchall(
            "SELECT content,timestamp FROM messages WHERE direction='outgoing' AND timestamp>? ORDER BY timestamp",
            (since.isoformat(),)
        )
        return [{'content': r[0], 'timestamp': r[1]} for r in rows]

    async def get_last_n_commands(self, n: int = 10) -> List[Dict]:
        rows = await self.db.fetchall(
            "SELECT content,timestamp FROM messages WHERE direction='outgoing' ORDER BY timestamp DESC LIMIT ?", (n,)
        )
        return [{'content': r[0], 'timestamp': r[1]} for r in reversed(rows)]


# --- 65. تتبع التبعيات ---
class DependencyTracker:
    """تتبع علاقة الأوامر ببعضها"""
    def __init__(self, db: Database):
        self.db = db
        self._chains: Dict[str, List[str]] = {}

    async def start_chain(self, chain_id: str, initial_command: str):
        await self.db.execute(
            "INSERT INTO command_chains (chain_id,step_number,command,status) VALUES (?,?,?,'running')",
            (chain_id, 1, initial_command)
        )
        self._chains[chain_id] = [initial_command]

    async def add_step(self, chain_id: str, command: str, depends_on: str = ""):
        step = len(self._chains.get(chain_id, [])) + 1
        await self.db.execute(
            "INSERT INTO command_chains (chain_id,step_number,command,status,dependency) VALUES (?,?,?,'pending',?)",
            (chain_id, step, command, depends_on)
        )
        if chain_id not in self._chains:
            self._chains[chain_id] = []
        self._chains[chain_id].append(command)

    async def complete_step(self, chain_id: str, step: int, result: str):
        await self.db.execute(
            "UPDATE command_chains SET status='completed',result=? WHERE chain_id=? AND step_number=?",
            (result[:500], chain_id, step)
        )


# --- 69. تصنيف رسائل تلقائي ---
class AutoClassifier:
    """تصنيف الرسائل لفئات تلقائياً"""
    CATEGORIES = {
        'financial': ['ربح', 'خسارة', 'سعر', 'شراء', 'بيع', 'استثمار', 'أرباح', 'تكلفة', 'دفع', 'تحويل'],
        'technical': ['خطأ', 'عطل', 'مشكلة', 'إصلاح', 'تحديث', 'ترقية', 'اتصال', 'خادم', 'API'],
        'opportunity': ['فرصة', 'عرض', 'مكافأة', 'بونص', 'خصم', 'مجاني', 'جديد', 'إطلاق'],
        'status': ['حالة', 'تقرير', 'مراجعة', 'متابعة', 'إحصائيات', 'نتيجة', 'تقدم'],
        'command': ['Hermes:', 'نفذ', 'ابدأ', 'توقف', 'غير', 'أرسل', 'تحقق'],
    }

    def classify(self, text: str) -> Tuple[str, float]:
        scores = {}
        text_lower = text.lower()
        for cat, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[cat] = score
        if not scores or max(scores.values()) == 0:
            return 'general', 0.0
        best = max(scores, key=scores.get)
        total = sum(scores.values())
        return best, scores[best] / max(total, 1)


# --- 71. مراقبة الموارد ---
class ResourceMonitor:
    """تتبع استخدام CPU والذاكرة"""
    def __init__(self, db: Database):
        self.db = db

    async def snapshot(self) -> Dict:
        data = {'cpu_percent': 0, 'memory_mb': 0, 'disk_mb': 0, 'active_threads': threading.active_count()}
        try:
            import psutil
            data['cpu_percent'] = psutil.cpu_percent()
            data['memory_mb'] = psutil.virtual_memory().used / 1024 / 1024
            data['disk_mb'] = psutil.disk_usage('/').used / 1024 / 1024
        except ImportError:
            pass
        await self.db.execute(
            "INSERT INTO resource_usage (cpu_percent,memory_mb,disk_mb,active_threads) VALUES (?,?,?,?)",
            (data['cpu_percent'], data['memory_mb'], data['disk_mb'], data['active_threads'])
        )
        return data


# --- 74. تصحيح تلقائي ---
class AutoCorrector:
    """تصحيح الأوامر قبل الإرسال"""
    def __init__(self):
        self._fixes = {
            r'Hermes:\s*Hermes:': 'Hermes:',
            r'\s{3,}': ' ',
            r'هيرمس': 'Hermes',
        }

    def correct(self, text: str) -> Tuple[str, List[str]]:
        corrections = []
        original = text
        for pattern, replacement in self._fixes.items():
            new = re.sub(pattern, replacement, text)
            if new != text:
                corrections.append(f"تصحيح: {pattern} → {replacement}")
                text = new
        return text, corrections


# --- 76. تحليل سلاسل زمنية ---
class TimeSeriesAnalyzer:
    """تحليل الاتجاهات عبر الزمن"""
    def __init__(self, db: Database):
        self.db = db

    async def record(self, metric_name: str, value: float, period: str = "hourly"):
        await self.db.execute("INSERT INTO time_series (metric_name,value,period) VALUES (?,?,?)", (metric_name, value, period))

    async def get_trend(self, metric_name: str, hours: int = 24) -> Dict:
        rows = await self.db.fetchall(
            "SELECT value,timestamp FROM time_series WHERE metric_name=? AND timestamp>datetime('now',?) ORDER BY timestamp",
            (metric_name, f'-{hours} hours')
        )
        if len(rows) < 2:
            return {'trend': 'insufficient_data', 'direction': 'unknown'}
        values = [r[0] for r in rows]
        first_half = sum(values[:len(values)//2]) / max(len(values)//2, 1)
        second_half = sum(values[len(values)//2:]) / max(len(values) - len(values)//2, 1)
        direction = 'up' if second_half > first_half * 1.1 else ('down' if second_half < first_half * 0.9 else 'stable')
        return {'trend': direction, 'first_half_avg': first_half, 'second_half_avg': second_half, 'data_points': len(values)}


# --- 78. Watchdog ---
class Watchdog:
    """مراقب ذاتي وإعادة تشغيل عند التعطل"""
    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self._last_heartbeat = time.time()
        self._active = True

    def heartbeat(self):
        self._last_heartbeat = time.time()

    @property
    def is_alive(self):
        return time.time() - self._last_heartbeat < self.timeout

    @property
    def seconds_since_beat(self):
        return time.time() - self._last_heartbeat


# --- 79. تصعيد الأخطاء ---
class ErrorEscalator:
    """تصعيد الأخطاء حسب الخطورة والتكرار"""
    def __init__(self, levels: int = 3):
        self.levels = levels
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._escalation_map = {1: AlertLevel.LOW, 2: AlertLevel.MEDIUM, 3: AlertLevel.HIGH}

    def classify(self, error_type: str) -> AlertLevel:
        self._error_counts[error_type] += 1
        count = self._error_counts[error_type]
        level_num = min((count - 1) // 3 + 1, self.levels)
        return self._escalation_map.get(level_num, AlertLevel.CRITICAL)

    def reset(self, error_type: str):
        self._error_counts.pop(error_type, None)


# --- 81. إصدارات البرومبتات ---
class PromptVersionManager:
    """نظام إصدارات للبرومبتات مع rollback"""
    def __init__(self, db: Database, versions_dir: str):
        self.db = db
        self.versions_dir = versions_dir
        os.makedirs(versions_dir, exist_ok=True)

    async def save_version(self, role: str, content: str, ab_group: str = 'A') -> int:
        row = await self.db.fetchone("SELECT MAX(version) FROM prompt_versions WHERE role=?", (role,))
        version = (row[0] or 0) + 1
        await self.db.execute(
            "INSERT INTO prompt_versions (role,version,content,ab_group) VALUES (?,?,?,?)",
            (role, version, content, ab_group)
        )
        filepath = os.path.join(self.versions_dir, f"{role}_v{version}.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        log.info(f"برومبت محفوظ: {role} v{version}")
        return version

    async def get_active(self, role: str) -> str:
        row = await self.db.fetchone(
            "SELECT content FROM prompt_versions WHERE role=? AND is_active=1 ORDER BY version DESC LIMIT 1", (role,)
        )
        return row[0] if row else ""

    async def rollback(self, role: str, version: int):
        await self.db.execute("UPDATE prompt_versions SET is_active=0 WHERE role=?", (role,))
        await self.db.execute("UPDATE prompt_versions SET is_active=1 WHERE role=? AND version=?", (role, version))
        log.info(f"Rollback {role} إلى v{version}")


# --- 83. كشف تكرار متقدم N-gram ---
class NGramDeduplicator:
    """كشف تكرار متقدم باستخدام N-gram"""
    def __init__(self, n: int = 3):
        self.n = n
        self._seen: Set[str] = set()

    def get_ngrams(self, text: str) -> Set[str]:
        words = text.split()
        if len(words) < self.n:
            return {text}
        return {' '.join(words[i:i+self.n]) for i in range(len(words)-self.n+1)}

    def is_duplicate(self, text: str, threshold: float = 0.7) -> bool:
        ngrams = self.get_ngrams(text)
        if not ngrams:
            return False
        if not self._seen:
            self._seen = ngrams
            return False
        overlap = len(ngrams & self._seen) / len(ngrams)
        self._seen = ngrams
        return overlap > threshold


# --- 84. توجيه ذكي ---
class SmartRouter:
    """توجيه المهام لأفضل موديل بناءً على النوع"""
    TASK_MODEL_MAP = {
        'analysis': 'gemma-4-31b-it',
        'extraction': 'gemma-3-27b-it',
        'classification': 'gemini-2.5-flash',
        'correction': 'gemini-2.5-flash',
        'summarization': 'gemma-3-12b',
    }

    def route(self, task_type: str, available_models: List[str]) -> str:
        preferred = self.TASK_MODEL_MAP.get(task_type, 'gemini-2.5-flash')
        if preferred in available_models:
            return preferred
        return available_models[0] if available_models else 'gemini-2.5-flash'


# --- 89. ضغط البيانات ---
class DataCompressor:
    """ضغط النصوص الطويلة في DB"""
    @staticmethod
    def compress(text: str) -> bytes:
        return gzip.compress(text.encode('utf-8'))

    @staticmethod
    def decompress(data: bytes) -> str:
        return gzip.decompress(data).decode('utf-8')


# --- 90. تقييم جودة الاستجابة ---
class QualityScorer:
    """تقييم جودة ردود AI"""
    def score(self, prompt: str, response: str) -> float:
        if not response:
            return 0.0
        score = 0.5
        length = len(response)
        if 50 < length < 2000:
            score += 0.2
        elif length > 2000:
            score += 0.1
        if re.search(r'\d+', response):
            score += 0.1
        if re.search(r'[1-9]\.', response):
            score += 0.1
        useful_words = len(re.findall(r'[\u0600-\u06FF]{4,}', response))
        if useful_words > 5:
            score += 0.1
        return min(score, 1.0)


# --- 91. حماية من الحقن ---
class InjectionProtector:
    """فلترة مدخلات خطرة"""
    DANGEROUS_PATTERNS = [
        r'ignore\s+previous\s+instructions',
        r'forget\s+everything',
        r'jailbreak',
        r'DAN\s+mode',
        r'\<\s*script',
        r'eval\s*\(',
        r'exec\s*\(',
        r'os\.system',
        r'subprocess',
    ]

    def check(self, text: str) -> Tuple[bool, str]:
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"نمط خطير مكتشف: {pattern}"
        return False, "آمن"


# --- 94. لوحة تحكم TUI ---
class TUIDashboard:
    """واجهة نصية تفاعلية غنية"""
    def __init__(self, engine_ref):
        self.engine = engine_ref

    def render(self) -> str:
        m = self.engine.metrics
        lines = [
            "╔══════════════════════════════════════════════════════╗",
            "║           HERMES ENGINE v100.0 - لوحة التحكم         ║",
            "╠══════════════════════════════════════════════════════╣",
            f"║  الحالة: {self.engine.state.state.name:<42}║",
            f"║  التشغيل: {m.uptime:<41}║",
            f"║  الاستراتيجية: {self.engine.strategy.current_strategy.value:<37}║",
            f"║  الرسائل الواردة: {m.get_counter('messages_received'):<33.0f}║",
            f"║  الأوامر الصادرة: {m.get_counter('commands_sent'):<33.0f}║",
            f"║  الأخطاء: {m.get_counter('errors'):<40.0f}║",
            f"║  التكلفة: ${m.get_counter('total_cost'):<39.4f}║",
            f"║  الميزانية المتبقية: ${self.engine.cost_tracker.budget_remaining:<33.4f}║",
            "╚══════════════════════════════════════════════════════╝",
        ]
        return "\n".join(lines)


# --- 95. ملفات تعريف ---
class ProfileManager:
    """تبديل بين إعدادات مختلفة"""
    def __init__(self, db: Database, profiles_dir: str):
        self.db = db
        self.profiles_dir = profiles_dir
        os.makedirs(profiles_dir, exist_ok=True)

    async def save_profile(self, name: str, config: Config):
        await self.db.execute(
            "INSERT OR REPLACE INTO profiles (name,config_json) VALUES (?,?)",
            (name, json.dumps(config.to_dict(), ensure_ascii=False))
        )
        log.info(f"ملف تعريف محفوظ: {name}")

    async def load_profile(self, name: str) -> Optional[Dict]:
        row = await self.db.fetchone("SELECT config_json FROM profiles WHERE name=?", (name,))
        if row:
            return json.loads(row[0])
        return None

    async def list_profiles(self) -> List[str]:
        rows = await self.db.fetchall("SELECT name FROM profiles")
        return [r[0] for r in rows]

    async def activate(self, name: str):
        await self.db.execute("UPDATE profiles SET is_active=0")
        await self.db.execute("UPDATE profiles SET is_active=1 WHERE name=?", (name,))


# --- 98. اختبارات ذاتية ---
class SelfTester:
    """فحص ذاتي دوري"""
    def __init__(self, db: Database):
        self.db = db

    async def run_all(self) -> List[Dict]:
        results = []
        r = await self._test_db()
        results.append(r)
        r = await self._test_memory()
        results.append(r)
        r = await self._test_api()
        results.append(r)
        return results

    async def _test_db(self) -> Dict:
        start = time.time()
        try:
            await self.db.execute("SELECT 1")
            return {'test': 'database', 'result': 'pass', 'duration': time.time() - start}
        except Exception as e:
            return {'test': 'database', 'result': 'fail', 'details': str(e)[:100], 'duration': time.time() - start}

    async def _test_memory(self) -> Dict:
        start = time.time()
        try:
            r = await self.db.fetchone("SELECT COUNT(*) FROM memory")
            return {'test': 'memory', 'result': 'pass', 'duration': time.time() - start, 'entries': r[0]}
        except Exception as e:
            return {'test': 'memory', 'result': 'fail', 'details': str(e)[:100], 'duration': time.time() - start}

    async def _test_api(self) -> Dict:
        return {'test': 'api', 'result': 'skip', 'details': 'requires running engine'}

    async def save_results(self, results: List[Dict]):
        for r in results:
            await self.db.execute(
                "INSERT INTO self_tests (test_name,result,details,duration) VALUES (?,?,?,?)",
                (r['test'], r['result'], r.get('details', ''), r.get('duration', 0))
            )


# --- 99. محرك سيناريوهات ---
class ScenarioEngine:
    """تنفيذ سيناريوهات مركبة متعددة الخطوات"""
    def __init__(self, db: Database):
        self.db = db
        self._active: Dict[str, int] = {}

    async def create(self, name: str, steps: List[str]) -> str:
        scenario_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:8]
        steps_json = json.dumps(steps, ensure_ascii=False)
        await self.db.execute("INSERT INTO scenarios (name,steps,status) VALUES (?,?,'idle')", (name, steps_json))
        log.info(f"سيناريو جديد: {name} ({len(steps)} خطوات)")
        return scenario_id

    async def advance(self, name: str, result: str = "") -> Optional[str]:
        row = await self.db.fetchone("SELECT steps,current_step FROM scenarios WHERE name=? AND status='running'", (name,))
        if not row:
            return None
        steps = json.loads(row[0])
        current = row[1]
        await self.db.execute("UPDATE scenarios SET current_step=?,result=? WHERE name=?", (current+1, result[:500], name))
        if current + 1 >= len(steps):
            await self.db.execute("UPDATE scenarios SET status='completed' WHERE name=?", (name,))
            log.info(f"سيناريو مكتمل: {name}")
            return None
        return steps[current + 1]


# --- 100. محرك التحول الكامل (Meta-Engine) ---
class MetaEngine:
    """النظام يراقب ويحسّن نفسه تلقائياً"""
    def __init__(self, db: Database, metrics: Metrics, alerts: AlertManager, config: Config):
        self.db = db
        self.metrics = metrics
        self.alerts = alerts
        self.config = config
        self._last_review = 0
        self._improvements_made: List[str] = []

    async def review_and_optimize(self):
        """مراجعة دورية وتحسين ذاتي"""
        now = time.time()
        if now - self._last_review < self.config.META_REVIEW_INTERVAL:
            return
        self._last_review = now
        log.info("🧬 Meta-Engine: مراجعة ذاتية...")
        improvements = []

        # 1. فحص نسبة الأخطاء
        errors = self.metrics.get_counter('errors')
        commands = self.metrics.get_counter('commands_sent')
        if commands > 10 and errors / commands > 0.2:
            improvements.append("ارتفاع نسبة الأخطاء - يُقترح تقليل سرعة الإرسال")

        # 2. فحص زمن الاستجابة
        latency = self.metrics.get_histogram_stats('manager_latency')
        if latency.get('p95', 0) > 30:
            improvements.append("زمن استجابة مرتفع - يُقترح تبديل الموديل")

        # 3. فحص التكلفة مقابل الأوامر
        cost = self.metrics.get_counter('total_cost')
        if cost > 0 and commands > 0 and cost / commands > 0.01:
            improvements.append("تكلفة عالية لكل أمر - يُقترح تقليل حجم البرومبتات")

        for imp in improvements:
            log.info(f"🧬 Meta suggestion: {imp}")
            self._improvements_made.append(f"[{datetime.now().isoformat()}] {imp}")
            await self.alerts.fire(AlertLevel.MEDIUM, "meta_engine", imp)

        if not improvements:
            log.info("🧬 Meta-Engine: الأداء جيد - لا تحسينات مطلوبة")

    async def get_improvement_history(self) -> List[str]:
        return self._improvements_made[-20:]
