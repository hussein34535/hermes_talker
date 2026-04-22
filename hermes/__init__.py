"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           HERMES AUTOMATION ENGINE v100.0                                   ║
║              النظام الشامل للأتمتة الذكية - الجيل المائة                   ║
║                                                                            ║
║  حزمة بايثون احترافية مكونة من 13 مodule                                   ║
║  كل ملف مسؤول عن جزء محدد من النظام                                        ║
║  المايسترو: main.py يجمع كل شيء ويشغّل المحرك                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

__version__ = "100.0"
__author__ = "Hussein - Hermes Engine"

# استيراد المكونات الأساسية (لا تحتاج مكتبات خارجية)
from hermes.config import Config, EngineState, StateMachine
from hermes.database import Database
from hermes.infrastructure import RateLimiter, CircuitBreaker, CircuitState, TTLCache, Metrics, async_retry
from hermes.alerts import AlertLevel, Alert, AlertManager
from hermes.memory import SmartMemory, LearningSystem, BackupSystem, MessageQueue, QueuedMessage, CostTracker, ModelHealthTracker, SentimentAnalyzer
from hermes.strategy import Strategy, StrategyConfig, StrategyEngine, STRATEGY_PROFILES
from hermes.tools import (
    DataEncryptor, TokenCounter, ThreadManager, AuditLogger,
    ABTestingEngine, AnomalyDetector, DataExporter, RulesEngine,
    PersistentCache, ReplayEngine, DependencyTracker, AutoClassifier,
    ResourceMonitor, AutoCorrector, TimeSeriesAnalyzer,
    Watchdog, ErrorEscalator, PromptVersionManager, NGramDeduplicator,
    SmartRouter, DataCompressor, QualityScorer, InjectionProtector,
    ScenarioEngine, MetaEngine, SelfTester, ProfileManager,
)

# استيراد كسول للمكونات اللي تحتاج مكتبات خارجية (telethon, google)
# هذه تُستورد فقط عند الحاجة لتجنب أخطاء الاستيراد
def __getattr__(name):
    """استيراد كسول - يتم فقط عند الوصول الفعلي"""
    if name == 'AIEngine':
        from hermes.ai_engine import AIEngine
        return AIEngine
    if name == 'HermesEngine':
        from hermes.engine import HermesEngine
        return HermesEngine
    raise AttributeError(f"module 'hermes' has no attribute {name}")

__all__ = [
    # Config & State
    'Config', 'EngineState', 'StateMachine',
    # Database
    'Database',
    # Infrastructure
    'RateLimiter', 'CircuitBreaker', 'CircuitState', 'TTLCache', 'Metrics', 'async_retry',
    # Alerts
    'AlertLevel', 'Alert', 'AlertManager',
    # Memory & Learning
    'SmartMemory', 'LearningSystem', 'BackupSystem', 'MessageQueue', 'QueuedMessage',
    'CostTracker', 'ModelHealthTracker', 'SentimentAnalyzer',
    # Strategy
    'Strategy', 'StrategyConfig', 'StrategyEngine', 'STRATEGY_PROFILES',
    # AI (lazy)
    'AIEngine',
    # Tools (v51-100)
    'DataEncryptor', 'TokenCounter', 'ThreadManager', 'AuditLogger',
    'ABTestingEngine', 'AnomalyDetector', 'DataExporter', 'RulesEngine',
    'PersistentCache', 'ReplayEngine', 'DependencyTracker', 'AutoClassifier',
    'ResourceMonitor', 'AutoCorrector', 'TimeSeriesAnalyzer',
    'Watchdog', 'ErrorEscalator', 'PromptVersionManager', 'NGramDeduplicator',
    'SmartRouter', 'DataCompressor', 'QualityScorer', 'InjectionProtector',
    'ScenarioEngine', 'MetaEngine', 'SelfTester', 'ProfileManager',
    # Engine (lazy)
    'HermesEngine',
]
