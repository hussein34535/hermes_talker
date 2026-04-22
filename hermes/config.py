"""
═════════════════════════════════════════════════════════════════════════════
  config.py - الإعدادات المركزية وآلة الحالة ونظام السجل
═════════════════════════════════════════════════════════════════════════════
  يحتوي على:
    - ColoredFormatter: تنسيق السجل بالألوان
    - setup_logging: إعداد السجل الاحترافي
    - Config: إعدادات النظام المركزية (100 تحسين)
    - EngineState: حالات المحرك (12 حالة)
    - StateMachine: آلة الحالة مع التحولات
"""

import logging
import logging.handlers
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from typing import List
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()


# ════════════════════════════════════════════════════════════════════════════
# 1. نظام السجل الاحترافي
# ════════════════════════════════════════════════════════════════════════════

class ColoredFormatter(logging.Formatter):
    """تنسيق السجل بالألوان مع رموز تعبيرية"""
    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    EMOJIS = {'DEBUG': '🔍', 'INFO': '✅', 'WARNING': '⚠️', 'ERROR': '❌', 'CRITICAL': '🔥'}

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        emoji = self.EMOJIS.get(record.levelname, '')
        record.levelname = f"{color}{self.BOLD}{emoji} {record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(log_dir="logs", level=logging.INFO):
    """إعداد السجل الاحترافي مع ملفات دوارة"""
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("HermesEngine")
    logger.setLevel(level)
    logger.handlers.clear()

    # معالج الطرفية (ملون)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(ColoredFormatter('%(asctime)s │ %(levelname)s │ %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(ch)

    # معالج ملف السجل العام (دوّار)
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "hermes.log"),
        maxBytes=5 * 1024 * 1024, backupCount=10, encoding='utf-8'
    )
    fh.setFormatter(logging.Formatter('%(asctime)s │ %(levelname)s │ %(funcName)s:%(lineno)d │ %(message)s'))
    logger.addHandler(fh)

    # معالج ملف الأخطاء (دوّار)
    eh = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "errors.log"),
        maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )
    eh.setLevel(logging.ERROR)
    eh.setFormatter(logging.Formatter('%(asctime)s │ %(levelname)s │ %(message)s\n'))
    logger.addHandler(eh)

    return logger


# إنشاء السجل العام - يستخدمه كل ملف في الحزمة
log = setup_logging()


# ════════════════════════════════════════════════════════════════════════════
# 2. إدارة الإعدادات المركزية (100 تحسين)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """إعدادات النظام المركزية - 100 تحسين"""

    # --- تليجرام ---
    API_ID: int = 0
    API_HASH: str = ''
    HERMES_USERNAME: str = '@m3lmhermes_bot'
    SESSION_NAME: str = 'hussein_session'
    OPERATOR_CHAT_ID: int = 0  # 61. معرف المشغل للإشعارات المباشرة

    # --- Google GenAI ---
    GOOGLE_API_KEY: str = ''
    API_KEY_ROTATION_HOURS: int = 168  # 67. تدوير المفاتيح كل أسبوع

    # --- الموديلات ---
    MANAGER_MODEL: str = 'gemma-4-31b-it'
    SECRETARY_MODELS: List[str] = field(default_factory=lambda: ['gemma-3-27b-it', 'gemma-3-12b', 'gemini-2.5-flash'])
    ANALYST_MODEL: str = 'gemini-2.5-flash'
    CLASSIFIER_MODEL: str = 'gemini-2.5-flash'  # 69. موديل التصنيف
    CORRECTOR_MODEL: str = 'gemini-2.5-flash'    # 74. موديل التصحيح

    # --- أوقات الانتظار ---
    MESSAGE_COLLECT_TIMEOUT: int = 15
    MIN_DELAY_BETWEEN_MESSAGES: float = 2.0
    MAX_DELAY_BETWEEN_MESSAGES: float = 6.0
    TYPING_SIMULATION: bool = True

    # --- معدل السرعة ---
    API_CALLS_PER_MINUTE: int = 15
    API_CALLS_PER_DAY: int = 1500

    # --- الذاكرة ---
    MEMORY_MAX_ENTRIES: int = 500
    MEMORY_COMPRESS_THRESHOLD: int = 100
    MEMORY_SUMMARY_RATIO: float = 0.3

    # --- قاعدة البيانات ---
    DB_PATH: str = 'hermes_engine_v2.db'
    BACKUP_DIR: str = 'backups'
    BACKUP_INTERVAL_HOURS: int = 6
    DB_CONNECTION_POOL_SIZE: int = 5  # 87. حجم تجمّع الاتصالات

    # --- الدائرة القاطعة ---
    CIRCUIT_FAILURE_THRESHOLD: int = 5
    CIRCUIT_RESET_TIMEOUT: int = 60

    # --- إعادة المحاولة ---
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 2.0
    RETRY_MAX_DELAY: float = 60.0

    # --- التكلفة ---
    COST_PER_MANAGER_CALL: float = 0.002
    COST_PER_SECRETARY_CALL: float = 0.001
    DAILY_BUDGET_LIMIT: float = 5.0

    # --- المفاتيح (v1-50) ---
    ENABLE_SENTIMENT_ANALYSIS: bool = True
    ENABLE_OPPORTUNITY_SCORING: bool = True
    ENABLE_RISK_ASSESSMENT: bool = True
    ENABLE_LEARNING: bool = True
    ENABLE_AUTO_BACKUP: bool = True
    PARALLEL_MODEL_CALLS: bool = True

    # --- إعدادات جديدة 51-100 ---
    ENABLE_BOT_COMMANDS: bool = True          # 51. أوامر البوت
    AES_ENCRYPTION_KEY: str = ''              # 52. مفتاح التشفير
    ENABLE_TOKEN_COUNTING: bool = True        # 53. عداد التوكنز
    ENABLE_MULTI_THREAD: bool = True          # 54. محادثات متعددة
    WEBHOOK_PORT: int = 8765                  # 55. منفذ Webhook
    ENABLE_AUDIT_LOG: bool = True             # 56. سجل المراجعة
    CONFIG_WATCH_INTERVAL: int = 30           # 57. فترة مراقبة الإعدادات
    ENABLE_AB_TESTING: bool = True            # 58. A/B Testing
    ANOMALY_THRESHOLD: float = 2.5            # 59. عتبة كشف الشذوذ
    ENABLE_EXPORT: bool = True                # 60. تصدير البيانات
    ENABLE_OPERATOR_NOTIFICATIONS: bool = True # 61. إشعارات المشغل
    ENABLE_RULES_ENGINE: bool = True          # 62. محرك القواعد
    PERSISTENT_CACHE_PATH: str = 'cache_store.json'  # 63. مسار الكاش الدائم
    ENABLE_REPLAY: bool = True                # 64. إعادة اللعب
    ENABLE_DEPENDENCY_TRACKING: bool = True   # 65. تتبع التبعيات
    MOVING_AVERAGE_WINDOW: int = 20           # 66. نافذة المتوسط المتحرك
    ENABLE_KEY_ROTATION: bool = False         # 67. تدوير المفاتيح
    CYCLE_DETECTION_WINDOW: int = 50          # 68. نافذة كشف الأنماط
    ENABLE_AUTO_CLASSIFY: bool = True         # 69. تصنيف تلقائي
    WARMUP_CATEGORIES: List[str] = field(default_factory=lambda: ['analysis', 'command', 'opportunity'])  # 70
    ENABLE_RESOURCE_MONITOR: bool = True      # 71. مراقبة الموارد
    RESOURCE_CHECK_INTERVAL: int = 60         # فحص الموارد كل 60 ثانية
    ENABLE_DYNAMIC_PRIORITY: bool = True      # 72. أولويات ديناميكية
    ENABLE_SMART_MODEL_SELECT: bool = True    # 73. اختيار موديل ذكي
    ENABLE_AUTO_CORRECTION: bool = True       # 74. تصحيح تلقائي
    ENABLE_CHAIN_TRACKING: bool = True        # 75. تتبع سلسلة الأوامر
    ENABLE_TIME_SERIES: bool = True           # 76. تحليل سلاسل زمنية
    HTTP_MONITOR_PORT: int = 9090             # 77. منفذ HTTP المراقبة
    ENABLE_HTTP_MONITOR: bool = True          # تفعيل خادم المراقبة
    WATCHDOG_TIMEOUT: int = 300               # 78. مهلة المراقب
    ERROR_ESCALATION_LEVELS: int = 3          # 79. مستويات تصعيد الأخطاء
    ENABLE_INTERACTIVE_CONSOLE: bool = True   # 80. واجهة تفاعلية
    PROMPT_VERSIONS_DIR: str = 'prompt_versions'  # 81. مجلد إصدارات البرومبتات
    ENABLE_PROFIT_DASHBOARD: bool = True      # 82. لوحة ربح
    NGRAM_DEDUP_SIZE: int = 3                 # 83. حجم N-gram للكشف
    ENABLE_SMART_ROUTING: bool = True         # 84. توجيه ذكي
    PERF_COMPARISON_INTERVAL: int = 3600      # 85. فترة مقارنة الأداء
    CRON_SCHEDULES: List[str] = field(default_factory=list)  # 86. جداول Cron
    ENABLE_PROGRESSIVE_LOADING: bool = True   # 88. تحميل تدريجي
    COMPRESS_DB_TEXT_THRESHOLD: int = 500     # 89. عتبة ضغط النصوص
    ENABLE_QUALITY_SCORING: bool = True       # 90. تقييم الجودة
    ENABLE_INJECTION_PROTECTION: bool = True  # 91. حماية الحقن
    ENABLE_ENERGY_TRACKING: bool = True       # 92. تتبع الطاقة
    ENABLE_COMPETITOR_ANALYSIS: bool = True   # 93. تحليل منافسين
    ENABLE_TUI_DASHBOARD: bool = True         # 94. لوحة TUI
    PROFILES_DIR: str = 'profiles'            # 95. مجلد الملفات الشخصية
    ACTIVE_PROFILE: str = 'default'           # الملف النشط
    CLOUD_SYNC_ENDPOINT: str = ''             # 96. نقطة نهاية المزامنة
    ALERT_SUMMARY_INTERVAL: int = 600         # 97. فترة تلخيص التنبيهات
    SELF_TEST_INTERVAL: int = 1800            # 98. فترة الاختبارات الذاتية
    ENABLE_SCENARIO_ENGINE: bool = True       # 99. محرك السيناريوهات
    ENABLE_META_ENGINE: bool = True           # 100. محرك التحول الكامل
    META_REVIEW_INTERVAL: int = 3600          # فترة مراجعة Meta

    @classmethod
    def from_env(cls):
        """إنشاء إعدادات من متغيرات البيئة"""
        return cls(
            API_ID=int(os.getenv('TG_API_ID', cls.API_ID)),
            API_HASH=os.getenv('TG_API_HASH', cls.API_HASH),
            HERMES_USERNAME=os.getenv('HERMES_BOT', cls.HERMES_USERNAME),
            GOOGLE_API_KEY=os.getenv('GOOGLE_API_KEY', cls.GOOGLE_API_KEY),
            AES_ENCRYPTION_KEY=os.getenv('AES_ENCRYPTION_KEY', cls.AES_ENCRYPTION_KEY),
        )

    def to_dict(self):
        return asdict(self)

    def mask_secrets(self):
        """إخفاء البيانات الحساسة للعرض"""
        d = self.to_dict()
        for k in ['API_HASH', 'GOOGLE_API_KEY', 'AES_ENCRYPTION_KEY']:
            if k in d and d[k]:
                d[k] = str(d[k])[:6] + '***'
        return d


# ════════════════════════════════════════════════════════════════════════════
# 3. آلة الحالة
# ════════════════════════════════════════════════════════════════════════════

class EngineState(Enum):
    """حالات المحرك - 12 حالة مع تحولات محددة"""
    INITIALIZING = auto()
    CONNECTING = auto()
    IDLE = auto()
    COLLECTING = auto()
    PROCESSING = auto()
    ANALYZING = auto()
    DISPATCHING = auto()
    WAITING_RESPONSE = auto()
    ERROR_RECOVERY = auto()
    SHUTTING_DOWN = auto()
    OFFLINE = auto()
    MAINTENANCE = auto()  # حالة جديدة للصيانة


class StateMachine:
    """آلة الحالة مع تحولات مسموحة ومراقبة"""
    TRANSITIONS = {
        EngineState.INITIALIZING: [EngineState.CONNECTING, EngineState.ERROR_RECOVERY, EngineState.SHUTTING_DOWN],
        EngineState.CONNECTING: [EngineState.IDLE, EngineState.ERROR_RECOVERY, EngineState.SHUTTING_DOWN],
        EngineState.IDLE: [EngineState.COLLECTING, EngineState.SHUTTING_DOWN, EngineState.ERROR_RECOVERY, EngineState.MAINTENANCE],
        EngineState.COLLECTING: [EngineState.PROCESSING, EngineState.IDLE, EngineState.ERROR_RECOVERY],
        EngineState.PROCESSING: [EngineState.ANALYZING, EngineState.ERROR_RECOVERY, EngineState.IDLE],
        EngineState.ANALYZING: [EngineState.DISPATCHING, EngineState.ERROR_RECOVERY, EngineState.IDLE],
        EngineState.DISPATCHING: [EngineState.WAITING_RESPONSE, EngineState.ERROR_RECOVERY, EngineState.IDLE],
        EngineState.WAITING_RESPONSE: [EngineState.COLLECTING, EngineState.IDLE, EngineState.ERROR_RECOVERY],
        EngineState.ERROR_RECOVERY: [EngineState.IDLE, EngineState.CONNECTING, EngineState.SHUTTING_DOWN],
        EngineState.MAINTENANCE: [EngineState.IDLE, EngineState.SHUTTING_DOWN],
        EngineState.SHUTTING_DOWN: [EngineState.OFFLINE],
        EngineState.OFFLINE: [EngineState.INITIALIZING],
    }

    def __init__(self):
        self._state = EngineState.INITIALIZING
        self._history = [(self._state, datetime.now())]
        self._state_start = datetime.now()

    @property
    def state(self):
        return self._state

    @property
    def time_in_state(self):
        return (datetime.now() - self._state_start).total_seconds()

    def transition(self, new):
        """تحول آمن بين الحالات"""
        if new in self.TRANSITIONS.get(self._state, []):
            old = self._state
            self._state = new
            self._state_start = datetime.now()
            self._history.append((new, datetime.now()))
            log.info(f"تحول: {old.name} → {new.name}")
            return True
        log.warning(f"تحول غير مسموح: {self._state.name} → {new.name}")
        return False

    def force_state(self, new):
        """فرض تحول بغض النظر عن القواعد"""
        old = self._state
        self._state = new
        self._state_start = datetime.now()
        self._history.append((new, datetime.now()))
        log.warning(f"فرض تحول: {old.name} → {new.name}")

    def history_summary(self):
        """ملخص آخر 20 تحول"""
        return " → ".join(s.name for s, _ in self._history[-20:])
