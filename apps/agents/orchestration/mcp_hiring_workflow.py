"""
Enhanced Hiring Workflow with MCP Integration
Demonstrates LangGraph workflow using MCP servers
"""

import logging
from datetime import datetime, timedelta
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

from apps.agents.mcp.mcp_client import get_mcp_client

logger = logging.getLogger(__name__)


class MCPHiringState(TypedDict):
    """Hiring workflow state with MCP integration."""
    candidate_id: str
    job_id: str
    candidate_email: str
    interviewer_emails: List[str]
    interview_scheduled: bool
    calendar_event_id: str
    meeting_link: str
    current_stage: str
    errors: Annotated[List[str], lambda x, y: x + y]


class MCPHiringWorkflow:
    """
    Hiring workflow with MCP integration.
    
    Demonstrates how LangGraph workflows can use MCP servers.
    """
    
    def __init__(self):
        """Initialize workflow."""
        self.mcp_client = get_mcp_client()
        self.graph = self._build_graph()
        self.compiled = self.graph.compile()
    
    def _build_graph(self) -> StateGraph:
        """Build workflow graph with MCP integration."""
        workflow = StateGraph(MCPHiringState)
        
        # Add nodes
        workflow.add_node("get_emails", self._get_emails_node)
        workflow.add_node("find_meeting_times", self._find_meeting_times_node)
        workflow.add_node("create_calendar_event", self._create_calendar_event_node)
        workflow.add_node("send_notifications", self._send_notifications_node)
        
        # Define flow
        workflow.set_entry_point("get_emails")
        workflow.add_edge("get_emails", "find_meeting_times")
        workflow.add_conditional_edges(
            "find_meeting_times",
            self._should_create_event,
            {
                "create": "create_calendar_event",
                "no_slots": END,
            }
        )
        workflow.add_edge("create_calendar_event", "send_notifications")
        workflow.add_edge("send_notifications", END)
        
        return workflow
    
    async def _get_emails_node(self, state: MCPHiringState) -> MCPHiringState:
        """Get candidate and interviewer emails."""
        # TODO: Fetch from database
        state["candidate_email"] = f"candidate_{state['candidate_id']}@example.com"
        state["interviewer_emails"] = [
            f"interviewer_{i}@example.com"
            for i in range(2)
        ]
        state["current_stage"] = "emails_collected"
        return state
    
    async def _find_meeting_times_node(self, state: MCPHiringState) -> MCPHiringState:
        """Find meeting times using Calendar MCP Server."""
        try:
            result = await self.mcp_client.call_tool(
                server_name="calendar-server",
                tool_name="find_meeting_times",
                arguments={
                    "attendee_emails": [state["candidate_email"]] + state["interviewer_emails"],
                    "duration_minutes": 60,
                    "start_date": (datetime.now() + timedelta(days=1)).isoformat(),
                    "end_date": (datetime.now() + timedelta(days=14)).isoformat(),
                    "timezone": "UTC",
                }
            )
            
            meeting_times = result.get("meeting_times", [])
            state["meeting_times"] = meeting_times
            state["current_stage"] = "meeting_times_found"
            
            if meeting_times:
                state["selected_slot"] = meeting_times[0]
            
        except Exception as e:
            logger.error(f"Error finding meeting times: {e}")
            state["errors"].append(f"Failed to find meeting times: {str(e)}")
            state["meeting_times"] = []
        
        return state
    
    async def _create_calendar_event_node(self, state: MCPHiringState) -> MCPHiringState:
        """Create calendar event using Calendar MCP Server."""
        try:
            selected_slot = state.get("selected_slot")
            if not selected_slot:
                state["errors"].append("No slot selected for event creation")
                return state
            
            result = await self.mcp_client.call_tool(
                server_name="calendar-server",
                tool_name="create_calendar_event",
                arguments={
                    "subject": f"Interview - Candidate {state['candidate_id']}",
                    "start_time": selected_slot["start"],
                    "end_time": selected_slot["end"],
                    "attendee_emails": [state["candidate_email"]] + state["interviewer_emails"],
                    "body_content": f"Interview for job {state['job_id']}",
                    "is_online_meeting": True,
                }
            )
            
            state["interview_scheduled"] = True
            state["calendar_event_id"] = result.get("event_id")
            state["meeting_link"] = result.get("meeting_link")
            state["current_stage"] = "event_created"
            
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            state["errors"].append(f"Failed to create event: {str(e)}")
        
        return state
    
    async def _send_notifications_node(self, state: MCPHiringState) -> MCPHiringState:
        """Send notifications (placeholder for future MCP server)."""
        # TODO: Use Notification MCP Server when available
        logger.info(f"Sending notifications for event {state.get('calendar_event_id')}")
        state["current_stage"] = "notifications_sent"
        return state
    
    def _should_create_event(self, state: MCPHiringState) -> str:
        """Decide if event should be created."""
        if state.get("meeting_times"):
            return "create"
        return "no_slots"
    
    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run workflow.
        
        Args:
            initial_state: Initial workflow state
            
        Returns:
            Final state
        """
        # Initialize state
        state = MCPHiringState(
            candidate_id=initial_state.get("candidate_id", ""),
            job_id=initial_state.get("job_id", ""),
            candidate_email="",
            interviewer_emails=[],
            interview_scheduled=False,
            calendar_event_id="",
            meeting_link="",
            current_stage="started",
            errors=[],
        )
        
        # Run workflow
        final_state = await self.compiled.ainvoke(state)
        return final_state


# Example usage
"""
from apps.agents.orchestration.mcp_hiring_workflow import MCPHiringWorkflow

workflow = MCPHiringWorkflow()

result = await workflow.run({
    "candidate_id": "cand_123",
    "job_id": "job_456",
})

print(f"Interview scheduled: {result['interview_scheduled']}")
print(f"Event ID: {result['calendar_event_id']}")
print(f"Meeting link: {result['meeting_link']}")
"""
