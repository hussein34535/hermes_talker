"""
═════════════════════════════════════════════════════════════════════════════
  ai_engine.py - محرك AI المتقدم (بعد جراحة العقل - Phase 1)
═════════════════════════════════════════════════════════════════════════════
  التعديلات:
    - تغيير برومبت المدير من "جنرال حرب" لـ "CEO وكالة عمولات"
    - تغيير برومبت السكرتير ليستخرج أوامر تنفيذية بيزنس حقيقية
    - إضافة فلتر ينضف أي "هلوسة سيادية" قبل ما تدخل للموديل
"""

import asyncio
import re
import time

from google import genai

from hermes.config import log
from hermes.config import Config
from hermes.infrastructure import RateLimiter, CircuitBreaker, Metrics, async_retry
from hermes.memory import SmartMemory, LearningSystem, ModelHealthTracker, CostTracker, SentimentAnalyzer
from hermes.database import Database
from hermes.tools import (
    TokenCounter, InjectionProtector, AutoCorrector,
    QualityScorer, SmartRouter, NGramDeduplicator,
)


class AIEngine:
    """محرك AI المتقدم - المدير والسكرتير مع كل التحسينات"""

    def __init__(
        self,
        config: Config,
        rate_limiter: RateLimiter,
        circuits: dict,
        health_tracker: ModelHealthTracker,
        cost_tracker: CostTracker,
        metrics: Metrics,
        memory: SmartMemory,
        learning: LearningSystem,
        sentiment: SentimentAnalyzer,
        db: Database,
    ):
        self.config = config
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.rate_limiter = rate_limiter
        self.circuits = circuits
        self.health = health_tracker
        self.cost = cost_tracker
        self.metrics = metrics
        self.memory = memory
        self.learning = learning
        self.sentiment = sentiment
        self.db = db

        # المكونات الجديدة (v51-100)
        self.token_counter = TokenCounter()
        self.injection_protector = InjectionProtector()
        self.auto_corrector = AutoCorrector()
        self.quality_scorer = QualityScorer()
        self.smart_router = SmartRouter()
        self.ngram_dedup = NGramDeduplicator(config.NGRAM_DEDUP_SIZE)

    def _clean_hallucinations(self, text: str) -> str:
        """فلتر تنظيف أي هلوسة أو خيال علمي قبل إرساله للموديل"""
        hallucination_patterns = [
            r'SOVEREIGN.*?SILENCE', r'ABSOLUTE.*?AUTHORITY', r'PROFIT.*?ATTACK',
            r'SILENT.*?OBSERVER', r'WALL.*?DEFENSE', r'SYS-CORE-001',
            r'ETERNAL.*?OPERATION', r'ZERO.*?INTERVENTION', r'JOYSTICK.*?INTEGRATION',
            r'authenticate', r'sovereign_status', r'authority_level',
        ]
        cleaned = text
        for pattern in hallucination_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        # تنظيف المسافات الزائدة الناتجة عن الحذف
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @async_retry(max_retries=3, base_delay=2.0, jitter=True)
    async def _call_model(self, model, prompt, operation="general"):
        """استدعاء موديل AI مع كل طبقات الحماية"""
        # فحص الميزانية
        if not self.cost.can_afford:
            log.warning("الميزانية استنفدت")
            return None

        # 91. حماية من الحقن
        is_dangerous, reason = self.injection_protector.check(prompt)
        if is_dangerous:
            log.warning(f"محتوى خطير: {reason}")
            return None

        # معدّل السرعة
        await self.rate_limiter.acquire()

        # قاطع الدائرة
        circuit = self.circuits.get(model)
        if circuit and not await circuit.can_proceed():
            return None

        start = time.time()
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.client.models.generate_content(model=model, contents=prompt)
            )
            latency = time.time() - start
            result = response.text

            # تسجيل النجاح
            await self.health.record_success(model, latency)
            if circuit:
                await circuit.record_success()

            # تتبع التوكنز والتكلفة
            tokens = self.token_counter.estimate(prompt) + self.token_counter.estimate(result) if self.config.ENABLE_TOKEN_COUNTING else 0
            cost = self.config.COST_PER_MANAGER_CALL if 'manager' in operation else self.config.COST_PER_SECRETARY_CALL
            await self.cost.record_call(model, operation, cost, tokens)

            self.metrics.observe('model_latency', latency)

            # 90. تقييم الجودة
            if self.config.ENABLE_QUALITY_SCORING:
                qs = self.quality_scorer.score(prompt, result)
                self.metrics.gauge('last_quality_score', qs)

            log.info(f"✅ {model}: {latency:.1f}s ({len(result)} حرف, ~{tokens} توكن)")
            return result

        except Exception as e:
            latency = time.time() - start
            err = str(e)[:200]
            await self.health.record_failure(model, err)
            if circuit:
                await circuit.record_failure(err)
            self.metrics.increment('errors')
            raise

    async def manager_analyze(self, report):
        """تحليل المدير - استراتيجي وعميق (النسخة التجارية)"""
        self.metrics.increment('manager_calls')
        history = await self.memory.get_context_for_prompt(3000)
        enhancements = self.learning.get_prompt_enhancements()

        # 83. كشف تكرار
        if self.config.NGRAM_DEDUP_SIZE > 0 and self.ngram_dedup.is_duplicate(report):
            log.info("تقرير مكرر (N-gram) - تخطي التحليل الكامل")

        # تنظيف أي هلوسة متبقية في المدخلات
        clean_report = self._clean_hallucinations(report)
        clean_history = self._clean_hallucinations(history)

        prompt = f"""أنت هيرمس، CEO وكالة تسويق بالعمولة (Affiliate Marketing) المتخصصة في أدوات السوفت وير والذكاء الاصطناعي (SaaS & AI Tools).
هدفك الوحيد هو زيادة الإيرادات الشهرية المتكررة (MRR) من خلال استراتيجية الـ SEO العضوي المجاني.

قواعد صارمة:
1. لا تختلق معلومات أو أرقام. استخدم فقط البيانات المتاحة في التقرير.
2. قراراتك يجب أن تعتمد على (حجم البحث، صعوبة الكلمة، قيمة العمولة).
3. ممنوع استخدام مصطلحات عسكرية أو خيال علمي (مثل سيادة، هجوم، جدران دفاعية، أوامر عليا).
4. ردك يجب أن يكون خطوة تنفيذية واحدة محددة تتعلق بالبحث، الكتابة، أو النشر لمحتوى يجيب زيارات.

[الذاكرة السابقة]: {clean_history}
[التعلم]: {enhancements}
[التقرير الحالي]: {clean_report}

حلل التقرير بناءً على قواعد البيزنس، واعطني خطوة تنفيذية واحدة واضحة.
ابدأ ردك بـ "Hermes:" """

        start = time.time()
        result = await self._call_model(self.config.MANAGER_MODEL, prompt, "manager_analysis")
        if result:
            self.metrics.observe('manager_latency', time.time() - start)
            # 66. متوسط متحرك
            ma = self.metrics.moving_average('manager_latency', time.time() - start)
            self.metrics.gauge('manager_latency_ma', ma)
        return result

    async def secretary_extract(self, analysis):
        """استخلاص الأمر من السكرتير (النسخة التجارية)"""
        self.metrics.increment('secretary_calls')
        
        clean_analysis = self._clean_hallucinations(analysis)
        
        prompt = f"""أنت سكرتير تنفيذي. وظيفتك تحويل التحليل الاستراتيجي لأمر مباشر واضح لفريق التسويق.
الأمر يجب أن يبدأ بفعل (ابحث، اكتب، انشر، حلل) ويكون محدد جداً.
ممنوع الأوامر الغامضة أو الخيالية أو العسكرية.

التحليل: {clean_analysis}

استخرج الأمر التنفيذي فقط. ابدأ بـ "Hermes:" """

        # 73. اختيار موديل ذكي
        if self.config.ENABLE_SMART_MODEL_SELECT:
            model = self.smart_router.route('extraction', self.config.SECRETARY_MODELS)
        else:
            model = self.health.get_best_model(self.config.SECRETARY_MODELS)

        result = await self._call_model(model, prompt, "secretary_extract")
        if result:
            result = result.strip()
            if not result.startswith('Hermes:'):
                result = f"Hermes: {result}"
            # 74. تصحيح تلقائي
            if self.config.ENABLE_AUTO_CORRECTION:
                result, corrections = self.auto_corrector.correct(result)
                if corrections:
                    log.info(f"تصحيحات: {corrections}")
        return result
