"""
═════════════════════════════════════════════════════════════════════════════
  strategy.py - محرك الاستراتيجيات
═════════════════════════════════════════════════════════════════════════════
  يحتوي على:
    - Strategy: أنواع الاستراتيجيات (هجومي/متوازن/محافظ/انتهازي)
    - StrategyConfig: إعدادات كل استراتيجية
    - STRATEGY_PROFILES: ملفات التعريف الافتراضية
    - StrategyEngine: محرك الاستراتيجيات مع تقييم المخاطر والفرص
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List

from hermes.config import log
from hermes.database import Database
from hermes.infrastructure import Metrics
from hermes.alerts import AlertManager


class Strategy(Enum):
    """أنواع الاستراتيجيات"""
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"
    OPPORTUNISTIC = "opportunistic"


@dataclass
class StrategyConfig:
    """إعدادات الاستراتيجية"""
    strategy: Strategy
    max_daily_commands: int
    risk_threshold: float
    profit_target: float
    description: str


STRATEGY_PROFILES = {
    Strategy.AGGRESSIVE: StrategyConfig(Strategy.AGGRESSIVE, 30, 0.8, 0.5, "هجومي: مخاطرة عالية، أرباح سريعة"),
    Strategy.BALANCED: StrategyConfig(Strategy.BALANCED, 15, 0.5, 0.3, "متوازن: توازن بين المخاطرة والأرباح"),
    Strategy.CONSERVATIVE: StrategyConfig(Strategy.CONSERVATIVE, 8, 0.3, 0.15, "محافظ: مخاطرة منخفضة"),
    Strategy.OPPORTUNISTIC: StrategyConfig(Strategy.OPPORTUNISTIC, 20, 0.6, 0.4, "انتهازي: انتظر الفرص ثم اضرب"),
}


class StrategyEngine:
    """محرك الاستراتيجيات مع تقييم المخاطر واكتشاف الفرص"""

    def __init__(self, db: Database, metrics: Metrics, alerts: AlertManager):
        self.db = db
        self.metrics = metrics
        self.alerts = alerts
        self.current_strategy = Strategy.BALANCED
        self._commands_today = 0
        self._last_reset = datetime.now().date()

    @property
    def config(self):
        return STRATEGY_PROFILES[self.current_strategy]

    def can_send_command(self):
        """هل يمكن إرسال أمر جديد؟"""
        today = datetime.now().date()
        if today != self._last_reset:
            self._commands_today = 0
            self._last_reset = today
        return self._commands_today < self.config.max_daily_commands

    def record_command(self):
        self._commands_today += 1

    async def assess_risk(self, cmd):
        """تقييم مخاطر الأمر قبل الإرسال"""
        rs = 0.0
        factors = []
        for w in ['حذف', 'مسح', 'بيع كامل', 'استثمار كامل']:
            if w in cmd:
                rs += 0.3
                factors.append(f"عالي المخاطرة: {w}")
        for w in ['شراء', 'بيع', 'استثمار', 'تحويل']:
            if w in cmd:
                rs += 0.1
                factors.append(f"متوسط المخاطرة: {w}")
        rs = min(rs, 1.0)
        return rs, "; ".join(factors) if factors else "مخاطرة منخفضة"

    async def detect_opportunities(self, text):
        """اكتشاف الفرص في النص"""
        opps = []
        patterns = {
            'price_drop': (r'(?:انخفاض|هبوط)', 0.7, 'فرصة شراء'),
            'bonus': (r'(?:مكافأة|بونص|هدية)', 0.8, 'مكافأة متاحة'),
            'arbitrage': (r'(?:فرق سعر|مراجحة)', 0.9, 'فرصة مراجحة'),
            'new_service': (r'(?:خدمة جديدة|إطلاق)', 0.6, 'خدمة جديدة'),
        }
        for ot, (pat, sc, desc) in patterns.items():
            if re.search(pat, text):
                opps.append({
                    'type': ot,
                    'score': sc,
                    'description': desc,
                    'risk_level': 'high' if sc > 0.7 else 'medium'
                })
        return opps

    async def adapt_strategy(self):
        """تكيف تلقائي للاستراتيجية حسب الأداء"""
        err = self.metrics.get_counter('errors')
        cmds = self.metrics.get_counter('commands_sent')
        if cmds > 0 and err / cmds > 0.3 and self.current_strategy != Strategy.CONSERVATIVE:
            self.current_strategy = Strategy.CONSERVATIVE
            log.warning("تحول تلقائي للمحافظ")
