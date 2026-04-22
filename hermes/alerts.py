"""
═════════════════════════════════════════════════════════════════════════════
  alerts.py - نظام التنبيهات الذكي
═════════════════════════════════════════════════════════════════════════════
  يحتوي على:
    - AlertLevel: مستويات التنبيه (منخفض/متوسط/عالي/حرج)
    - Alert: بيانات التنبيه
    - AlertManager: مدير التنبيهات مع تلخيص وتبريد
"""

import asyncio
import logging
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List

from hermes.config import log


class AlertLevel(Enum):
    """مستويات التنبيه"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Alert:
    """بيانات التنبيه"""
    level: AlertLevel
    category: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False


class AlertManager:
    """مدير التنبيهات الذكي مع تلخيص وتبريد"""

    def __init__(self):
        self._alerts = []
        self._handlers = []
        self._cooldowns = {}
        self._cd = 300  # فترة التبريد (ثانية)
        self._summary_buffer: List[Alert] = []  # 97. تلخيص التنبيهات

    def add_handler(self, h):
        """إضافة معالج تنبيهات"""
        self._handlers.append(h)

    async def fire(self, level, category, message):
        """إطلاق تنبيه مع تبريد تلقائي"""
        key = f"{category}:{message[:50]}"
        now = time.time()
        # تبريد: لا تكرر نفس التنبيه خلال 5 دقائق
        if key in self._cooldowns and now - self._cooldowns[key] < self._cd:
            return
        self._cooldowns[key] = now
        a = Alert(level=level, category=category, message=message)
        self._alerts.append(a)
        self._summary_buffer.append(a)

        emj = {'LOW': '💡', 'MEDIUM': '⚠️', 'HIGH': '🚨', 'CRITICAL': '🔴'}
        lvl = {'LOW': logging.INFO, 'MEDIUM': logging.WARNING, 'HIGH': logging.ERROR, 'CRITICAL': logging.CRITICAL}
        log.log(lvl.get(level.name, logging.INFO), f"{emj.get(level.name, '📢')} [{level.value}] {category}: {message}")

        for h in self._handlers:
            try:
                if asyncio.iscoroutinefunction(h):
                    await h(a)
                else:
                    h(a)
            except:
                pass

    async def get_summary(self):
        """97. تلخيص التنبيهات المتكررة"""
        if not self._summary_buffer:
            return "لا توجد تنبيهات جديدة"
        by_cat = defaultdict(list)
        for a in self._summary_buffer:
            by_cat[a.category].append(a)
        lines = []
        for cat, alerts in by_cat.items():
            lines.append(f"📋 {cat}: {len(alerts)} تنبيه")
            levels = Counter(a.level.value for a in alerts)
            for lv, cnt in levels.items():
                lines.append(f"  - {lv}: {cnt}")
        self._summary_buffer.clear()
        return "\n".join(lines)

    @property
    def active_alerts(self):
        return [a for a in self._alerts if not a.resolved]

    def resolve(self, cat):
        """حل كل تنبيهات فئة معينة"""
        for a in self._alerts:
            if a.category == cat and not a.resolved:
                a.resolved = True
