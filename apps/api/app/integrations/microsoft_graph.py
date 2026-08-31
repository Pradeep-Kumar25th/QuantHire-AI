"""Microsoft Graph API integration for calendar and email."""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import msal
from httpx import AsyncClient

logger = logging.getLogger(__name__)


class MicrosoftGraphClient:
    """Client for Microsoft Graph API operations."""
    
    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
    SCOPES = ["https://graph.microsoft.com/.default"]
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """
        Initialize Microsoft Graph client.
        
        Args:
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            tenant_id: Azure AD tenant ID
        """
        self.client_id = client_id or os.getenv("MICROSOFT_GRAPH_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("MICROSOFT_GRAPH_CLIENT_SECRET")
        self.tenant_id = tenant_id or os.getenv("MICROSOFT_GRAPH_TENANT_ID")
        
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            logger.warning("Microsoft Graph credentials not configured")
            self.enabled = False
        else:
            self.enabled = True
        
        self._token = None
        self._token_expiry = None
    
    async def get_access_token(self) -> str:
        """Get access token using client credentials flow."""
        # Check if token is still valid
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token
        
        # Request new token
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret,
        )
        
        result = app.acquire_token_for_client(scopes=self.SCOPES)
        
        if "access_token" in result:
            self._token = result["access_token"]
            # Token expires in 1 hour, refresh 5 minutes early
            self._token_expiry = datetime.now() + timedelta(seconds=result.get("expires_in", 3600) - 300)
            logger.info("Microsoft Graph access token acquired")
            return self._token
        else:
            error = result.get("error_description", "Unknown error")
            logger.error(f"Failed to acquire token: {error}")
            raise Exception(f"Failed to acquire Microsoft Graph token: {error}")
    
    async def find_available_time_slots(
        self,
        attendee_emails: List[str],
        duration_minutes: int,
        start_date: str,
        end_date: str,
        timezone: str = "UTC",
    ) -> List[Dict]:
        """
        Find available meeting time slots.
        
        Uses Microsoft Graph findMeetingTimes API.
        
        Args:
            attendee_emails: List of attendee email addresses
            duration_minutes: Meeting duration in minutes
            start_date: Start date for search (YYYY-MM-DD)
            end_date: End date for search (YYYY-MM-DD)
            timezone: Timezone for results
            
        Returns:
            List of available time slots
        """
        if not self.enabled:
            logger.warning("Microsoft Graph not configured, returning mock data")
            return self._mock_time_slots()
        
        token = await self.get_access_token()
        
        # Prepare request
        url = f"{self.GRAPH_API_ENDPOINT}/me/findMeetingTimes"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        attendees = [
            {"emailAddress": {"address": email}, "type": "Required"}
            for email in attendee_emails
        ]
        
        body = {
            "attendees": attendees,
            "timeConstraint": {
                "timeslots": [
                    {
                        "start": {
                            "dateTime": f"{start_date}T09:00:00",
                            "timeZone": timezone
                        },
                        "end": {
                            "dateTime": f"{end_date}T17:00:00",
                            "timeZone": timezone
                        }
                    }
                ]
            },
            "meetingDuration": f"PT{duration_minutes}M",
            "returnSuggestionReasons": True,
            "minimumAttendeePercentage": 100,
        }
        
        async with AsyncClient() as client:
            response = await client.post(url, headers=headers, json=body)
            
            if response.status_code == 200:
                data = response.json()
                suggestions = data.get("meetingTimeSuggestions", [])
                
                return [
                    {
                        "start": slot["meetingTimeSlot"]["start"]["dateTime"],
                        "end": slot["meetingTimeSlot"]["end"]["dateTime"],
                        "confidence": slot.get("confidence", "high"),
                        "attendee_availability": slot.get("attendeeAvailability", [])
                    }
                    for slot in suggestions
                ]
            else:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                return []
    
    async def create_meeting(
        self,
        subject: str,
        start_time: str,
        end_time: str,
        attendee_emails: List[str],
        body_content: str,
        timezone: str = "UTC",
        organizer_email: Optional[str] = None,
    ) -> Dict:
        """
        Create calendar meeting.
        
        Args:
            subject: Meeting subject
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            attendee_emails: List of attendee emails
            body_content: Meeting description
            timezone: Timezone
            organizer_email: Organizer email (uses service account if None)
            
        Returns:
            Meeting details including join link
        """
        if not self.enabled:
            logger.warning("Microsoft Graph not configured, returning mock meeting")
            return self._mock_meeting()
        
        token = await self.get_access_token()
        
        # Use /users/{id}/events if organizer specified, otherwise /me/events
        if organizer_email:
            url = f"{self.GRAPH_API_ENDPOINT}/users/{organizer_email}/events"
        else:
            url = f"{self.GRAPH_API_ENDPOINT}/me/events"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        attendees = [
            {
                "emailAddress": {"address": email},
                "type": "Required"
            }
            for email in attendee_emails
        ]
        
        body = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_content
            },
            "start": {
                "dateTime": start_time,
                "timeZone": timezone
            },
            "end": {
                "dateTime": end_time,
                "timeZone": timezone
            },
            "attendees": attendees,
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness"
        }
        
        async with AsyncClient() as client:
            response = await client.post(url, headers=headers, json=body)
            
            if response.status_code == 201:
                meeting = response.json()
                logger.info(f"Meeting created: {meeting.get('id')}")
                
                return {
                    "meeting_id": meeting["id"],
                    "subject": meeting["subject"],
                    "start": meeting["start"]["dateTime"],
                    "end": meeting["end"]["dateTime"],
                    "join_url": meeting.get("onlineMeeting", {}).get("joinUrl"),
                    "organizer": meeting["organizer"]["emailAddress"]["address"],
                }
            else:
                logger.error(f"Failed to create meeting: {response.status_code} - {response.text}")
                raise Exception(f"Failed to create meeting: {response.text}")
    
    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body_html: str,
        from_email: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
    ) -> bool:
        """
        Send email via Microsoft Graph.
        
        Args:
            to_emails: Recipient email addresses
            subject: Email subject
            body_html: Email body (HTML)
            from_email: Sender email (uses service account if None)
            cc_emails: CC recipients
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.warning("Microsoft Graph not configured, email not sent")
            return False
        
        token = await self.get_access_token()
        
        # Use /users/{id}/sendMail if from_email specified
        if from_email:
            url = f"{self.GRAPH_API_ENDPOINT}/users/{from_email}/sendMail"
        else:
            url = f"{self.GRAPH_API_ENDPOINT}/me/sendMail"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        to_recipients = [
            {"emailAddress": {"address": email}}
            for email in to_emails
        ]
        
        cc_recipients = [
            {"emailAddress": {"address": email}}
            for email in (cc_emails or [])
        ]
        
        body = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html
                },
                "toRecipients": to_recipients,
                "ccRecipients": cc_recipients,
            },
            "saveToSentItems": True
        }
        
        async with AsyncClient() as client:
            response = await client.post(url, headers=headers, json=body)
            
            if response.status_code == 202:
                logger.info(f"Email sent to {', '.join(to_emails)}")
                return True
            else:
                logger.error(f"Failed to send email: {response.status_code} - {response.text}")
                return False
    
    async def get_user_calendar(
        self,
        user_email: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict]:
        """
        Get user's calendar events.
        
        Args:
            user_email: User's email address
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            List of calendar events
        """
        if not self.enabled:
            return []
        
        token = await self.get_access_token()
        
        url = f"{self.GRAPH_API_ENDPOINT}/users/{user_email}/calendarView"
        params = {
            "startDateTime": start_date,
            "endDateTime": end_date
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            else:
                logger.error(f"Failed to get calendar: {response.status_code}")
                return []
    
    def _mock_time_slots(self) -> List[Dict]:
        """Return mock time slots for testing."""
        return [
            {
                "start": "2024-10-15T09:00:00",
                "end": "2024-10-15T10:00:00",
                "confidence": "high",
                "attendee_availability": []
            },
            {
                "start": "2024-10-15T14:00:00",
                "end": "2024-10-15T15:00:00",
                "confidence": "high",
                "attendee_availability": []
            },
        ]
    
    def _mock_meeting(self) -> Dict:
        """Return mock meeting for testing."""
        return {
            "meeting_id": "mock_meeting_123",
            "subject": "Mock Interview",
            "start": "2024-10-15T14:00:00",
            "end": "2024-10-15T15:00:00",
            "join_url": "https://teams.microsoft.com/l/meetup-join/mock",
            "organizer": "recruiter@test.com",
        }


# Global client instance
_graph_client: Optional[MicrosoftGraphClient] = None


def init_graph_client(
    client_id: str,
    client_secret: str,
    tenant_id: str,
) -> MicrosoftGraphClient:
    """Initialize global Microsoft Graph client."""
    global _graph_client
    _graph_client = MicrosoftGraphClient(client_id, client_secret, tenant_id)
    return _graph_client


def get_graph_client() -> MicrosoftGraphClient:
    """Get global Microsoft Graph client."""
    if _graph_client is None:
        # Initialize with env vars
        return MicrosoftGraphClient()
    return _graph_client












