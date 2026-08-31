"""
Health Check Endpoint
====================
Simple endpoint to verify backend is running and accessible.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status and timestamp
    """
    return {
        "status": "healthy",
        "service": "QuantHireAI API",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/v1/health")
async def health_check_v1():
    """
    Health check endpoint for v1 API.
    
    Returns:
        dict: Health status and timestamp
    """
    return {
        "status": "healthy",
        "service": "QuantHireAI API v1",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "endpoints": {
            "jd_generation": "/api/v1/jd-generation/generate",
            "quantchat": "/api/v1/quantchat/chat",
            "resume_parsing": "/api/v1/resume-parsing/upload",
        }
    }

