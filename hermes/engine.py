"""
═════════════════════════════════════════════════════════════════════════════
  engine.py - المحرك الرئيسي (المايسترو)
═════════════════════════════════════════════════════════════════════════════
  هذا هو الملف الذي يجمع كل المكونات ويشغّلها ككيان واحد.
  يحتوي على:
    - HermesEngine: المحرك الرئيسي - 100 تحسين مدمج
      * تهيئة كل المكونات
      * الاستماع للرسائل من تليجرام
      * معالجة الرسائل (تحليل → أوامر)
      * المهام الدورية
      * أوامر البوت
      * الإغلاق النظيف
"""

import asyncio
import random
import signal
import time
import traceback

from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError, ChatWriteForbiddenError,
    SessionPasswordNeededError, AuthKeyError,
)

from hermes.config import log, Config, EngineState, StateMachine
from hermes.database import Database
from hermes.infrastructure import RateLimiter, CircuitBreaker, Metrics
from hermes.alerts import AlertManager
from hermes.memory import (
    SmartMemory, ModelHealthTracker, SentimentAnalyzer,
    LearningSystem, BackupSystem, MessageQueue, CostTracker,
)
from hermes.strategy import StrategyEngine
from hermes.ai_engine import AIEngine
from hermes.tools import (
    DataEncryptor, TokenCounter, ThreadManager, AuditLogger,
    ABTestingEngine, AnomalyDetector, DataExporter, RulesEngine,
    PersistentCache, ReplayEngine, DependencyTracker, AutoClassifier,
    ResourceMonitor, TimeSeriesAnalyzer, Watchdog, ErrorEscalator,
    PromptVersionManager, TUIDashboard, ProfileManager,
    SelfTester, ScenarioEngine, MetaEngine,
)
from hermes.servers import start_http_monitor


class HermesEngine:
    """المحرك الرئيسي - 100 تحسين مدمج - المايسترو الذي يجمع كل شيء"""

    def __init__(self, config=None):
        self.config = config or Config.from_env()

        # === المكونات الأساسية (v1-50) ===
        self.state = StateMachine()
        self.db = Database(self.config.DB_PATH)
        self.metrics = Metrics()
        self.alerts = AlertManager()
        self.rate_limiter = RateLimiter(self.config.API_CALLS_PER_MINUTE, self.config.API_CALLS_PER_DAY)
        self.memory = SmartMemory(self.db, self.config)
        self.health_tracker = ModelHealthTracker(self.db)
        self.sentiment = SentimentAnalyzer()
        self.learning = LearningSystem(self.db)
        self.backup = BackupSystem(self.db, self.config)
        self.msg_queue = MessageQueue()

        # قواطع الدائرة لكل موديل
        all_models = [self.config.MANAGER_MODEL] + self.config.SECRETARY_MODELS
        self.circuits = {
            m: CircuitBreaker(m, self.config.CIRCUIT_FAILURE_THRESHOLD, self.config.CIRCUIT_RESET_TIMEOUT)
            for m in all_models
        }

        self.cost_tracker = CostTracker(self.db, self.config, self.metrics, self.alerts)
        self.strategy = StrategyEngine(self.db, self.metrics, self.alerts)
        self.ai = AIEngine(
            self.config, self.rate_limiter, self.circuits,
            self.health_tracker, self.cost_tracker, self.metrics,
            self.memory, self.learning, self.sentiment, self.db,
        )

        # === المكونات الجديدة (v51-100) ===
        self.encryptor = DataEncryptor(self.config.AES_ENCRYPTION_KEY)          # 52
        self.thread_mgr = ThreadManager()                                        # 54
        self.audit_logger = AuditLogger(self.db)                                 # 56
        self.ab_testing = ABTestingEngine(self.db)                                # 58
        self.anomaly_detector = AnomalyDetector(self.db, self.config)            # 59
        self.data_exporter = DataExporter(self.db)                                # 60
        self.rules_engine = RulesEngine(self.db, self.alerts)                     # 62
        self.persistent_cache = PersistentCache(self.config.PERSISTENT_CACHE_PATH)# 63
        self.replay_engine = ReplayEngine(self.db)                                # 64
        self.dep_tracker = DependencyTracker(self.db)                             # 65
        self.auto_classifier = AutoClassifier()                                   # 69
        self.resource_monitor = ResourceMonitor(self.db)                          # 71
        self.time_series = TimeSeriesAnalyzer(self.db)                            # 76
        self.watchdog = Watchdog(self.config.WATCHDOG_TIMEOUT)                    # 78
        self.error_escalator = ErrorEscalator(self.config.ERROR_ESCALATION_LEVELS)# 79
        self.prompt_versions = PromptVersionManager(self.db, self.config.PROMPT_VERSIONS_DIR)  # 81
        self.tui = TUIDashboard(self)                                             # 94
        self.profile_mgr = ProfileManager(self.db, self.config.PROFILES_DIR)      # 95
        self.self_tester = SelfTester(self.db)                                    # 98
        self.scenario_engine = ScenarioEngine(self.db)                            # 99
        self.meta_engine = MetaEngine(self.db, self.metrics, self.alerts, self.config)  # 100

        # === حالة التشغيل ===
        self.tg_client = None
        self._collected_messages = []
        self._last_msg_time = 0
        self._collecting = False
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """تهيئة كل المكونات والاتصال بتليجرام"""
        self.state.transition(EngineState.CONNECTING)
        log.info("=" * 60)
        log.info("🔥🔥 محرك هرمس v100.0 - بدء التهيئة 🔥🔥")
        log.info("=" * 60)

        # تهيئة قاعدة البيانات
        await self.db.initialize()

        # تهيئة الذاكرة والتعلم
        await self.memory.initialize()
        all_models = [self.config.MANAGER_MODEL] + self.config.SECRETARY_MODELS
        await self.health_tracker.initialize(all_models)
        await self.learning.initialize()

        # سجل المراجعة
        await self.audit_logger.log("engine_start", details="v100.0 initialization")

        # تهيئة الأنظمة الاختيارية
        if self.config.ENABLE_RULES_ENGINE:
            await self.rules_engine.initialize()
        if self.config.ENABLE_AB_TESTING:
            await self.ab_testing.initialize()

        # الاتصال بتليجرام
        self.tg_client = TelegramClient(
            self.config.SESSION_NAME,
            self.config.API_ID,
            self.config.API_HASH
        )
        await self.tg_client.start()
        log.info("✅ تم الاتصال بتليجرام")

        # معالجات الإشارات
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except:
                pass

        self.state.transition(EngineState.IDLE)
        log.info("✅ التهيئة مكتملة - 100 تحسين جاهز")
        await self._print_status()

    async def _print_status(self):
        """طباعة حالة النظام"""
        log.info("─" * 50)
        log.info(f"📊 الاستراتيجية: {self.strategy.current_strategy.value}")
        log.info(f"💰 الميزانية: ${self.cost_tracker.budget_remaining:.4f}")
        log.info(f"📡 API (دقيقة): {self.rate_limiter.minute_remaining} | (يوم): {self.rate_limiter.day_remaining}")
        log.info(self.health_tracker.health_report())
        log.info("─" * 50)

    async def send_message(self, text, priority=5):
        """إرسال رسالة لتليجرام مع كل طبقات الحماية"""
        if not self.strategy.can_send_command():
            log.warning("تجاوز الحد اليومي")
            return False

        # 22. تقييم المخاطر
        if self.config.ENABLE_RISK_ASSESSMENT:
            rs, rd = await self.strategy.assess_risk(text)
            if rs > 0.5:
                log.warning(f"⚠️ مخاطرة ({rs:.2f}): {rd}")

        try:
            # 11. تأخير عشوائي لمحاكاة السلوك البشري
            if self.config.TYPING_SIMULATION:
                await asyncio.sleep(
                    random.uniform(self.config.MIN_DELAY_BETWEEN_MESSAGES, self.config.MAX_DELAY_BETWEEN_MESSAGES)
                )

            await self.tg_client.send_message(self.config.HERMES_USERNAME, text)
            self.strategy.record_command()
            self.metrics.increment('commands_sent')

            await self.db.execute(
                "INSERT INTO messages (direction,content,model_used,tokens_used) VALUES ('outgoing',?,'hermes',?)",
                (text[:500], self.ai.token_counter.estimate(text))
            )

            # 56. سجل المراجعة
            if self.config.ENABLE_AUDIT_LOG:
                await self.audit_logger.log("command_sent", target=self.config.HERMES_USERNAME, details=text[:200])

            # 61. إشعار المشغل
            if self.config.ENABLE_OPERATOR_NOTIFICATIONS and self.config.OPERATOR_CHAT_ID:
                try:
                    await self.tg_client.send_message(self.config.OPERATOR_CHAT_ID, f"📤 أمر مرسل: {text[:100]}")
                except:
                    pass

            self.state.transition(EngineState.WAITING_RESPONSE)
            log.info(f"📤 تم الإرسال: {text[:80]}...")
            return True

        except FloodWaitError as e:
            log.warning(f"⏳ فيضان: {e.seconds}s")
            await asyncio.sleep(e.seconds + 5)
            return await self.send_message(text, priority)

        except Exception as e:
            # 79. تصعيد الخطأ
            level = self.error_escalator.classify(str(type(e).__name__))
            await self.alerts.fire(level, "send_error", str(e)[:100])
            self.metrics.increment('errors')
            return False

    async def process_collected_messages(self):
        """معالجة الرسائل المجمعة: تحليل → أوامر"""
        if not self._collected_messages:
            return

        self.state.transition(EngineState.PROCESSING)
        full_report = "\n".join(self._collected_messages)
        self._collected_messages.clear()
        log.info(f"📦 معالجة تقرير ({len(full_report)} حرف)...")
        self.watchdog.heartbeat()  # 78

        # متغيرات افتراضية للسياق
        sent = {'overall': 0, 'label': 'neutral'}
        cat = 'general'
        conf = 0.0

        try:
            # 15. تحليل المشاعر
            if self.config.ENABLE_SENTIMENT_ANALYSIS:
                sent = self.sentiment.analyze(full_report)
                self.metrics.gauge('last_sentiment', sent['overall'])
                log.info(f"🎭 مشاعر: {sent['label']} ({sent['overall']:.2f})")

            # 69. تصنيف تلقائي
            if self.config.ENABLE_AUTO_CLASSIFY:
                cat, conf = self.auto_classifier.classify(full_report)
                log.info(f"📂 تصنيف: {cat} (ثقة: {conf:.0%})")
                # 54. تعيين موضوع
                if self.config.ENABLE_MULTI_THREAD:
                    thread_id = self.thread_mgr.get_or_create(cat)
                    self.thread_mgr.update_activity(thread_id)

            # 33. اكتشاف الفرص
            if self.config.ENABLE_OPPORTUNITY_SCORING:
                opps = await self.strategy.detect_opportunities(full_report)
                if opps:
                    log.info(f"🌟 {len(opps)} فرصة مكتشفة")

            # 62. محرك القواعد
            if self.config.ENABLE_RULES_ENGINE:
                ctx = {
                    'sentiment': sent.get('overall', 0),
                    'category': cat,
                    'message_count': len(self._collected_messages) + 1,
                }
                rule_actions = await self.rules_engine.evaluate(ctx)
                if rule_actions:
                    log.info(f"⚡ {len(rule_actions)} قاعدة نُفذت")

            # === التحليل بالـ AI ===
            self.state.transition(EngineState.ANALYZING)
            analysis = await self.ai.manager_analyze(full_report)
            if not analysis:
                log.error("❌ فشل تحليل المدير")
                self.state.transition(EngineState.IDLE)
                return

            await self.memory.add(
                f"تقرير: {full_report[:150]}...\nتحليل: {analysis[:300]}...",
                category="analysis", importance=0.7
            )

            if self.config.ENABLE_LEARNING:
                await self.learning.record_outcome(full_report[:100], "analysis_complete", 0.8)

            # === استخلاص الأمر ===
            self.state.transition(EngineState.DISPATCHING)
            command = await self.ai.secretary_extract(analysis)
            if command:
                sent_ok = await self.send_message(command)
                if sent_ok:
                    log.info(f"🚀 أمر: {command[:100]}")
                    await self.memory.add(f"أمر: {command[:200]}", category="command", importance=0.8)
                    # 76. تسجيل سلسلة زمنية
                    if self.config.ENABLE_TIME_SERIES:
                        await self.time_series.record('commands_per_cycle', 1)
                else:
                    await self.msg_queue.enqueue(command, 3)

            # 8. تعديل الاستراتيجية تلقائياً
            await self.strategy.adapt_strategy()

            # 17. نسخ احتياطي
            if self.config.ENABLE_AUTO_BACKUP:
                await self.backup.backup_if_needed()

            # 59. كشف شذوذ
            if self.config.ANOMALY_THRESHOLD > 0:
                latency_vals = [v for v in self.metrics._histograms.get('manager_latency', [])][-50:]
                if latency_vals:
                    self.anomaly_detector.update_baseline('manager_latency', latency_vals)
                    last_lat = latency_vals[-1] if latency_vals else 0
                    is_anom, dev = self.anomaly_detector.is_anomaly('manager_latency', last_lat)
                    if is_anom:
                        log.warning(f"🚨 شذوذ في زمن الاستجابة! deviation={dev:.1f}")
                        await self.anomaly_detector.record_anomaly(
                            'manager_latency',
                            self.anomaly_detector._baselines.get('manager_latency', (0, 0))[0],
                            last_lat, dev
                        )

            self.state.transition(EngineState.IDLE)

        except Exception as e:
            log.error(f"❌ خطأ: {e}")
            self.metrics.increment('errors')
            self.state.transition(EngineState.ERROR_RECOVERY)
            await asyncio.sleep(10)
            self.state.transition(EngineState.IDLE)

    async def start_listening(self):
        """بدء الاستماع لرسائل تليجرام"""

        @self.tg_client.on(events.NewMessage(chats=self.config.HERMES_USERNAME))
        async def handler(event):
            self.metrics.increment('messages_received')
            self._collected_messages.append(event.text)
            self._last_msg_time = time.time()
            self.watchdog.heartbeat()

            # 69. تصنيف وحفظ
            cat, conf = self.auto_classifier.classify(event.text) if self.config.ENABLE_AUTO_CLASSIFY else ('general', 0)
            await self.db.execute(
                "INSERT INTO messages (direction,content,sentiment_score) VALUES ('incoming',?,?)",
                (event.text[:500], self.sentiment.analyze(event.text)['overall'] if self.config.ENABLE_SENTIMENT_ANALYSIS else 0)
            )
            log.info(f"📩 رسالة من هرمس ({len(self._collected_messages)}) [{cat}]")

            if not self._collecting:
                self._collecting = True
                self.state.transition(EngineState.COLLECTING)
                asyncio.create_task(self._wait_and_process())

        # 51. أوامر البوت
        if self.config.ENABLE_BOT_COMMANDS:
            @self.tg_client.on(events.NewMessage(outgoing=True, pattern=r'^/(\w+)'))
            async def command_handler(event):
                cmd = event.pattern_match.group(1)
                if cmd == 'status':
                    await event.reply(self.tui.render())
                elif cmd == 'stats':
                    await event.reply(self.metrics.summary())
                elif cmd == 'health':
                    await event.reply(self.health_tracker.health_report())
                elif cmd == 'strategy':
                    sc = self.strategy.config
                    await event.reply(f"🎯 {self.strategy.current_strategy.value}\n{sc.description}\nأوامر/يوم: {sc.max_daily_commands}")
                elif cmd == 'cost':
                    await event.reply(f"💰 تكلفة اليوم: ${self.cost_tracker._daily:.4f}\nالمتبقي: ${self.cost_tracker.budget_remaining:.4f}")
                elif cmd == 'memory':
                    recent = await self.memory.get_recent(5)
                    msg = "\n".join(f"- {m['content'][:80]}" for m in recent)
                    await event.reply(f"📚 آخر 5 سجلات:\n{msg}")
                elif cmd == 'reset':
                    self._collected_messages.clear()
                    self._collecting = False
                    self.state.force_state(EngineState.IDLE)
                    await event.reply("🔄 تم إعادة التعيين")
                elif cmd == 'export':
                    await self.data_exporter.export_stats_json('export_stats.json')
                    await event.reply("📁 تم التصدير")
                elif cmd == 'help':
                    await event.reply("أوامر: /status /stats /health /strategy /cost /memory /reset /export /help")

        log.info(f"📡 الاستماع لـ {self.config.HERMES_USERNAME} 24/7")

    async def _wait_and_process(self):
        """الانتظار حتى انتهاء تدفق الرسائل ثم المعالجة"""
        timeout = self.config.MESSAGE_COLLECT_TIMEOUT
        while True:
            await asyncio.sleep(timeout)
            if time.time() - self._last_msg_time >= timeout:
                break
        self._collecting = False
        await self.process_collected_messages()

    async def send_initial_prompt(self):
        """إرسال أمر البدء الأولي"""
        cmd = "Hermes: مراجعة الحالة والبدء فوراً في تنفيذ أولى خطوات البحث عن فرص الربح."
        await self.send_message(cmd, 1)

    async def periodic_tasks(self):
        """مهام دورية شاملة - قلب النظام النابض"""
        cycle = 0
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60)
                cycle += 1
                self.watchdog.heartbeat()

                # كل دقيقة: فحص طابور
                if self.msg_queue.pending_count > 0:
                    msg = await self.msg_queue.dequeue()
                    if msg:
                        sent = await self.send_message(msg.content, msg.priority)
                        if sent:
                            await self.msg_queue.mark_sent(msg)
                        else:
                            await self.msg_queue.mark_failed(msg)

                # كل 5 دقائق: تقرير
                if cycle % 5 == 0:
                    log.info(f"📊 [{self.state.state.name}] {self.metrics.summary()}")

                # كل 15 دقيقة: مراقبة موارد
                if self.config.ENABLE_RESOURCE_MONITOR and cycle % 15 == 0:
                    res = await self.resource_monitor.snapshot()
                    log.info(f"💻 CPU: {res['cpu_percent']:.1f}% | RAM: {res['memory_mb']:.0f}MB | Threads: {res['active_threads']}")

                # كل 30 دقيقة: سلسلة زمنية
                if self.config.ENABLE_TIME_SERIES and cycle % 30 == 0:
                    await self.time_series.record('error_rate', self.metrics.get_counter('errors'))
                    await self.time_series.record('cost_rate', self.metrics.get_counter('total_cost'))

                # كل ساعة: Meta-Engine
                if self.config.ENABLE_META_ENGINE and cycle % 60 == 0:
                    await self.meta_engine.review_and_optimize()

                # كل ساعة: اختبارات ذاتية
                if self.config.ENABLE_SCENARIO_ENGINE and cycle % 60 == 0:
                    results = await self.self_tester.run_all()
                    await self.self_tester.save_results(results)

                # تلخيص تنبيهات
                if cycle % (self.config.ALERT_SUMMARY_INTERVAL // 60) == 0:
                    summary = await self.alerts.get_summary()
                    if summary != "لا توجد تنبيهات جديدة":
                        log.info(f"📋 ملخص تنبيهات: {summary}")

                # نسخ احتياطي
                if self.config.ENABLE_AUTO_BACKUP and cycle % (self.config.BACKUP_INTERVAL_HOURS * 60) == 0:
                    await self.backup.backup_if_needed()

            except Exception as e:
                log.error(f"خطأ دوري: {e}")
                await asyncio.sleep(30)

    async def shutdown(self):
        """إغلاق نظيف مع حفظ الحالة"""
        log.info("🛑 إيقاف النظام...")
        self.state.transition(EngineState.SHUTTING_DOWN)
        self._shutdown_event.set()

        try:
            if self._collected_messages:
                combined = "\n".join(self._collected_messages)
                await self.memory.add(f"رسائل معلقة: {combined[:300]}", "shutdown", 0.9)
            await self.audit_logger.log("engine_shutdown", details="graceful shutdown")
            if self.tg_client:
                await self.tg_client.disconnect()
            await self.db.close()
            log.info("✅ إغلاق نظيف")
        except Exception as e:
            log.error(f"خطأ إغلاق: {e}")

        self.state.transition(EngineState.OFFLINE)

    async def run(self):
        """تشغيل المحرك الرئيسي - نقطة الدخول"""
        try:
            await self.initialize()
            await self.start_listening()

            # 77. خادم HTTP للمراقبة
            if self.config.ENABLE_HTTP_MONITOR:
                start_http_monitor(self, self.config.HTTP_MONITOR_PORT)

            await self.send_initial_prompt()
            periodic_task = asyncio.create_task(self.periodic_tasks())

            log.info("\n" + "🔥" * 30 + "\n  HERMES v100.0 يعمل 24/7\n" + "🔥" * 30 + "\n")
            await self.tg_client.run_until_disconnected()

        except SessionPasswordNeededError:
            log.critical("🔐 حماية ثنائية مطلوبة")
        except AuthKeyError:
            log.critical("🔑 مفتاح غير صالح")
        except KeyboardInterrupt:
            log.info("⌨️ إيقاف يدوي")
        except Exception as e:
            log.critical(f"💥 خطأ حرج: {e}")
            log.critical(traceback.format_exc())
        finally:
            await self.shutdown()
