"""Resume parsing tasks."""

import sys
sys.path.insert(0, "/agents")
sys.path.insert(0, "/api")

from worker.celery_app import app
from agents.parsing.agent import ParsingAgent


@app.task(bind=True, max_retries=3)
def parse_resume_task(self, candidate_id: str, resume_text: str):
    """Parse resume asynchronously.
    
    Args:
        candidate_id: Candidate ID
        resume_text: Resume text content
        
    Returns:
        dict: Parsed resume data
    """
    try:
        # Initialize agent
        agent = ParsingAgent()
        
        # Parse resume
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            agent.execute({"resume_text": resume_text})
        )
        
        if not result.success:
            raise ValueError(result.error)
        
        # TODO: Update database with parsed data
        # This would use SQLAlchemy to update the candidate record
        
        return {
            "candidate_id": candidate_id,
            "status": "completed",
            "data": result.output,
            "confidence": result.confidence,
        }
    
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@app.task
def batch_parse_resumes(candidate_ids: list, resume_texts: list):
    """Batch parse multiple resumes.
    
    Args:
        candidate_ids: List of candidate IDs
        resume_texts: List of resume texts
        
    Returns:
        list: Results for each parse
    """
    from celery import group
    
    # Create group of parallel tasks
    job = group(
        parse_resume_task.s(cid, text)
        for cid, text in zip(candidate_ids, resume_texts)
    )
    
    result = job.apply_async()
    return {"job_id": result.id, "total": len(candidate_ids)}

