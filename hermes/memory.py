"""
═════════════════════════════════════════════════════════════════════════════
  memory.py - نظام الذاكرة والتعلم والنسخ الاحتياطي
═════════════════════════════════════════════════════════════════════════════
  يحتوي على:
    - SmartMemory: ذاكرة ذكية مع ضغط وتلخيص تلقائي
    - ModelHealthTracker: تتبع صحة الموديلات
    - SentimentAnalyzer: تحليل مشاعر الرسائل
    - LearningSystem: نظام التعلم من التفاعلات
    - BackupSystem: نظام النسخ الاحتياطي التلقائي
    - MessageQueue / QueuedMessage: طابور رسائل موثوق
    - CostTracker: تتبع تكلفة API
"""
import asyncio
import hashlib
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from hermes.config import log
from hermes.database import Database
from hermes.infrastructure import TTLCache
from hermes.alerts import AlertLevel, AlertManager


# ════════════════════════════════════════════════════════════════════════════
# 11. نظام الذاكرة الذكية
# ════════════════════════════════════════════════════════════════════════════

class SmartMemory:
    """ذاكرة ذكية مع ضغط وتلخيص تلقائي وخاصية كاش"""

    def __init__(self, db: Database, config):
        self.db = db
        self.config = config
        self._cache = TTLCache(60)
        self._total = 0

    async def initialize(self):
        r = await self.db.fetchone("SELECT COUNT(*) FROM memory")
        self._total = r[0] if r else 0
        log.info(f"الذاكرة: {self._total} سجل")

    async def add(self, content, category="general", importance=0.5, thread_id="default"):
        """إضافة سجل جديد مع منع التكرار عبر الهاش"""
        h = hashlib.md5(content.encode()).hexdigest()
        ex = await self.db.fetchone("SELECT id FROM memory WHERE hash=?", (h,))
        if ex:
            return ex[0]
        importance = min(importance + 0.1 if importance < 1.0 else 0, 1.0)
        c = await self.db.execute(
            "INSERT INTO memory (timestamp,category,content,importance,hash,thread_id) VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), category, content, importance, h, thread_id)
        )
        self._total += 1
        if self._total >= self.config.MEMORY_COMPRESS_THRESHOLD:
            await self.compress()
        return c.lastrowid

    async def get_recent(self, limit=20, category=None, thread_id=None):
        """جلب أحدث السجلات مع كاش"""
        ck = f"recent:{limit}:{category}:{thread_id}"
        cached = self._cache.get(ck)
        if cached:
            return cached
        q = "SELECT timestamp,category,content,importance FROM memory WHERE 1=1"
        p = []
        if category:
            q += " AND category=?"
            p.append(category)
        if thread_id:
            q += " AND thread_id=?"
            p.append(thread_id)
        q += " ORDER BY timestamp DESC LIMIT ?"
        p.append(limit)
        rows = await self.db.fetchall(q, tuple(p))
        result = [{'timestamp': r[0], 'category': r[1], 'content': r[2], 'importance': r[3]} for r in rows]
        self._cache.set(ck, result, 30)
        return result

    async def get_context_for_prompt(self, max_chars=3000):
        """جلب السياق للبرومبت مع أولوية حسب الأهمية"""
        rows = await self.db.fetchall(
            "SELECT content,importance FROM memory ORDER BY importance DESC,timestamp DESC LIMIT 50"
        )
        parts = []
        cl = 0
        for c, i in rows:
            if cl + len(c) > max_chars:
                rem = max_chars - cl
                if rem > 50:
                    parts.append(c[:rem] + "...")
                break
            parts.append(c)
            cl += len(c)
        return "\n".join(parts) if parts else "سجل المشروع فارغ: البداية الآن."

    async def compress(self):
        """ضغط السجلات القديمة منخفضة الأهمية"""
        old = await self.db.fetchall(
            "SELECT id,content FROM memory WHERE importance<0.3 AND timestamp<datetime('now','-1 day') ORDER BY timestamp ASC LIMIT 50"
        )
        if not old or len(old) < 5:
            return
        combined = "\n".join(f"- {c}" for _, c in old)
        summary = self._local_summarize(combined)
        await self.db.execute(
            "INSERT INTO memory (timestamp,category,content,summary,importance,hash) VALUES (?,'compressed',?, ?,0.2,?)",
            (datetime.now().isoformat(), f"ملخص مضغوط: {summary}", summary, hashlib.md5(summary.encode()).hexdigest())
        )
        ids = tuple(e[0] for e in old)
        ph = ','.join('?' * len(ids))
        await self.db.execute(f"DELETE FROM memory WHERE id IN ({ph})", ids)
        self._total -= len(old)
        self._cache.clear()

    def _local_summarize(self, text):
        """تلخيص محلي بدون API"""
        lines = text.split('\n')
        if len(lines) <= 5:
            return text[:500]
        words = re.findall(r'[\u0600-\u06FF]+', text.lower())
        wf = defaultdict(int)
        for w in words:
            if len(w) > 3:
                wf[w] += 1
        top = sorted(wf, key=wf.get, reverse=True)[:5]
        return f"ملخص ({len(lines)} سجل): " + " | ".join(top) + f"\nأول: {lines[0][:100]}"


# ════════════════════════════════════════════════════════════════════════════
# 12. تتبع صحة الموديلات
# ════════════════════════════════════════════════════════════════════════════

class ModelHealthTracker:
    """تتبع صحة الموديلات مع اختيار الأفضل"""

    def __init__(self, db: Database):
        self.db = db
        self._health = {}

    async def initialize(self, models):
        for m in models:
            r = await self.db.fetchone(
                "SELECT success,failure,avg_latency FROM model_health WHERE model_name=? ORDER BY id DESC LIMIT 1", (m,)
            )
            self._health[m] = {
                'success': r[0] if r else 0,
                'failure': r[1] if r else 0,
                'avg_latency': r[2] if r else 0,
                'available': True
            }

    async def record_success(self, model, latency):
        h = self._health.get(model, {})
        h['success'] = h.get('success', 0) + 1
        old = h.get('avg_latency', 0)
        h['avg_latency'] = old * 0.8 + latency * 0.2
        h['available'] = True
        await self.db.execute(
            "INSERT INTO model_health (model_name,success,avg_latency,last_used) VALUES (?,?,?,?)",
            (model, 1, latency, datetime.now().isoformat())
        )

    async def record_failure(self, model, error):
        h = self._health.get(model, {})
        h['failure'] = h.get('failure', 0) + 1
        if h.get('failure', 0) > 3 and h.get('success', 0) / max(h.get('failure', 0) + h.get('success', 0), 1) < 0.5:
            h['available'] = False
        await self.db.execute(
            "INSERT INTO model_health (model_name,failure,last_error,last_used) VALUES (?,1,?,?)",
            (model, error[:200], datetime.now().isoformat())
        )

    def get_best_model(self, candidates):
        """اختيار أفضل موديل بناءً على نسبة النجاح والسرعة"""
        avail = [m for m in candidates if self._health.get(m, {}).get('available', True)]
        if not avail:
            return candidates[0]

        def score(m):
            h = self._health.get(m, {'success': 0, 'failure': 0, 'avg_latency': 5})
            t = h.get('success', 0) + h.get('failure', 0)
            sr = h.get('success', 0) / max(t, 1)
            ls = 1.0 / max(h.get('avg_latency', 5), 0.1)
            return sr * 0.7 + ls * 0.3

        return max(avail, key=score)

    def health_report(self):
        lines = ["📊 صحة الموديلات:"]
        for m, h in self._health.items():
            t = h.get('success', 0) + h.get('failure', 0)
            r = h.get('success', 0) / max(t, 1) * 100
            s = "✅" if h.get('available', True) else "❌"
            lines.append(f"  {s} {m}: {r:.0f}% | {h.get('avg_latency', 0):.1f}s | ({h.get('success', 0)}/{t})")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# 14. تحليل المشاعر
# ════════════════════════════════════════════════════════════════════════════

class SentimentAnalyzer:
    """تحليل مشاعر النصوص العربية"""
    POS = {'ربح', 'نجاح', 'مكسب', 'فوز', 'تحسن', 'زيادة', 'نمو', 'إيجابي', 'ممتاز', 'فرصة', 'مفيد', 'تقدم', 'إنجاز', 'أرباح'}
    NEG = {'خسارة', 'فشل', 'خطأ', 'مشكلة', 'عطل', 'انخفاض', 'تراجع', 'سلبي', 'صعوبة', 'خطر', 'تحذير', 'ضعيف', 'سيء'}

    def analyze(self, text):
        words = set(re.findall(r'[\u0600-\u06FF]+', text.lower()))
        pc = len(words & self.POS)
        nc = len(words & self.NEG)
        t = max(pc + nc, 1)
        ov = (pc - nc) / t
        return {
            'positive': pc / t,
            'negative': nc / t,
            'overall': ov,
            'label': 'positive' if ov > 0.15 else ('negative' if ov < -0.15 else 'neutral')
        }


# ════════════════════════════════════════════════════════════════════════════
# 15. نظام التعلم
# ════════════════════════════════════════════════════════════════════════════

class LearningSystem:
    """نظام التعلم من التفاعلات السابقة"""

    def __init__(self, db: Database):
        self.db = db
        self._patterns = {}

    async def initialize(self):
        rows = await self.db.fetchall(
            "SELECT pattern,outcome,success_score,occurrence_count FROM learning ORDER BY occurrence_count DESC LIMIT 100"
        )
        for p, o, s, c in rows:
            self._patterns[p] = {'outcome': o, 'score': s, 'count': c}
        log.info(f"التعلم: {len(self._patterns)} نمط")

    async def record_outcome(self, pattern, outcome, score):
        if pattern in self._patterns:
            p = self._patterns[pattern]
            old = p['score'] * p['count']
            p['count'] += 1
            p['score'] = (old + score) / p['count']
            p['outcome'] = outcome
            await self.db.execute(
                "UPDATE learning SET success_score=?,occurrence_count=?,last_seen=?,outcome=? WHERE pattern=?",
                (p['score'], p['count'], datetime.now().isoformat(), outcome, pattern)
            )
        else:
            self._patterns[pattern] = {'outcome': outcome, 'score': score, 'count': 1}
            await self.db.execute(
                "INSERT INTO learning (pattern,outcome,success_score,occurrence_count) VALUES (?,?,?,1)",
                (pattern, outcome, score)
            )

    def get_successful_patterns(self, limit=5):
        return [(p, d['score']) for p, d in sorted(
            self._patterns.items(),
            key=lambda x: x[1]['score'] * min(x[1]['count'] / 3, 1),
            reverse=True
        )[:limit]]

    def get_prompt_enhancements(self):
        sp = self.get_successful_patterns(3)
        if not sp:
            return ""
        return "أنماط ناجحة:\n" + "\n".join(f"- {p} ({s:.0%})" for p, s in sp)


# ════════════════════════════════════════════════════════════════════════════
# 16. نظام النسخ الاحتياطي
# ════════════════════════════════════════════════════════════════════════════

class BackupSystem:
    """نظام نسخ احتياطي تلقائي لقاعدة البيانات"""

    def __init__(self, db: Database, config):
        self.db = db
        self.config = config
        self._last = 0

    async def backup_if_needed(self):
        now = time.time()
        if now - self._last < self.config.BACKUP_INTERVAL_HOURS * 3600:
            return
        os.makedirs(self.config.BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bp = os.path.join(self.config.BACKUP_DIR, f"hermes_backup_{ts}.db")
        try:
            import shutil
            shutil.copy2(self.config.DB_PATH, bp)
            self._last = now
            log.info(f"نسخة احتياطية: {bp}")
            bk = sorted(Path(self.config.BACKUP_DIR).glob("hermes_backup_*.db"))
            for o in bk[:-10]:
                o.unlink()
        except Exception as e:
            log.error(f"فشل النسخ: {e}")


# ════════════════════════════════════════════════════════════════════════════
# 17. طابور الرسائل
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class QueuedMessage:
    """رسالة في الطابور"""
    id: str
    content: str
    priority: int = 5
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    max_attempts: int = 3
    sent: bool = False


class MessageQueue:
    """طابور رسائل موثوق مع أولويات"""

    def __init__(self):
        self._q = []
        self._sent = []
        self._lock = asyncio.Lock()

    async def enqueue(self, content, priority=5):
        import asyncio
        mid = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:8]
        msg = QueuedMessage(id=mid, content=content, priority=priority)
        async with self._lock:
            self._q.append(msg)
            self._q.sort(key=lambda m: m.priority)
        return mid

    async def dequeue(self):
        import asyncio
        async with self._lock:
            return self._q.pop(0) if self._q else None

    async def mark_sent(self, msg):
        msg.sent = True
        self._sent.append(msg)

    async def mark_failed(self, msg):
        msg.attempts += 1
        if msg.attempts < msg.max_attempts:
            msg.priority = max(1, msg.priority - 1)
            async with self._lock:
                self._q.append(msg)
                self._q.sort(key=lambda m: m.priority)

    @property
    def pending_count(self):
        return len(self._q)


# ════════════════════════════════════════════════════════════════════════════
# 18. تتبع التكلفة
# ════════════════════════════════════════════════════════════════════════════

class CostTracker:
    """تتبع تكلفة API مع حد يومي وتنبيهات"""

    def __init__(self, db: Database, config, metrics, alerts: AlertManager):
        self.db = db
        self.config = config
        self.metrics = metrics
        self.alerts = alerts
        self._daily = 0.0
        self._last_reset = datetime.now().date()
        self._tokens_today = 0  # 53. توكنز

    async def record_call(self, model, operation, cost, tokens=0):
        today = datetime.now().date()
        if today != self._last_reset:
            self._daily = 0.0
            self._tokens_today = 0
            self._last_reset = today
        self._daily += cost
        self._tokens_today += tokens
        self.metrics.increment('total_cost', cost)
        self.metrics.gauge('daily_cost', self._daily)
        self.metrics.gauge('tokens_today', self._tokens_today)
        await self.db.execute(
            "INSERT INTO cost_tracking (model_name,operation_type,cost,tokens_used) VALUES (?,?,?,?)",
            (model, operation, cost, tokens)
        )
        if self._daily > self.config.DAILY_BUDGET_LIMIT * 0.8:
            await self.alerts.fire(AlertLevel.HIGH, "budget", f"التكلفة ${self._daily:.4f} (80% من الحد)")

    @property
    def budget_remaining(self):
        return max(self.config.DAILY_BUDGET_LIMIT - self._daily, 0)

    @property
    def can_afford(self):
        return self._daily < self.config.DAILY_BUDGET_LIMIT
