"""
═════════════════════════════════════════════════════════════════════════════
  infrastructure.py - المكونات الأساسية للبنية التحتية
═════════════════════════════════════════════════════════════════════════════
  يحتوي على:
    - RateLimiter: معدّل سرعة API (لكل دقيقة/يوم)
    - CircuitState: حالات قاطع الدائرة
    - CircuitBreaker: قاطع الدائرة للحماية من الأعطال
    - TTLCache: تخزين مؤقت مع وقت انتهاء
    - async_retry: ديكوريتر إعادة المحاولة مع تراجع أُسي
    - Metrics: نظام قياسات أداء شامل مع متوسط متحرك
"""

import asyncio
import random
import time
from collections import defaultdict, deque
from enum import Enum
from functools import wraps
from typing import Dict

from hermes.config import log


class RateLimiter:
    """معدّل سرعة API - حماية من التجاوز (لكل دقيقة/يوم)"""

    def __init__(self, cpm: int, cpd: int):
        self.minute_limit = cpm
        self.day_limit = cpd
        self._m: deque = deque()
        self._d: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """طلب إذن للاتصال - ينتظر إذا لزم الأمر"""
        async with self._lock:
            now = time.time()
            while self._m and now - self._m[0] > 60:
                self._m.popleft()
            while self._d and now - self._d[0] > 86400:
                self._d.popleft()
            if len(self._d) >= self.day_limit:
                w = 86400 - (now - self._d[0]) + 1
                log.warning(f"حد يومي: انتظار {w:.0f}s")
                await asyncio.sleep(w)
                return await self.acquire()
            if len(self._m) >= self.minute_limit:
                w = 60 - (now - self._m[0]) + 1
                await asyncio.sleep(w)
                return await self.acquire()
            self._m.append(now)
            self._d.append(now)

    @property
    def minute_remaining(self):
        now = time.time()
        while self._m and now - self._m[0] > 60:
            self._m.popleft()
        return self.minute_limit - len(self._m)

    @property
    def day_remaining(self):
        now = time.time()
        while self._d and now - self._d[0] > 86400:
            self._d.popleft()
        return self.day_limit - len(self._d)


class CircuitState(Enum):
    """حالات قاطع الدائرة"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """قاطع الدائرة - حماية من الأعطال المتكررة"""

    def __init__(self, name: str, ft: int = 5, rt: int = 60):
        self.name = name
        self.ft = ft  # failure threshold
        self.rt = rt  # reset timeout
        self.state = CircuitState.CLOSED
        self.fc = 0  # failure count
        self.sc = 0  # success count
        self.lft = 0  # last failure time
        self._lock = asyncio.Lock()

    async def can_proceed(self):
        """هل يمكن المتابعة؟"""
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                if time.time() - self.lft >= self.rt:
                    self.state = CircuitState.HALF_OPEN
                    return True
                return False
            return True  # HALF_OPEN

    async def record_success(self):
        """تسجيل نجاح"""
        async with self._lock:
            self.sc += 1
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.fc = 0

    async def record_failure(self, err: str = ""):
        """تسجيل فشل"""
        async with self._lock:
            self.fc += 1
            self.lft = time.time()
            if self.fc >= self.ft:
                self.state = CircuitState.OPEN
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN


class TTLCache:
    """تخزين مؤقت مع وقت انتهاء صلاحية"""

    def __init__(self, ttl: int = 300):
        self._c = {}
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    def get(self, k):
        if k in self._c:
            v, e = self._c[k]
            if time.time() < e:
                self.hits += 1
                return v
            del self._c[k]
        self.misses += 1
        return None

    def set(self, k, v, ttl=None):
        self._c[k] = (v, time.time() + (ttl or self.ttl))

    def invalidate(self, k):
        self._c.pop(k, None)

    def clear(self):
        self._c.clear()

    @property
    def hit_rate(self):
        t = self.hits + self.misses
        return self.hits / t if t > 0 else 0.0

    def cleanup(self):
        now = time.time()
        for k in [k for k, (_, e) in self._c.items() if now >= e]:
            del self._c[k]


def async_retry(max_retries=3, base_delay=2.0, max_delay=60.0, jitter=True, retryable_exceptions=(Exception,)):
    """ديكوريتر إعادة المحاولة مع تراجع أُسي واضطراب"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*a, **kw):
            last_ex = None
            for att in range(max_retries + 1):
                try:
                    return await func(*a, **kw)
                except retryable_exceptions as e:
                    last_ex = e
                    if att >= max_retries:
                        raise
                    d = min(base_delay * (2 ** att), max_delay)
                    if jitter:
                        d *= (0.5 + random.random() * 0.5)
                    log.warning(f"محاولة {att+1}/{max_retries} فشلت: {e}. إعادة بعد {d:.1f}s")
                    await asyncio.sleep(d)
            raise last_ex
        return wrapper
    return decorator


class Metrics:
    """نظام قياسات أداء شامل مع متوسط متحرك"""

    def __init__(self):
        self._counters = defaultdict(float)
        self._gauges = {}
        self._histograms = defaultdict(list)
        self._start_time = time.time()
        self._ma_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))

    def increment(self, n, v=1):
        self._counters[n] += v

    def gauge(self, n, v):
        self._gauges[n] = v

    def observe(self, n, v):
        self._histograms[n].append(v)
        if len(self._histograms[n]) > 1000:
            self._histograms[n] = self._histograms[n][-1000:]

    def moving_average(self, name, value):
        """66. حساب المتوسط المتحرك"""
        self._ma_windows[name].append(value)
        vals = list(self._ma_windows[name])
        return sum(vals) / len(vals) if vals else 0

    def get_counter(self, n):
        return self._counters.get(n, 0)

    def get_histogram_stats(self, n):
        v = self._histograms.get(n, [])
        if not v:
            return {'count': 0, 'avg': 0, 'min': 0, 'max': 0, 'p95': 0}
        s = sorted(v)
        return {
            'count': len(v),
            'avg': sum(v) / len(v),
            'min': s[0],
            'max': s[-1],
            'p95': s[int(len(s) * 0.95)]
        }

    @property
    def uptime(self):
        s = int(time.time() - self._start_time)
        h, r = divmod(s, 3600)
        m, s = divmod(r, 60)
        return f"{h}h {m}m {s}s"

    def summary(self):
        lines = [
            f"⏱ التشغيل: {self.uptime}",
            f"📊 رسائل واردة: {self._counters.get('messages_received', 0):.0f}",
            f"📤 أوامر صادرة: {self._counters.get('commands_sent', 0):.0f}",
            f"🧠 استدعاءات مدير: {self._counters.get('manager_calls', 0):.0f}",
            f"❌ أخطاء: {self._counters.get('errors', 0):.0f}",
            f"💰 تكلفة: ${self._counters.get('total_cost', 0):.4f}"
        ]
        l = self.get_histogram_stats('manager_latency')
        if l['count'] > 0:
            lines.append(f"⏳ استجابة المدير: {l['avg']:.1f}s (P95:{l['p95']:.1f}s)")
        return "\n".join(lines)
