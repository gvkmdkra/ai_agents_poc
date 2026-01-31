"""
Observability Layer

Implements:
- OpenTelemetry tracing
- Prometheus metrics
- Conversation analytics
- Performance dashboards
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

# OpenTelemetry imports
try:
    from opentelemetry import trace, metrics
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# METRICS DEFINITIONS
# ============================================================================


@dataclass
class CallMetrics:
    """Metrics for a single call"""
    call_id: UUID
    tenant_id: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None

    # Timing
    ring_duration_ms: int = 0
    answer_latency_ms: int = 0
    total_duration_ms: int = 0

    # AI Performance
    ai_response_times_ms: list = field(default_factory=list)
    avg_ai_latency_ms: float = 0
    max_ai_latency_ms: float = 0

    # Conversation
    total_turns: int = 0
    user_speaking_time_ms: int = 0
    ai_speaking_time_ms: int = 0
    silence_time_ms: int = 0

    # Quality
    ai_confidence_scores: list = field(default_factory=list)
    sentiment_scores: list = field(default_factory=list)
    escalated: bool = False
    outcome: str = ""

    # Costs
    llm_tokens_used: int = 0
    asr_seconds: float = 0
    tts_characters: int = 0
    telephony_minutes: float = 0
    total_cost_usd: float = 0


class MetricsCollector:
    """
    Collects and exposes metrics for the voice agent system.

    Integrates with:
    - OpenTelemetry for distributed tracing
    - Prometheus for metrics collection
    - CloudWatch for AWS monitoring
    """

    def __init__(
        self,
        service_name: str = "voice-agent",
        otlp_endpoint: Optional[str] = None,
    ):
        self.service_name = service_name
        self._active_calls: dict[UUID, CallMetrics] = {}
        self._metrics_buffer: list[CallMetrics] = []

        # Initialize OpenTelemetry if available
        if OTEL_AVAILABLE and otlp_endpoint:
            self._init_otel(otlp_endpoint)
        else:
            self.tracer = None
            self.meter = None

        # In-memory counters for quick access
        self._counters = {
            "calls_total": 0,
            "calls_success": 0,
            "calls_failed": 0,
            "calls_escalated": 0,
            "leads_created": 0,
            "leads_qualified_hot": 0,
            "leads_qualified_warm": 0,
            "leads_qualified_cold": 0,
            "appointments_scheduled": 0,
            "ai_timeouts": 0,
            "circuit_breaker_opens": 0,
        }

        # Histograms
        self._histograms = {
            "call_duration_seconds": [],
            "ai_latency_ms": [],
            "lead_score": [],
        }

    def _init_otel(self, otlp_endpoint: str):
        """Initialize OpenTelemetry"""
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": "1.0.0",
        })

        # Tracing
        tracer_provider = TracerProvider(resource=resource)
        span_processor = BatchSpanProcessor(
            OTLPSpanExporter(endpoint=otlp_endpoint)
        )
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)
        self.tracer = trace.get_tracer(self.service_name)

        # Metrics
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=otlp_endpoint),
            export_interval_millis=60000,
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(meter_provider)
        self.meter = metrics.get_meter(self.service_name)

        logger.info(f"OpenTelemetry initialized with endpoint: {otlp_endpoint}")

    # =========================================================================
    # TRACING
    # =========================================================================

    @asynccontextmanager
    async def trace_call(self, call_id: UUID, tenant_id: UUID):
        """Context manager for tracing a call"""
        call_metrics = CallMetrics(
            call_id=call_id,
            tenant_id=tenant_id,
            started_at=datetime.now(),
        )
        self._active_calls[call_id] = call_metrics
        self._counters["calls_total"] += 1

        if self.tracer:
            with self.tracer.start_as_current_span(
                "voice_call",
                attributes={
                    "call.id": str(call_id),
                    "tenant.id": str(tenant_id),
                },
            ) as span:
                try:
                    yield call_metrics
                    span.set_status(Status(StatusCode.OK))
                    self._counters["calls_success"] += 1
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    self._counters["calls_failed"] += 1
                    raise
                finally:
                    call_metrics.ended_at = datetime.now()
                    self._finalize_call_metrics(call_metrics)
        else:
            try:
                yield call_metrics
                self._counters["calls_success"] += 1
            except Exception:
                self._counters["calls_failed"] += 1
                raise
            finally:
                call_metrics.ended_at = datetime.now()
                self._finalize_call_metrics(call_metrics)

    @asynccontextmanager
    async def trace_ai_turn(self, call_id: UUID, turn_number: int):
        """Trace an AI conversation turn"""
        start_time = time.time()

        if self.tracer:
            with self.tracer.start_as_current_span(
                "ai_turn",
                attributes={
                    "call.id": str(call_id),
                    "turn.number": turn_number,
                },
            ) as span:
                try:
                    yield
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    latency_ms = (time.time() - start_time) * 1000
                    if call_id in self._active_calls:
                        self._active_calls[call_id].ai_response_times_ms.append(latency_ms)
                    self._histograms["ai_latency_ms"].append(latency_ms)
        else:
            try:
                yield
            finally:
                latency_ms = (time.time() - start_time) * 1000
                if call_id in self._active_calls:
                    self._active_calls[call_id].ai_response_times_ms.append(latency_ms)
                self._histograms["ai_latency_ms"].append(latency_ms)

    def _finalize_call_metrics(self, call_metrics: CallMetrics):
        """Finalize and store call metrics"""
        if call_metrics.ended_at and call_metrics.started_at:
            duration = (call_metrics.ended_at - call_metrics.started_at).total_seconds()
            call_metrics.total_duration_ms = int(duration * 1000)
            self._histograms["call_duration_seconds"].append(duration)

        if call_metrics.ai_response_times_ms:
            call_metrics.avg_ai_latency_ms = sum(call_metrics.ai_response_times_ms) / len(call_metrics.ai_response_times_ms)
            call_metrics.max_ai_latency_ms = max(call_metrics.ai_response_times_ms)

        if call_metrics.escalated:
            self._counters["calls_escalated"] += 1

        # Move to buffer and remove from active
        self._metrics_buffer.append(call_metrics)
        self._active_calls.pop(call_metrics.call_id, None)

        # Keep buffer size manageable
        if len(self._metrics_buffer) > 10000:
            self._metrics_buffer = self._metrics_buffer[-5000:]

    # =========================================================================
    # COUNTER METHODS
    # =========================================================================

    def increment(self, metric: str, value: int = 1, labels: Optional[dict] = None):
        """Increment a counter metric"""
        if metric in self._counters:
            self._counters[metric] += value

        # Also record to OpenTelemetry if available
        if self.meter:
            counter = self.meter.create_counter(
                name=f"voice_agent.{metric}",
                description=f"Counter for {metric}",
            )
            counter.add(value, labels or {})

    def record_histogram(self, metric: str, value: float, labels: Optional[dict] = None):
        """Record a histogram value"""
        if metric in self._histograms:
            self._histograms[metric].append(value)

        if self.meter:
            histogram = self.meter.create_histogram(
                name=f"voice_agent.{metric}",
                description=f"Histogram for {metric}",
            )
            histogram.record(value, labels or {})

    def record_ai_latency(self, latency_ms: float, model: str = "default"):
        """Record AI response latency"""
        self.record_histogram("ai_latency_ms", latency_ms, {"model": model})

        # Track timeouts
        if latency_ms > 3000:
            self._counters["ai_timeouts"] += 1

    def record_lead_score(self, score: float, temperature: str):
        """Record lead qualification score"""
        self._histograms["lead_score"].append(score)

        if temperature == "hot":
            self._counters["leads_qualified_hot"] += 1
        elif temperature == "warm":
            self._counters["leads_qualified_warm"] += 1
        else:
            self._counters["leads_qualified_cold"] += 1

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict:
        """Get current statistics"""
        stats = {
            "counters": dict(self._counters),
            "active_calls": len(self._active_calls),
            "buffered_metrics": len(self._metrics_buffer),
        }

        # Calculate histogram percentiles
        for name, values in self._histograms.items():
            if values:
                sorted_values = sorted(values)
                n = len(sorted_values)
                stats[f"{name}_p50"] = sorted_values[int(n * 0.5)]
                stats[f"{name}_p95"] = sorted_values[int(n * 0.95)]
                stats[f"{name}_p99"] = sorted_values[int(n * 0.99)]
                stats[f"{name}_avg"] = sum(values) / n
                stats[f"{name}_count"] = n

        return stats

    def get_tenant_stats(self, tenant_id: UUID, hours: int = 24) -> dict:
        """Get statistics for a specific tenant"""
        cutoff = datetime.now() - timedelta(hours=hours)

        tenant_calls = [
            m for m in self._metrics_buffer
            if m.tenant_id == tenant_id and m.started_at >= cutoff
        ]

        if not tenant_calls:
            return {"tenant_id": str(tenant_id), "calls": 0}

        return {
            "tenant_id": str(tenant_id),
            "period_hours": hours,
            "calls": len(tenant_calls),
            "avg_duration_seconds": sum(m.total_duration_ms for m in tenant_calls) / len(tenant_calls) / 1000,
            "avg_ai_latency_ms": sum(m.avg_ai_latency_ms for m in tenant_calls) / len(tenant_calls),
            "escalation_rate": sum(1 for m in tenant_calls if m.escalated) / len(tenant_calls),
            "total_cost_usd": sum(m.total_cost_usd for m in tenant_calls),
        }

    def get_dashboard_data(self) -> dict:
        """Get data for dashboard display"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)

        recent_hour = [m for m in self._metrics_buffer if m.started_at >= hour_ago]
        recent_day = [m for m in self._metrics_buffer if m.started_at >= day_ago]

        return {
            "current": {
                "active_calls": len(self._active_calls),
                "calls_last_hour": len(recent_hour),
                "calls_last_24h": len(recent_day),
            },
            "performance": {
                "ai_latency_p95_ms": self._get_percentile("ai_latency_ms", 0.95),
                "call_duration_avg_seconds": self._get_average("call_duration_seconds"),
            },
            "quality": {
                "escalation_rate_24h": (
                    sum(1 for m in recent_day if m.escalated) / len(recent_day)
                    if recent_day else 0
                ),
                "success_rate": (
                    self._counters["calls_success"] /
                    max(1, self._counters["calls_total"])
                ),
            },
            "leads": {
                "total_created": self._counters["leads_created"],
                "hot": self._counters["leads_qualified_hot"],
                "warm": self._counters["leads_qualified_warm"],
                "cold": self._counters["leads_qualified_cold"],
            },
            "reliability": {
                "ai_timeouts": self._counters["ai_timeouts"],
                "circuit_breaker_opens": self._counters["circuit_breaker_opens"],
            },
        }

    def _get_percentile(self, metric: str, percentile: float) -> float:
        """Get percentile value for a histogram"""
        values = self._histograms.get(metric, [])
        if not values:
            return 0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _get_average(self, metric: str) -> float:
        """Get average value for a histogram"""
        values = self._histograms.get(metric, [])
        return sum(values) / len(values) if values else 0


# ============================================================================
# CONVERSATION ANALYTICS
# ============================================================================


class ConversationAnalytics:
    """
    Analytics specifically for conversation quality and outcomes.
    """

    def __init__(self, db_pool):
        self.db = db_pool

    async def get_conversion_funnel(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Get lead conversion funnel data"""
        async with self.db.acquire() as conn:
            result = await conn.fetch(
                """
                SELECT
                    lead_temperature,
                    status,
                    COUNT(*) as count
                FROM voice_leads
                WHERE tenant_id = $1
                  AND created_at BETWEEN $2 AND $3
                GROUP BY lead_temperature, status
                ORDER BY lead_temperature, status
                """,
                tenant_id,
                start_date,
                end_date,
            )

            funnel = {
                "hot": {"total": 0, "converted": 0},
                "warm": {"total": 0, "converted": 0},
                "cold": {"total": 0, "converted": 0},
            }

            for row in result:
                temp = row["lead_temperature"]
                if temp in funnel:
                    funnel[temp]["total"] += row["count"]
                    if row["status"] in ("won", "meeting_scheduled"):
                        funnel[temp]["converted"] += row["count"]

            # Calculate conversion rates
            for temp in funnel:
                total = funnel[temp]["total"]
                funnel[temp]["conversion_rate"] = (
                    funnel[temp]["converted"] / total if total > 0 else 0
                )

            return funnel

    async def get_ai_performance_metrics(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Get AI performance metrics"""
        async with self.db.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_calls,
                    AVG(conversation_turns) as avg_turns,
                    AVG(duration_seconds) as avg_duration,
                    SUM(CASE WHEN escalated_to_human THEN 1 ELSE 0 END) as escalated_count,
                    AVG(sentiment_score) as avg_sentiment,
                    SUM(total_cost_usd) as total_cost
                FROM voice_calls
                WHERE tenant_id = $1
                  AND started_at BETWEEN $2 AND $3
                  AND status = 'completed'
                """,
                tenant_id,
                start_date,
                end_date,
            )

            return {
                "total_calls": result["total_calls"] or 0,
                "avg_conversation_turns": float(result["avg_turns"] or 0),
                "avg_call_duration_seconds": float(result["avg_duration"] or 0),
                "escalation_rate": (
                    (result["escalated_count"] or 0) / max(1, result["total_calls"] or 1)
                ),
                "avg_sentiment_score": float(result["avg_sentiment"] or 0),
                "total_cost_usd": float(result["total_cost"] or 0),
            }


# ============================================================================
# GLOBAL METRICS INSTANCE
# ============================================================================

_metrics_collector: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get or create the global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def init_metrics(service_name: str, otlp_endpoint: Optional[str] = None):
    """Initialize the global metrics collector"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(
        service_name=service_name,
        otlp_endpoint=otlp_endpoint,
    )
    return _metrics_collector
