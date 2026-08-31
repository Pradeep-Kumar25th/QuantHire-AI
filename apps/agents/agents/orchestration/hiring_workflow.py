"""LangGraph orchestration for complete hiring funnel workflow."""

import logging
from typing import Any, Dict, List, TypedDict

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import END, StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not installed. Workflow orchestration disabled.")


class HiringState(TypedDict):
    """State for hiring workflow."""
    job_id: str
    candidate_id: str
    job_spec: Dict[str, Any]
    candidate_profile: Dict[str, Any]
    screening_result: Dict[str, Any]
    assessment_result: Dict[str, Any]
    interview_result: Dict[str, Any]
    decision: Dict[str, Any]
    offer: Dict[str, Any]
    current_stage: str
    errors: List[str]


class HiringWorkflow:
    """
    Complete hiring funnel orchestration with LangGraph.
    
    Workflow stages:
    1. Job Specification (SpecAgent)
    2. Candidate Sourcing (SourcingAgent)
    3. Resume Parsing (ParsingAgent)
    4. Pre-Screening (ScreeningAgent)
    5. Matching & Ranking (MatchingAgent)
    6. Assessment (AssessmentAgent)
    7. Interview Scheduling (SchedulerAgent)
    8. Interview Analysis (InterviewAnalysisAgent)
    9. Decision (DecisionAgent)
    10. Offer Generation (OfferAgent)
    """
    
    def __init__(self):
        """Initialize workflow."""
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph required for workflow orchestration")
        
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile()
    
    def _build_graph(self) -> StateGraph:
        """Build the hiring workflow graph."""
        workflow = StateGraph(HiringState)
        
        # Define nodes
        workflow.add_node("parse_resume", self.parse_resume_node)
        workflow.add_node("screen_candidate", self.screen_candidate_node)
        workflow.add_node("match_candidate", self.match_candidate_node)
        workflow.add_node("assess_candidate", self.assess_candidate_node)
        workflow.add_node("schedule_interview", self.schedule_interview_node)
        workflow.add_node("analyze_interview", self.analyze_interview_node)
        workflow.add_node("make_decision", self.make_decision_node)
        workflow.add_node("generate_offer", self.generate_offer_node)
        
        # Define edges (workflow flow)
        workflow.set_entry_point("parse_resume")
        workflow.add_edge("parse_resume", "screen_candidate")
        workflow.add_conditional_edges(
            "screen_candidate",
            self.should_continue_after_screening,
            {
                "continue": "match_candidate",
                "reject": END,
            }
        )
        workflow.add_edge("match_candidate", "assess_candidate")
        workflow.add_conditional_edges(
            "assess_candidate",
            self.should_continue_after_assessment,
            {
                "continue": "schedule_interview",
                "reject": END,
            }
        )
        workflow.add_edge("schedule_interview", "analyze_interview")
        workflow.add_edge("analyze_interview", "make_decision")
        workflow.add_conditional_edges(
            "make_decision",
            self.should_make_offer,
            {
                "offer": "generate_offer",
                "reject": END,
            }
        )
        workflow.add_edge("generate_offer", END)
        
        return workflow
    
    async def parse_resume_node(self, state: HiringState) -> HiringState:
        """Parse resume with ParsingAgent."""
        from agents.parsing.agent import ParsingAgent
        
        logger.info(f"Parsing resume for candidate {state['candidate_id']}")
        
        agent = ParsingAgent()
        result = await agent.execute({
            "resume_text": state.get("resume_text", ""),
            "candidate_id": state["candidate_id"],
        })
        
        if result.success:
            state["candidate_profile"] = result.output
            state["current_stage"] = "parsed"
        else:
            state["errors"].append(f"Parsing failed: {result.error}")
        
        return state
    
    async def screen_candidate_node(self, state: HiringState) -> HiringState:
        """Screen candidate with ScreeningAgent."""
        from agents.screening.agent import ScreeningAgent
        
        logger.info(f"Screening candidate {state['candidate_id']}")
        
        agent = ScreeningAgent()
        result = await agent.execute({
            "screening_questions": state["job_spec"].get("screening_questions", []),
            "candidate_responses": state.get("screening_responses", {}),
            "job_spec": state["job_spec"],
        })
        
        if result.success:
            state["screening_result"] = result.output
            state["current_stage"] = "screened"
        else:
            state["errors"].append(f"Screening failed: {result.error}")
        
        return state
    
    async def match_candidate_node(self, state: HiringState) -> HiringState:
        """Match candidate with MatchingAgent."""
        from agents.matching.agent import MatchingAgent
        
        logger.info(f"Matching candidate {state['candidate_id']}")
        
        agent = MatchingAgent()
        result = await agent.execute({
            "job_spec": state["job_spec"],
            "candidates": [state["candidate_profile"]],
        })
        
        if result.success and result.output:
            state["match_score"] = result.output[0].get("score", 0)
            state["current_stage"] = "matched"
        
        return state
    
    async def assess_candidate_node(self, state: HiringState) -> HiringState:
        """Assess candidate with AssessmentAgent."""
        from agents.assessment.agent import AssessmentAgent
        
        logger.info(f"Assessing candidate {state['candidate_id']}")
        
        agent = AssessmentAgent()
        result = await agent.execute({
            "assessment_type": "coding",
            "submission": state.get("assessment_submission", {}),
            "rubric": state.get("assessment_rubric", {}),
        })
        
        if result.success:
            state["assessment_result"] = result.output
            state["current_stage"] = "assessed"
        
        return state
    
    async def schedule_interview_node(self, state: HiringState) -> HiringState:
        """Schedule interview with SchedulerAgent."""
        from agents.scheduler.agent import SchedulerAgent
        
        logger.info(f"Scheduling interview for candidate {state['candidate_id']}")
        
        agent = SchedulerAgent()
        result = await agent.execute({
            "candidate_id": state["candidate_id"],
            "job_id": state["job_id"],
            "interviewers": state.get("interviewers", []),
        })
        
        if result.success:
            state["interview_scheduled"] = result.output
            state["current_stage"] = "interview_scheduled"
        
        return state
    
    async def analyze_interview_node(self, state: HiringState) -> HiringState:
        """Analyze interview with InterviewAnalysisAgent."""
        from agents.interview_analysis.agent import InterviewAnalysisAgent
        
        logger.info(f"Analyzing interview for candidate {state['candidate_id']}")
        
        agent = InterviewAnalysisAgent()
        result = await agent.execute({
            "transcript": state.get("interview_transcript", ""),
            "interview_type": "technical",
            "job_spec": state["job_spec"],
        })
        
        if result.success:
            state["interview_result"] = result.output
            state["current_stage"] = "interviewed"
        
        return state
    
    async def make_decision_node(self, state: HiringState) -> HiringState:
        """Make hiring decision with DecisionAgent."""
        from agents.decision.agent import DecisionAgent
        
        logger.info(f"Making decision for candidate {state['candidate_id']}")
        
        agent = DecisionAgent()
        result = await agent.execute({
            "job_spec": state["job_spec"],
            "candidate": state["candidate_profile"],
            "screening": state.get("screening_result", {}),
            "assessment": state.get("assessment_result", {}),
            "interview": state.get("interview_result", {}),
        })
        
        if result.success:
            state["decision"] = result.output
            state["current_stage"] = "decision_made"
        
        return state
    
    async def generate_offer_node(self, state: HiringState) -> HiringState:
        """Generate offer with OfferAgent."""
        from agents.offer.agent import OfferAgent
        
        logger.info(f"Generating offer for candidate {state['candidate_id']}")
        
        agent = OfferAgent()
        result = await agent.execute({
            "candidate_id": state["candidate_id"],
            "job_spec": state["job_spec"],
            "decision": state["decision"],
        })
        
        if result.success:
            state["offer"] = result.output
            state["current_stage"] = "offer_generated"
        
        return state
    
    def should_continue_after_screening(self, state: HiringState) -> str:
        """Decide if candidate should continue after screening."""
        screening_result = state.get("screening_result", {})
        passed = screening_result.get("passed", False)
        
        return "continue" if passed else "reject"
    
    def should_continue_after_assessment(self, state: HiringState) -> str:
        """Decide if candidate should continue after assessment."""
        assessment_result = state.get("assessment_result", {})
        score = assessment_result.get("overall_score", 0)
        
        return "continue" if score >= 70 else "reject"
    
    def should_make_offer(self, state: HiringState) -> str:
        """Decide if offer should be generated."""
        decision = state.get("decision", {})
        recommendation = decision.get("recommendation", "no_hire")
        
        return "offer" if recommendation in ["hire", "strong_hire"] else "reject"
    
    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run complete hiring workflow.
        
        Args:
            initial_state: Initial workflow state
            
        Returns:
            Final state after workflow completion
        """
        logger.info("Starting hiring workflow")
        
        # Initialize state
        state = HiringState(
            job_id=initial_state.get("job_id", ""),
            candidate_id=initial_state.get("candidate_id", ""),
            job_spec=initial_state.get("job_spec", {}),
            candidate_profile={},
            screening_result={},
            assessment_result={},
            interview_result={},
            decision={},
            offer={},
            current_stage="started",
            errors=[],
        )
        
        # Update with additional initial data
        state.update(initial_state)
        
        # Run workflow
        final_state = await self.compiled_graph.ainvoke(state)
        
        logger.info(f"Workflow completed: stage={final_state.get('current_stage')}")
        
        return final_state


# Example usage
"""
from agents.orchestration.hiring_workflow import HiringWorkflow

workflow = HiringWorkflow()

result = await workflow.run({
    "job_id": "job_123",
    "candidate_id": "cand_456",
    "job_spec": {...},
    "resume_text": "...",
    "screening_responses": {...},
    "assessment_submission": {...},
    "interview_transcript": "...",
})

print(f"Final stage: {result['current_stage']}")
print(f"Decision: {result['decision']}")
if 'offer' in result:
    print(f"Offer: {result['offer']}")
"""












