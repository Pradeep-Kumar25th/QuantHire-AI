"""MLflow integration for agent model tracking and versioning."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# MLflow imports (optional dependency)
try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not installed. Model tracking disabled.")


class MLflowTracker:
    """
    Track agent models and experiments with MLflow.
    
    Features:
    - Model versioning
    - Experiment tracking
    - Parameter logging
    - Metric logging
    - Artifact storage
    """
    
    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        experiment_name: str = "quanthire-agents",
        enabled: bool = True,
    ):
        """
        Initialize MLflow tracker.
        
        Args:
            tracking_uri: MLflow tracking server URI
            experiment_name: Experiment name
            enabled: Whether tracking is enabled
        """
        self.tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        self.experiment_name = experiment_name
        self.enabled = enabled and MLFLOW_AVAILABLE
        
        if self.enabled:
            mlflow.set_tracking_uri(self.tracking_uri)
            
            # Create or get experiment
            try:
                self.experiment = mlflow.set_experiment(experiment_name)
                logger.info(f"MLflow tracking enabled: {self.tracking_uri}")
            except Exception as e:
                logger.warning(f"Failed to initialize MLflow: {e}")
                self.enabled = False
        else:
            logger.info("MLflow tracking disabled")
    
    def start_run(
        self,
        run_name: str,
        agent_name: str,
        model_version: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Optional[Any]:
        """
        Start a new MLflow run.
        
        Args:
            run_name: Human-readable run name
            agent_name: Agent name
            model_version: Model version
            tags: Additional tags
            
        Returns:
            MLflow run object or None if disabled
        """
        if not self.enabled:
            return None
        
        run_tags = {
            "agent_name": agent_name,
            "model_version": model_version,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if tags:
            run_tags.update(tags)
        
        try:
            run = mlflow.start_run(run_name=run_name, tags=run_tags)
            logger.info(f"MLflow run started: {run.info.run_id}")
            return run
        except Exception as e:
            logger.error(f"Failed to start MLflow run: {e}")
            return None
    
    def log_params(self, params: Dict[str, Any]) -> None:
        """Log parameters to current run."""
        if not self.enabled:
            return
        
        try:
            mlflow.log_params(params)
        except Exception as e:
            logger.error(f"Failed to log params: {e}")
    
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """Log metrics to current run."""
        if not self.enabled:
            return
        
        try:
            for key, value in metrics.items():
                mlflow.log_metric(key, value, step=step)
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")
    
    def log_artifact(self, artifact_path: str, artifact_name: Optional[str] = None) -> None:
        """Log artifact (file) to current run."""
        if not self.enabled:
            return
        
        try:
            mlflow.log_artifact(artifact_path, artifact_name)
        except Exception as e:
            logger.error(f"Failed to log artifact: {e}")
    
    def log_model(
        self,
        model: Any,
        artifact_path: str,
        registered_model_name: Optional[str] = None,
    ) -> None:
        """
        Log model to MLflow.
        
        Args:
            model: Model object
            artifact_path: Path within run artifacts
            registered_model_name: Name for model registry
        """
        if not self.enabled:
            return
        
        try:
            mlflow.sklearn.log_model(
                model,
                artifact_path,
                registered_model_name=registered_model_name
            )
            logger.info(f"Model logged: {artifact_path}")
        except Exception as e:
            logger.error(f"Failed to log model: {e}")
    
    def end_run(self, status: str = "FINISHED") -> None:
        """End current MLflow run."""
        if not self.enabled:
            return
        
        try:
            mlflow.end_run(status=status)
            logger.info("MLflow run ended")
        except Exception as e:
            logger.error(f"Failed to end run: {e}")
    
    async def track_agent_execution(
        self,
        agent_name: str,
        model_version: str,
        input_data: Dict,
        output_data: Dict,
        confidence: float,
        execution_time_ms: float,
        cost_usd: float,
    ) -> None:
        """
        Track complete agent execution.
        
        Args:
            agent_name: Name of agent
            model_version: Model/prompt version
            input_data: Input parameters
            output_data: Output results
            confidence: Confidence score
            execution_time_ms: Execution time in milliseconds
            cost_usd: LLM cost in USD
        """
        if not self.enabled:
            return
        
        run_name = f"{agent_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        with mlflow.start_run(run_name=run_name):
            # Log parameters
            mlflow.log_params({
                "agent_name": agent_name,
                "model_version": model_version,
                "input_size": len(str(input_data)),
            })
            
            # Log metrics
            mlflow.log_metrics({
                "confidence": confidence,
                "execution_time_ms": execution_time_ms,
                "cost_usd": cost_usd,
            })
            
            # Log artifacts (if needed)
            # Save input/output as JSON
            import json
            import tempfile
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({
                    "input": input_data,
                    "output": output_data,
                }, f, indent=2)
                artifact_path = f.name
            
            mlflow.log_artifact(artifact_path, "execution_data")
            
            # Clean up temp file
            os.unlink(artifact_path)
    
    def register_model(
        self,
        model_name: str,
        model_version: str,
        description: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Register model in MLflow Model Registry.
        
        Args:
            model_name: Model name
            model_version: Version string
            description: Model description
            tags: Additional tags
        """
        if not self.enabled:
            return
        
        try:
            client = MlflowClient()
            
            # Register model version
            model_version_obj = client.create_model_version(
                name=model_name,
                source=f"runs:/{mlflow.active_run().info.run_id}/model",
                description=description,
                tags=tags or {},
            )
            
            logger.info(f"Model registered: {model_name} v{model_version}")
            return model_version_obj
        except Exception as e:
            logger.error(f"Failed to register model: {e}")


# Global tracker instance
_tracker: Optional[MLflowTracker] = None


def init_mlflow_tracker(
    tracking_uri: Optional[str] = None,
    experiment_name: str = "quanthire-agents",
) -> MLflowTracker:
    """Initialize global MLflow tracker."""
    global _tracker
    _tracker = MLflowTracker(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        enabled=os.getenv("ENABLE_MLFLOW", "false").lower() == "true",
    )
    return _tracker


def get_mlflow_tracker() -> MLflowTracker:
    """Get global MLflow tracker."""
    if _tracker is None:
        return init_mlflow_tracker()
    return _tracker












