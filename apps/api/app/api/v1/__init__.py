"""API v1 router aggregation."""

from fastapi import APIRouter, Depends

from app.core.auth_policy import allow_anonymous_user, require_authenticated_user

from app.api.v1 import (
    applications,
    assessments,
    auth,
    candidates,
    feedback,
    gdpr,
    interviews,
    jd_generation,
    job_matching,
    jobs,
    llm_gateway,
    offers,
    quantchat,
    resume_parsing,
)

public_router = APIRouter()
public_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

protected_router = APIRouter(dependencies=[Depends(require_authenticated_user)])
protected_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
protected_router.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
protected_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
protected_router.include_router(jd_generation.router, tags=["JD Generation"])
protected_router.include_router(job_matching.router, tags=["Job Matching"])
protected_router.include_router(quantchat.router, prefix="/quantchat", tags=["QuantChat"])
protected_router.include_router(
    resume_parsing.router, prefix="/resume-parsing", tags=["Resume Parsing"]
)
protected_router.include_router(llm_gateway.router, tags=["LLM Gateway"])
protected_router.include_router(feedback.router, tags=["Feedback"])
protected_router.include_router(assessments.router, prefix="/assessments", tags=["Assessments"])
protected_router.include_router(interviews.router, prefix="/interviews", tags=["Interviews"])
protected_router.include_router(offers.router, prefix="/offers", tags=["Offers"])
protected_router.include_router(gdpr.router, prefix="/gdpr", tags=["GDPR"])

router = APIRouter()
router.include_router(public_router)
router.include_router(protected_router)

__all__ = ["router", "public_router", "protected_router", "allow_anonymous_user"]
