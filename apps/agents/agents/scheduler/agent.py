"""Interview scheduling agent with calendar coordination."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class TimeSlot(BaseModel):
    """Time slot model."""

    start: datetime
    end: datetime
    available: bool = True


class SchedulerAgent(BaseAgent):
    """Agent for scheduling interviews and coordinating calendars."""

    def __init__(self):
        """Initialize scheduler agent."""
        config = AgentConfig(
            name="SchedulerAgent",
            description="Schedules interviews, resolves conflicts, coordinates calendars",
            temperature=0.3,  # Deterministic scheduling
        )
        super().__init__(config)

    def _find_available_slots(
        self,
        candidate_availability: List[TimeSlot],
        interviewer_availability: List[TimeSlot],
        duration_minutes: int = 60
    ) -> List[TimeSlot]:
        """Find overlapping available time slots.
        
        Args:
            candidate_availability: Candidate's available slots
            interviewer_availability: Interviewer's available slots
            duration_minutes: Interview duration
            
        Returns:
            List of mutually available slots
        """
        available_slots = []
        
        for candidate_slot in candidate_availability:
            if not candidate_slot.available:
                continue
                
            for interviewer_slot in interviewer_availability:
                if not interviewer_slot.available:
                    continue
                
                # Find overlap
                overlap_start = max(candidate_slot.start, interviewer_slot.start)
                overlap_end = min(candidate_slot.end, interviewer_slot.end)
                
                # Check if overlap is long enough
                if (overlap_end - overlap_start).total_seconds() >= duration_minutes * 60:
                    available_slots.append(TimeSlot(
                        start=overlap_start,
                        end=overlap_start + timedelta(minutes=duration_minutes),
                        available=True
                    ))
        
        return available_slots

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Schedule interview.
        
        Args:
            input_data: Dictionary with:
                - candidate_availability: List of candidate time slots
                - interviewer_availability: List of interviewer time slots
                - duration_minutes: Interview duration
                - interview_type: Type of interview
                - preferences: Any scheduling preferences
                
        Returns:
            AgentResult with suggested time slots
        """
        candidate_availability = input_data.get("candidate_availability", [])
        interviewer_availability = input_data.get("interviewer_availability", [])
        duration_minutes = input_data.get("duration_minutes", 60)
        interview_type = input_data.get("interview_type", "technical")
        
        try:
            # Convert dicts to TimeSlot objects if needed
            if candidate_availability and isinstance(candidate_availability[0], dict):
                candidate_availability = [
                    TimeSlot(**slot) for slot in candidate_availability
                ]
            
            if interviewer_availability and isinstance(interviewer_availability[0], dict):
                interviewer_availability = [
                    TimeSlot(**slot) for slot in interviewer_availability
                ]
            
            # Find available slots
            available_slots = self._find_available_slots(
                candidate_availability,
                interviewer_availability,
                duration_minutes
            )
            
            if not available_slots:
                return self._create_result(
                    output={
                        "available_slots": [],
                        "message": "No mutually available time slots found. Please provide more availability.",
                    },
                    confidence=1.0,
                    metadata={"conflict_detected": True},
                )
            
            # Rank slots (prefer earlier, business hours)
            ranked_slots = sorted(
                available_slots,
                key=lambda s: (
                    s.start.weekday() >= 5,  # Prefer weekdays
                    abs(s.start.hour - 14),  # Prefer around 2 PM
                    s.start  # Earlier is better
                )
            )
            
            # Take top 3 suggestions
            top_slots = ranked_slots[:3]
            
            return self._create_result(
                output={
                    "available_slots": [
                        {
                            "start": slot.start.isoformat(),
                            "end": slot.end.isoformat(),
                            "duration_minutes": duration_minutes,
                        }
                        for slot in top_slots
                    ],
                    "total_found": len(available_slots),
                    "message": f"Found {len(available_slots)} available slots. Top 3 recommendations provided.",
                },
                confidence=0.95,
                evidence=[
                    f"Analyzed {len(candidate_availability)} candidate slots",
                    f"Analyzed {len(interviewer_availability)} interviewer slots",
                    f"Found {len(available_slots)} mutually available slots",
                ],
            )

        except Exception as e:
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to schedule interview: {str(e)}",
            )

    def generate_default_availability(
        self,
        days_ahead: int = 14
    ) -> List[TimeSlot]:
        """Generate default availability slots for testing.
        
        Args:
            days_ahead: Number of days to generate slots for
            
        Returns:
            List of time slots
        """
        slots = []
        start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        
        for day in range(days_ahead):
            current_date = start_date + timedelta(days=day)
            
            # Skip weekends
            if current_date.weekday() >= 5:
                continue
            
            # Morning slot (9-12)
            slots.append(TimeSlot(
                start=current_date.replace(hour=9),
                end=current_date.replace(hour=12),
                available=True
            ))
            
            # Afternoon slot (14-17)
            slots.append(TimeSlot(
                start=current_date.replace(hour=14),
                end=current_date.replace(hour=17),
                available=True
            ))
        
        return slots

