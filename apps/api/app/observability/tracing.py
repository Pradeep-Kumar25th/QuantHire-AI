"""OpenTelemetry distributed tracing configuration."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# OpenTelemetry imports (optional dependency)
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not installed. Distributed tracing disabled.")


def init_tracing(app, service_name: str = "quanthire-api") -> None:
    """
    Initialize OpenTelemetry tracing for FastAPI application.
    
    Args:
        app: FastAPI application instance
        service_name: Service name for traces
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, skipping tracing setup")
        return
    
    enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    if not enabled:
        logger.info("OpenTelemetry tracing disabled (OTEL_ENABLED=false)")
        return
    
    try:
        # Create resource with service name
        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.getenv("APP_VERSION", "1.0.0"),
            "deployment.environment": os.getenv("APP_ENV", "development"),
        })
        
        # Create tracer provider
        provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        
        # Add span processor
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # Instrument HTTP clients
        HTTPXClientInstrumentor().instrument()
        
        # Instrument database
        SQLAlchemyInstrumentor().instrument()
        
        # Instrument Redis
        RedisInstrumentor().instrument()
        
        # Instrument logging
        LoggingInstrumentor().instrument(set_logging_format=True)
        
        logger.info(f"OpenTelemetry tracing initialized for {service_name}")
        logger.info(f"Exporting to: {otlp_endpoint}")
    
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")


def get_tracer(name: str = __name__):
    """Get tracer for manual instrumentation."""
    if not OTEL_AVAILABLE:
        # Return no-op tracer
        return None
    
    return trace.get_tracer(name)


def create_span(name: str, attributes: Optional[dict] = None):
    """
    Create a new span for manual instrumentation.
    
    Usage:
        with create_span("parse_resume", {"candidate_id": "123"}):
            # Your code here
            pass
    """
    if not OTEL_AVAILABLE:
        # Return context manager that does nothing
        from contextlib import nullcontext
        return nullcontext()
    
    tracer = get_tracer()
    if tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    
    return tracer.start_as_current_span(name, attributes=attributes or {})


# Example usage in agent code
"""
from app.observability.tracing import create_span

async def execute_agent(input_data):
    with create_span("agent_execution", {
        "agent.name": "ParsingAgent",
        "agent.version": "1.0.0",
        "candidate.id": input_data.get("candidate_id")
    }):
        # Agent execution code
        result = await parse_resume(input_data)
        
        # Add custom attributes
        span = trace.get_current_span()
        span.set_attribute("agent.confidence", result.confidence)
        span.set_attribute("agent.cost_usd", result.cost_usd)
        
        return result
"""


SETUP_INSTRUCTIONS = """
OpenTelemetry Setup
===================

1. Install Dependencies:
   pip install opentelemetry-api opentelemetry-sdk
   pip install opentelemetry-instrumentation-fastapi
   pip install opentelemetry-instrumentation-httpx
   pip install opentelemetry-instrumentation-sqlalchemy
   pip install opentelemetry-instrumentation-redis
   pip install opentelemetry-exporter-otlp

2. Deploy OpenTelemetry Collector (Optional):
   # Using Kubernetes
   kubectl apply -f https://github.com/open-telemetry/opentelemetry-operator/releases/latest/download/opentelemetry-operator.yaml

3. Configure Environment:
   export OTEL_ENABLED=true
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
   export OTEL_SERVICE_NAME=quanthire-api
   export OTEL_TRACES_SAMPLER=parentbased_traceidratio
   export OTEL_TRACES_SAMPLER_ARG=0.1  # Sample 10% of traces

4. Backend Options:
   a) Jaeger (open source):
      docker run -d --name jaeger \\
        -p 16686:16686 -p 4318:4318 \\
        jaegertracing/all-in-one:latest
      
   b) Azure Monitor (managed):
      export APPLICATIONINSIGHTS_CONNECTION_STRING="your_connection_string"
      
   c) Grafana Tempo (open source):
      # Deploy with Helm
      helm install tempo grafana/tempo

5. Verify Tracing:
   - Make API request
   - Check traces in backend UI:
     * Jaeger: http://localhost:16686
     * Azure Monitor: Azure Portal > Application Insights
     * Grafana Tempo: Grafana > Explore > Tempo

Benefits:
- ✅ End-to-end request tracing
- ✅ Service dependency mapping
- ✅ Latency bottleneck identification
- ✅ Error correlation across services
- ✅ Performance optimization insights

Documentation: https://opentelemetry.io/docs/
"""


def print_setup_instructions():
    """Print OpenTelemetry setup instructions."""
    print(SETUP_INSTRUCTIONS)












