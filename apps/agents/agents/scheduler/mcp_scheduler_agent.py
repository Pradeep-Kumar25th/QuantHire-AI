"""
Scheduler Agent with MCP Integration
Uses Calendar MCP Server for calendar operations
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult
from apps.agents.mcp.mcp_client import get_mcp_client


class MCPSchedulerAgent(BaseAgent):
    """
    Scheduler Agent that uses Calendar MCP Server.
    
    This agent demonstrates how to integrate MCP with agents.
    It uses the Calendar MCP Server for all calendar operations.
    """
    
    def __init__(self):
        """Initialize MCP-enabled scheduler agent."""
        config = AgentConfig(
            name="MCPSchedulerAgent",
            description="Schedules interviews using Calendar MCP Server",
            temperature=0.3,
        )
        super().__init__(config)
        self.mcp_client = get_mcp_client()
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Schedule interview using Calendar MCP Server.
        
        Args:
            input_data: Dictionary with:
                - candidate_email: Candidate email
                - interviewer_emails: List of interviewer emails
                - duration_minutes: Interview duration
                - start_date: Start date for search (ISO format)
                - end_date: End date for search (ISO format)
                - interview_type: Type of interview
                
        Returns:
            AgentResult with scheduled interview details
        """
        candidate_email = input_data.get("candidate_email")
        interviewer_emails = input_data.get("interviewer_emails", [])
        duration_minutes = input_data.get("duration_minutes", 60)
        start_date = input_data.get("start_date")
        end_date = input_data.get("end_date")
        interview_type = input_data.get("interview_type", "technical")
        
        try:
            # Step 1: Find mutually available meeting times using MCP
            meeting_times_result = await self.mcp_client.call_tool(
                server_name="calendar-server",
                tool_name="find_meeting_times",
                arguments={
                    "attendee_emails": [candidate_email] + interviewer_emails,
                    "duration_minutes": duration_minutes,
                    "start_date": start_date or (datetime.now() + timedelta(days=1)).isoformat(),
                    "end_date": end_date or (datetime.now() + timedelta(days=14)).isoformat(),
                    "timezone": "UTC",
                }
            )
            
            meeting_times = meeting_times_result.get("meeting_times", [])
            
            if not meeting_times:
                return self._create_result(
                    output={
                        "available_slots": [],
                        "message": "No mutually available time slots found.",
                    },
                    confidence=1.0,
                )
            
            # Step 2: Select best time slot (first available)
            selected_slot = meeting_times[0]
            start_time = selected_slot["start"]
            end_time = selected_slot["end"]
            
            # Step 3: Create calendar event using MCP
            event_result = await self.mcp_client.call_tool(
                server_name="calendar-server",
                tool_name="create_calendar_event",
                arguments={
                    "subject": f"{interview_type.title()} Interview - {candidate_email}",
                    "start_time": start_time,
                    "end_time": end_time,
                    "attendee_emails": [candidate_email] + interviewer_emails,
                    "body_content": f"Interview for {interview_type} position.",
                    "is_online_meeting": True,
                }
            )
            
            return self._create_result(
                output={
                    "event_id": event_result.get("event_id"),
                    "meeting_link": event_result.get("meeting_link"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "attendees": [candidate_email] + interviewer_emails,
                    "duration_minutes": duration_minutes,
                    "interview_type": interview_type,
                    "status": "scheduled",
                },
                confidence=0.95,
                evidence=[
                    f"Found {len(meeting_times)} available time slots",
                    f"Selected slot: {start_time}",
                    f"Created calendar event: {event_result.get('event_id')}",
                ],
            )
        
        except Exception as e:
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to schedule interview: {str(e)}",
            )
    
    async def get_availability(
        self,
        user_email: str,
        start_date: str,
        end_date: str,
        duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Get calendar availability using MCP.
        
        Args:
            user_email: User email
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            duration_minutes: Required duration
            
        Returns:
            Availability data
        """
        result = await self.mcp_client.call_tool(
            server_name="calendar-server",
            tool_name="get_calendar_availability",
            arguments={
                "user_email": user_email,
                "start_date": start_date,
                "end_date": end_date,
                "duration_minutes": duration_minutes,
                "timezone": "UTC",
            }
        )
        return result
