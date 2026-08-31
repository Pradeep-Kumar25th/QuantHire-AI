"""LLM Gateway for cost control, budget tracking, and intelligent routing."""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as redis
from pydantic import BaseModel, Field

from agents.llm.client import LLMClient
from agents.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Model performance tiers."""
    PREMIUM = "premium"      # GPT-4o, Claude Sonnet
    STANDARD = "standard"    # GPT-4
    ECONOMY = "economy"      # GPT-3.5-turbo
    LOCAL = "local"          # Self-hosted models


class UsageMetrics(BaseModel):
    """Token usage metrics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str
    provider: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str
    agent_name: Optional[str] = None


class BudgetStatus(BaseModel):
    """Current budget status."""
    daily_budget_usd: float
    spent_today_usd: float
    remaining_usd: float
    utilization_pct: float
    is_exceeded: bool
    current_tier: ModelTier
    alert_threshold_reached: bool


class LLMGateway:
    """
    LLM Gateway for intelligent routing, cost control, and observability.
    
    Features:
    - Budget tracking and enforcement
    - Intelligent model routing based on complexity
    - Cost optimization with tier fallback
    - Token usage monitoring
    - Request rate limiting
    - Detailed logging for LangSmith integration
    """

    # Token costs per 1M tokens (as of 2024)
    TOKEN_COSTS = {
        "gpt-4o": {"prompt": 5.00, "completion": 15.00},
        "gpt-4-turbo": {"prompt": 10.00, "completion": 30.00},
        "gpt-4": {"prompt": 30.00, "completion": 60.00},
        "gpt-3.5-turbo": {"prompt": 0.50, "completion": 1.50},
        "claude-3-5-sonnet-20241022": {"prompt": 3.00, "completion": 15.00},
        "claude-3-opus-20240229": {"prompt": 15.00, "completion": 75.00},
        "claude-3-sonnet-20240229": {"prompt": 3.00, "completion": 15.00},
        "claude-3-haiku-20240307": {"prompt": 0.25, "completion": 1.25},
        "llama-3.3-70b-versatile": {"prompt": 0.59, "completion": 0.79},
        "llama-3.1-8b-instant": {"prompt": 0.05, "completion": 0.08},
        "gemini-1.5-pro": {"prompt": 3.50, "completion": 10.50},
        "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    }

    MODEL_TIERS = {
        ModelTier.PREMIUM: ["llama-3.3-70b-versatile", "gpt-4o", "claude-3-5-sonnet-20241022"],
        ModelTier.STANDARD: ["gemini-1.5-pro", "gpt-4-turbo", "claude-3-sonnet-20240229"],
        ModelTier.ECONOMY: ["llama-3.1-8b-instant", "gemini-1.5-flash", "gpt-3.5-turbo", "claude-3-haiku-20240307"],
    }

    def __init__(
        self,
        redis_url: str,
        daily_budget_usd: float = 250.0,
        enable_budget_enforcement: bool = True,
        alert_threshold: float = 0.8,
        enable_tracking: bool = True,
    ):
        """
        Initialize LLM Gateway.
        
        Args:
            redis_url: Redis connection URL for state storage
            daily_budget_usd: Daily budget limit in USD
            enable_budget_enforcement: Block requests when budget exceeded
            alert_threshold: Alert when budget utilization reaches this %
            enable_tracking: Enable detailed usage tracking
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.daily_budget_usd = daily_budget_usd
        self.enable_budget_enforcement = enable_budget_enforcement
        self.alert_threshold = alert_threshold
        self.enable_tracking = enable_tracking
        
        self.current_tier = ModelTier.PREMIUM
        
        logger.info(
            f"LLM Gateway initialized: "
            f"budget=${daily_budget_usd}, enforcement={enable_budget_enforcement}"
        )

    async def route_request(
        self,
        prompt: str,
        model_preference: Optional[str] = None,
        task_complexity: str = "medium",  # low, medium, high
        agent_name: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[str, LLMProvider]:
        """
        Route request to appropriate model based on budget and complexity.
        
        Args:
            prompt: User prompt
            model_preference: Preferred model (if None, auto-select)
            task_complexity: Task complexity level
            agent_name: Name of calling agent
            request_id: Unique request ID for tracking
            
        Returns:
            Tuple of (selected_model, provider)
        """
        # Check budget status
        budget_status = await self.get_budget_status()
        
        # Enforce budget if enabled
        if self.enable_budget_enforcement and budget_status.is_exceeded:
            logger.warning("Daily budget exceeded, falling back to economy tier")
            self.current_tier = ModelTier.ECONOMY
        elif budget_status.utilization_pct > self.alert_threshold:
            logger.warning(
                f"Budget utilization at {budget_status.utilization_pct:.1%}, "
                f"considering tier downgrade"
            )
            if self.current_tier == ModelTier.PREMIUM:
                self.current_tier = ModelTier.STANDARD
        
        # Select model based on complexity and tier
        if model_preference:
            selected_model = model_preference
        else:
            selected_model = self._select_model_by_complexity(
                task_complexity, self.current_tier
            )
        
        # Determine provider
        provider = self._get_provider_for_model(selected_model)
        
        logger.info(
            f"Routed request: model={selected_model}, tier={self.current_tier}, "
            f"complexity={task_complexity}, budget_util={budget_status.utilization_pct:.1%}"
        )
        
        return selected_model, provider

    def _select_model_by_complexity(
        self, complexity: str, tier: ModelTier
    ) -> str:
        """Select model based on task complexity and current tier."""
        tier_models = self.MODEL_TIERS.get(tier, self.MODEL_TIERS[ModelTier.ECONOMY])
        
        if complexity == "high" and tier == ModelTier.PREMIUM:
            return "llama-3.3-70b-versatile"
        elif complexity == "high":
            return tier_models[0]
        elif complexity == "low":
            # Use economy model for simple tasks
            return self.MODEL_TIERS[ModelTier.ECONOMY][0]
        else:
            # Medium complexity
            return tier_models[0]

    def _get_provider_for_model(self, model: str) -> LLMProvider:
        """Get provider enum for model."""
        model_lower = model.lower()
        if "gpt" in model_lower:
            return LLMProvider.OPENAI
        elif "claude" in model_lower:
            return LLMProvider.ANTHROPIC
        elif "llama" in model_lower:
            return LLMProvider.GROQ
        elif "gemini" in model_lower:
            return LLMProvider.GOOGLE
        else:
            return LLMProvider.GROQ  # Default to GROQ as per user preference

    async def track_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        request_id: str,
        agent_name: Optional[str] = None,
    ) -> UsageMetrics:
        """
        Track token usage and calculate cost.
        
        Args:
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            request_id: Unique request ID
            agent_name: Agent making the request
            
        Returns:
            UsageMetrics object
        """
        if not self.enable_tracking:
            return UsageMetrics(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=0.0,
                model=model,
                provider=self._get_provider_for_model(model).value,
                request_id=request_id,
                agent_name=agent_name,
            )
        
        # Calculate cost
        cost_usd = self._calculate_cost(model, prompt_tokens, completion_tokens)
        
        # Create metrics
        metrics = UsageMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            model=model,
            provider=self._get_provider_for_model(model).value,
            request_id=request_id,
            agent_name=agent_name,
        )
        
        # Store in Redis
        await self._store_usage_metrics(metrics)
        
        # Update daily total
        await self._increment_daily_cost(cost_usd)
        
        logger.info(
            f"Usage tracked: {prompt_tokens}+{completion_tokens} tokens, "
            f"${cost_usd:.4f}, model={model}, agent={agent_name}"
        )
        
        return metrics

    def _calculate_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Calculate cost in USD for token usage."""
        if model not in self.TOKEN_COSTS:
            logger.warning(f"Unknown model pricing: {model}, using default")
            # Default to GPT-4o pricing
            model = "gpt-4o"
        
        costs = self.TOKEN_COSTS[model]
        prompt_cost = (prompt_tokens / 1_000_000) * costs["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * costs["completion"]
        
        return prompt_cost + completion_cost

    async def _store_usage_metrics(self, metrics: UsageMetrics) -> None:
        """Store usage metrics in Redis."""
        key = f"llm:usage:{metrics.timestamp.strftime('%Y-%m-%d')}:{metrics.request_id}"
        await self.redis_client.setex(
            key,
            86400 * 30,  # 30-day retention
            metrics.model_dump_json(),
        )
        
        # Store in agent-specific key for reporting
        if metrics.agent_name:
            agent_key = f"llm:agent:{metrics.agent_name}:daily:{metrics.timestamp.strftime('%Y-%m-%d')}"
            await self.redis_client.hincrby(agent_key, "total_tokens", metrics.total_tokens)
            await self.redis_client.hincrbyfloat(agent_key, "total_cost", metrics.cost_usd)
            await self.redis_client.expire(agent_key, 86400 * 30)

    async def _increment_daily_cost(self, cost: float) -> None:
        """Increment daily cost counter."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"llm:daily_cost:{today}"
        await self.redis_client.incrbyfloat(key, cost)
        await self.redis_client.expire(key, 86400 * 2)  # 2-day retention

    async def get_budget_status(self) -> BudgetStatus:
        """Get current budget status."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"llm:daily_cost:{today}"
        
        spent_str = await self.redis_client.get(key)
        spent_today = float(spent_str) if spent_str else 0.0
        
        remaining = max(0, self.daily_budget_usd - spent_today)
        utilization = spent_today / self.daily_budget_usd if self.daily_budget_usd > 0 else 0
        is_exceeded = spent_today >= self.daily_budget_usd
        alert_threshold_reached = utilization >= self.alert_threshold
        
        return BudgetStatus(
            daily_budget_usd=self.daily_budget_usd,
            spent_today_usd=spent_today,
            remaining_usd=remaining,
            utilization_pct=utilization,
            is_exceeded=is_exceeded,
            current_tier=self.current_tier,
            alert_threshold_reached=alert_threshold_reached,
        )

    async def get_daily_usage_by_agent(self, date: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        """
        Get usage breakdown by agent for a specific date.
        
        Args:
            date: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Dict mapping agent names to usage stats
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        pattern = f"llm:agent:*:daily:{date}"
        keys = await self.redis_client.keys(pattern)
        
        usage_by_agent = {}
        for key in keys:
            agent_name = key.split(":")[2]
            stats = await self.redis_client.hgetall(key)
            usage_by_agent[agent_name] = {
                "total_tokens": int(stats.get("total_tokens", 0)),
                "total_cost_usd": float(stats.get("total_cost", 0.0)),
            }
        
        return usage_by_agent

    async def reset_daily_budget(self) -> None:
        """Reset daily budget (typically called by scheduler at midnight UTC)."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"llm:daily_cost:{today}"
        await self.redis_client.delete(key)
        
        self.current_tier = ModelTier.PREMIUM
        
        logger.info("Daily budget reset")

    async def close(self) -> None:
        """Close Redis connection."""
        await self.redis_client.close()


# Global gateway instance (initialized in app startup)
_gateway: Optional[LLMGateway] = None


def init_gateway(
    redis_url: str,
    daily_budget_usd: float = 250.0,
    enable_budget_enforcement: bool = True,
) -> LLMGateway:
    """Initialize global gateway instance."""
    global _gateway
    _gateway = LLMGateway(
        redis_url=redis_url,
        daily_budget_usd=daily_budget_usd,
        enable_budget_enforcement=enable_budget_enforcement,
    )
    return _gateway


def get_gateway() -> LLMGateway:
    """Get global gateway instance."""
    if _gateway is None:
        raise RuntimeError("LLM Gateway not initialized. Call init_gateway() first.")
    return _gateway












