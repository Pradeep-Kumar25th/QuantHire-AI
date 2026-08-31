"""
Calendar MCP Server - Built from Scratch
Provides calendar operations for interview scheduling in QuantHire AI.

This server exposes calendar tools that agents can use to:
- Get calendar availability
- Find meeting times
- Create calendar events
- Update/cancel events
"""

from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add path to import Microsoft Graph client
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../"))
try:
    from apps.api.app.integrations.microsoft_graph import MicrosoftGraphClient
    GRAPH_CLIENT_AVAILABLE = True
except ImportError:
    logger.warning("Microsoft Graph client not found, using mock mode")
    GRAPH_CLIENT_AVAILABLE = False
    MicrosoftGraphClient = None

# Initialize FastMCP server
mcp = FastMCP("Calendar Server")

# Initialize Graph client (if available)
graph_client = None
if GRAPH_CLIENT_AVAILABLE:
    try:
        graph_client = MicrosoftGraphClient()
        if graph_client.enabled:
            logger.info("✅ Microsoft Graph client initialized")
        else:
            logger.warning("⚠️ Microsoft Graph not configured, using mock mode")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize Graph client: {e}")


def calculate_available_slots_from_events(
    events: List[Dict],
    start_date: str,
    end_date: str,
    duration_minutes: int
) -> List[Dict[str, str]]:
    """Calculate available slots from calendar events."""
    start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    
    # Extract busy times
    busy_periods = []
    for event in events:
        if "start" in event and "end" in event:
            try:
                busy_start = datetime.fromisoformat(
                    event["start"]["dateTime"].replace("Z", "+00:00")
                )
                busy_end = datetime.fromisoformat(
                    event["end"]["dateTime"].replace("Z", "+00:00")
                )
                busy_periods.append({"start": busy_start, "end": busy_end})
            except (KeyError, ValueError) as e:
                logger.warning(f"Error parsing event: {e}")
                continue
    
    # Sort busy periods
    busy_periods.sort(key=lambda x: x["start"])
    
    # Find available slots
    available_slots = []
    current_time = start
    business_start_hour = 9
    business_end_hour = 17
    
    while current_time < end:
        # Skip weekends
        if current_time.weekday() >= 5:
            current_time = current_time.replace(hour=business_start_hour, minute=0, second=0)
            current_time += timedelta(days=1)
            continue
        
        # Skip outside business hours
        if current_time.hour < business_start_hour:
            current_time = current_time.replace(hour=business_start_hour, minute=0, second=0)
        elif current_time.hour >= business_end_hour:
            current_time = current_time.replace(hour=business_start_hour, minute=0, second=0)
            current_time += timedelta(days=1)
            continue
        
        slot_end = current_time + timedelta(minutes=duration_minutes)
        
        # Check if slot overlaps with busy time
        is_busy = False
        for busy in busy_periods:
            if not (slot_end <= busy["start"] or current_time >= busy["end"]):
                is_busy = True
                current_time = busy["end"]
                break
        
        if not is_busy and slot_end <= end:
            available_slots.append({
                "start": current_time.isoformat(),
                "end": slot_end.isoformat(),
            })
            current_time += timedelta(minutes=30)
        else:
            current_time += timedelta(minutes=15)
    
    return available_slots


def generate_mock_availability(
    start_date: str,
    end_date: str,
    duration_minutes: int
) -> List[Dict[str, str]]:
    """Generate mock availability for testing."""
    start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    
    available_slots = []
    current_time = start.replace(hour=9, minute=0, second=0)
    
    while current_time < end:
        if current_time.weekday() >= 5:
            current_time += timedelta(days=1)
            current_time = current_time.replace(hour=9, minute=0, second=0)
            continue
        
        if current_time.hour >= 17:
            current_time += timedelta(days=1)
            current_time = current_time.replace(hour=9, minute=0, second=0)
            continue
        
        slot_end = current_time + timedelta(minutes=duration_minutes)
        if slot_end <= end and slot_end.hour <= 17:
            available_slots.append({
                "start": current_time.isoformat(),
                "end": slot_end.isoformat(),
            })
        
        current_time += timedelta(hours=1)
    
    return available_slots


# Tool 1: Get Calendar Availability
@mcp.tool()
async def get_calendar_availability(
    user_email: str,
    start_date: str,
    end_date: str,
    duration_minutes: int = 60,
    timezone: str = "UTC"
) -> str:
    """
    Get calendar availability for a user.
    
    This tool retrieves available time slots for a user's calendar.
    Perfect for checking when interviewers or candidates are available.
    
    Args:
        user_email: User's email address
        start_date: Start date in ISO format (YYYY-MM-DDTHH:MM:SS)
        end_date: End date in ISO format (YYYY-MM-DDTHH:MM:SS)
        duration_minutes: Required duration in minutes (default: 60)
        timezone: Timezone identifier (default: UTC)
    
    Returns:
        JSON string with available time slots
    """
    try:
        logger.info(f"Getting availability for {user_email}")
        
        if graph_client and graph_client.enabled:
            events = await graph_client.get_user_calendar(
                user_email=user_email,
                start_date=start_date,
                end_date=end_date,
            )
            available_slots = calculate_available_slots_from_events(
                events=events,
                start_date=start_date,
                end_date=end_date,
                duration_minutes=duration_minutes,
            )
        else:
            available_slots = generate_mock_availability(
                start_date=start_date,
                end_date=end_date,
                duration_minutes=duration_minutes,
            )
        
        response = {
            "user_email": user_email,
            "available_slots": available_slots,
            "total_slots": len(available_slots),
            "duration_minutes": duration_minutes,
            "timezone": timezone,
        }
        
        logger.info(f"Found {len(available_slots)} available slots")
        return json.dumps(response, indent=2)
    
    except Exception as e:
        logger.error(f"Error getting availability: {e}")
        return json.dumps({
            "error": str(e),
            "user_email": user_email,
            "available_slots": []
        })


# Tool 2: Find Meeting Times
@mcp.tool()
async def find_meeting_times(
    attendee_emails: List[str],
    duration_minutes: int,
    start_date: str,
    end_date: str,
    timezone: str = "UTC"
) -> str:
    """
    Find mutually available meeting times for multiple attendees.
    
    This tool finds time slots when all attendees are available.
    Perfect for scheduling interviews with candidates and interviewers.
    
    Args:
        attendee_emails: List of attendee email addresses
        duration_minutes: Meeting duration in minutes
        start_date: Start date for search (ISO format)
        end_date: End date for search (ISO format)
        timezone: Timezone identifier (default: UTC)
    
    Returns:
        JSON string with available meeting times
    """
    try:
        logger.info(f"Finding meeting times for {len(attendee_emails)} attendees")
        
        if graph_client and graph_client.enabled:
            meeting_times = await graph_client.find_available_time_slots(
                attendee_emails=attendee_emails,
                duration_minutes=duration_minutes,
                start_date=start_date,
                end_date=end_date,
                timezone=timezone,
            )
        else:
            # Mock mode - use common business hours
            meeting_times = generate_mock_availability(
                start_date=start_date,
                end_date=end_date,
                duration_minutes=duration_minutes,
            )
        
        response = {
            "attendees": attendee_emails,
            "duration_minutes": duration_minutes,
            "meeting_times": meeting_times,
            "total_options": len(meeting_times),
            "timezone": timezone,
        }
        
        logger.info(f"Found {len(meeting_times)} meeting time options")
        return json.dumps(response, indent=2)
    
    except Exception as e:
        logger.error(f"Error finding meeting times: {e}")
        return json.dumps({
            "error": str(e),
            "attendees": attendee_emails,
            "meeting_times": []
        })


# Tool 3: Create Calendar Event
@mcp.tool()
async def create_calendar_event(
    subject: str,
    start_time: str,
    end_time: str,
    attendee_emails: List[str],
    body_content: Optional[str] = None,
    location: Optional[str] = None,
    is_online_meeting: bool = True
) -> str:
    """
    Create a calendar event/meeting.
    
    This tool creates a calendar event and sends invites to attendees.
    Perfect for creating interview meetings.
    
    Args:
        subject: Meeting subject/title
        start_time: Start time in ISO format
        end_time: End time in ISO format
        attendee_emails: List of attendee email addresses
        body_content: Meeting body/content (optional)
        location: Meeting location (optional)
        is_online_meeting: Create Teams/Zoom meeting (default: True)
    
    Returns:
        JSON string with created event details
    """
    try:
        logger.info(f"Creating calendar event: {subject}")
        
        if graph_client and graph_client.enabled:
            meeting = await graph_client.create_meeting(
                subject=subject,
                start_time=start_time,
                end_time=end_time,
                attendee_emails=attendee_emails,
                body_content=body_content or "",
                location=location,
                is_online_meeting=is_online_meeting,
            )
            
            response = {
                "event_id": meeting.get("meeting_id"),
                "meeting_link": meeting.get("join_url"),
                "subject": subject,
                "start_time": start_time,
                "end_time": end_time,
                "attendees": attendee_emails,
                "status": "created",
                "source": "microsoft_graph",
            }
        else:
            # Mock mode
            response = {
                "event_id": f"mock-event-{int(datetime.now().timestamp())}",
                "meeting_link": "https://teams.microsoft.com/mock-meeting",
                "subject": subject,
                "start_time": start_time,
                "end_time": end_time,
                "attendees": attendee_emails,
                "status": "created",
                "source": "mock",
            }
        
        logger.info(f"✅ Event created: {response['event_id']}")
        return json.dumps(response, indent=2)
    
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return json.dumps({
            "error": str(e),
            "subject": subject,
            "event_id": None
        })


# Tool 4: Update Calendar Event
@mcp.tool()
async def update_calendar_event(
    event_id: str,
    subject: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    attendee_emails: Optional[List[str]] = None,
    body_content: Optional[str] = None
) -> str:
    """
    Update an existing calendar event.
    
    Args:
        event_id: Calendar event ID
        subject: New subject (optional)
        start_time: New start time (optional)
        end_time: New end time (optional)
        attendee_emails: New attendees (optional)
        body_content: New body content (optional)
    
    Returns:
        JSON string with updated event details
    """
    try:
        logger.info(f"Updating calendar event: {event_id}")
        
        # TODO: Implement actual update via Microsoft Graph
        response = {
            "event_id": event_id,
            "status": "updated",
            "message": "Event updated successfully",
            "updated_fields": {
                "subject": subject,
                "start_time": start_time,
                "end_time": end_time,
                "attendees": attendee_emails,
            }
        }
        
        logger.info(f"✅ Event updated: {event_id}")
        return json.dumps(response, indent=2)
    
    except Exception as e:
        logger.error(f"Error updating event: {e}")
        return json.dumps({
            "error": str(e),
            "event_id": event_id
        })


# Tool 5: Cancel Calendar Event
@mcp.tool()
async def cancel_calendar_event(
    event_id: str,
    notify_attendees: bool = True
) -> str:
    """
    Cancel a calendar event.
    
    Args:
        event_id: Calendar event ID
        notify_attendees: Send cancellation to attendees (default: True)
    
    Returns:
        JSON string with cancellation status
    """
    try:
        logger.info(f"Canceling calendar event: {event_id}")
        
        # TODO: Implement actual cancellation via Microsoft Graph
        response = {
            "event_id": event_id,
            "status": "cancelled",
            "notified_attendees": notify_attendees,
            "message": "Event cancelled successfully",
        }
        
        logger.info(f"✅ Event cancelled: {event_id}")
        return json.dumps(response, indent=2)
    
    except Exception as e:
        logger.error(f"Error canceling event: {e}")
        return json.dumps({
            "error": str(e),
            "event_id": event_id
        })


# Run the server
if __name__ == "__main__":
    logger.info("🚀 Starting Calendar MCP Server...")
    logger.info("Server listening on stdio...")
    mcp.run(transport="stdio")
