"""
═════════════════════════════════════════════════════════════════════════════
  database.py - طبقة قاعدة البيانات SQLite
═════════════════════════════════════════════════════════════════════════════
  يحتوي على:
    - Database: إدارة SQLite مع 16 جدول و7 فهارس
    - تنفيذ آمن مع أقفال async
    - عمليات CRUD مركزية
"""

import asyncio
import sqlite3

from hermes.config import log


class Database:
    """قاعدة بيانات SQLite مع 16 جدول - طبقة البيانات المركزية"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        """إنشاء/الاتصال بقاعدة البيانات مع كل الجداول والفهارس"""
        def _init():
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    content TEXT NOT NULL,
                    summary TEXT,
                    importance REAL DEFAULT 0.5,
                    hash TEXT,
                    thread_id TEXT DEFAULT 'default',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    direction TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model_used TEXT,
                    response_time REAL,
                    sentiment_score REAL,
                    thread_id TEXT DEFAULT 'default',
                    quality_score REAL DEFAULT 0,
                    tokens_used INTEGER DEFAULT 0,
                    is_compressed INTEGER DEFAULT 0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS model_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    success INTEGER DEFAULT 0,
                    failure INTEGER DEFAULT 0,
                    avg_latency REAL DEFAULT 0,
                    last_used TEXT,
                    last_error TEXT,
                    task_type TEXT DEFAULT 'general'
                );
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    tags TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT NOT NULL,
                    score REAL DEFAULT 0,
                    risk_level TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'detected',
                    source_report TEXT,
                    profit_potential REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS cost_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    tokens_used INTEGER DEFAULT 0,
                    cost REAL DEFAULT 0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS learning (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    success_score REAL DEFAULT 0,
                    occurrence_count INTEGER DEFAULT 1,
                    last_seen TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    actor TEXT DEFAULT 'system',
                    target TEXT,
                    details TEXT,
                    severity TEXT DEFAULT 'info',
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    action TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    enabled INTEGER DEFAULT 1,
                    last_triggered TEXT,
                    trigger_count INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS command_chains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    result TEXT,
                    status TEXT DEFAULT 'pending',
                    dependency TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    ab_group TEXT DEFAULT 'A',
                    success_rate REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS anomaly_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    expected_value REAL,
                    actual_value REAL,
                    deviation REAL,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS resource_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cpu_percent REAL DEFAULT 0,
                    memory_mb REAL DEFAULT 0,
                    disk_mb REAL DEFAULT 0,
                    active_threads INTEGER DEFAULT 0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    steps TEXT NOT NULL,
                    status TEXT DEFAULT 'idle',
                    current_step INTEGER DEFAULT 0,
                    result TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS self_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    result TEXT NOT NULL,
                    details TEXT,
                    duration REAL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    config_json TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS time_series (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    period TEXT DEFAULT 'hourly',
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_memory_ts ON memory(timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);
                CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
                CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_anomaly_ts ON anomaly_log(detected_at);
                CREATE INDEX IF NOT EXISTS idx_resource_ts ON resource_usage(timestamp);
                CREATE INDEX IF NOT EXISTS idx_timeseries ON time_series(metric_name, timestamp);
            """)
            conn.commit()
            return conn

        self._conn = await asyncio.get_event_loop().run_in_executor(None, _init)
        log.info("تم إنشاء/الاتصال بقاعدة البيانات v2 بنجاح")

    async def execute(self, query, params=()):
        """تنفيذ استعلام مع حفظ تلقائي"""
        async with self._lock:
            def _e():
                try:
                    c = self._conn.execute(query, params)
                    self._conn.commit()
                    return c
                except sqlite3.Error as e:
                    log.error(f"DB Error: {e}")
                    raise
            return await asyncio.get_event_loop().run_in_executor(None, _e)

    async def fetchone(self, query, params=()):
        """جلب صف واحد"""
        async with self._lock:
            def _f():
                try:
                    return self._conn.execute(query, params).fetchone()
                except:
                    return None
            return await asyncio.get_event_loop().run_in_executor(None, _f)

    async def fetchall(self, query, params=()):
        """جلب كل الصفوف"""
        async with self._lock:
            def _f():
                try:
                    return self._conn.execute(query, params).fetchall()
                except:
                    return []
            return await asyncio.get_event_loop().run_in_executor(None, _f)

    async def close(self):
        """إغلاق الاتصال"""
        if self._conn:
            self._conn.close()
            log.info("تم إغلاق قاعدة البيانات")
