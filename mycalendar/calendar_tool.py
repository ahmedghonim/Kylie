import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly',
          'https://www.googleapis.com/auth/calendar.events']

logger = logging.getLogger(__name__)

class CalendarTool:
    """
    A tool for interacting with a Google Calendar using the Google Calendar API.
    Requires initial setup of credentials.json and user authorization flow.
    """

    def __init__(self, credentials_file: str = "mycalendar\credentials.json", token_file: str = "token.json"):
        """
        Initializes the CalendarTool.
        Args:
            credentials_file: Path to the downloaded credentials.json file.
            token_file: Path to store/load user authorization tokens.
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Handles the authentication flow with Google Calendar API."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())

        try:
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Successfully authenticated with Google Calendar.")
        except HttpError as error:
            logger.error(f"An error occurred during authentication: {error}")
            self.service = None


    async def list_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Lists the upcoming events on the user's primary calendar.
        Args:
            max_results: Maximum number of events to return.
        Returns:
            A list of dictionaries representing events, or an empty list on error.
        """
        if not self.service:
             logger.error("Calendar service not initialized.")
             return [{"error": "Calendar service not initialized."}]

        try:
            now = datetime.utcnow().isoformat() + 'Z'
            logger.info(f"Getting the upcoming {max_results} events")
            events_result = self.service.events().list(calendarId='primary', timeMin=now,
                                                maxResults=max_results, singleEvents=True,
                                                orderBy='startTime').execute()
            events = events_result.get('items', [])

            formatted_events = []
            if not events:
                logger.info('No upcoming events found.')
                return [{"summary": "No upcoming events found."}]
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                formatted_events.append({
                    "summary": event.get('summary', 'No Title'),
                    "start": start,
                    "id": event.get('id')
                })
            logger.info(f"Found {len(formatted_events)} upcoming events.")
            return formatted_events

        except HttpError as error:
            logger.error(f"An error occurred while fetching events: {error}")
            return [{"error": f"An error occurred while fetching events: {error}"}]

    async def add_event(self, summary: str, start_time: str, end_time: str, description: str = "") -> Dict[str, Any]:
        """
        Adds an event to the user's primary calendar.
        Args:
            summary: Title of the event.
            start_time: Start time in ISO 8601 format (e.g., '2024-07-15T10:00:00').
            end_time: End time in ISO 8601 format (e.g., '2024-07-15T11:00:00').
            description: Optional description of the event.
        Returns:
            A dictionary with the result (success/failure message or event details) or error.
        """
         # Validate input times
        try:
            datetime.fromisoformat(start_time.replace('Z', '+00:00')) # Handle 'Z' suffix
            datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            error_msg = "Invalid date/time format. Please use ISO 8601 (e.g., '2024-07-15T10:00:00')."
            logger.error(error_msg)
            return {"error": error_msg}

        if not self.service:
            error_msg = "Calendar service not initialized."
            logger.error(error_msg)
            return {"error": error_msg}

        event = {
            'summary': summary,
            'location': '', 
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'UTC', 
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'UTC', 
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60}, 
                    {'method': 'popup', 'minutes': 10}, 
                ],
            },
        }
        try:
                event_result = self.service.events().insert(calendarId='primary', body=event).execute()
                success_msg = f"Event created: {event_result.get('htmlLink')}"
                logger.info(success_msg)
                return {
                    "status": "success",
                    "summary": event_result.get('summary'),
                    "start": event_result['start'].get('dateTime', event_result['start'].get('date')),
                    "id": event_result.get('id'),
                    "link": event_result.get('htmlLink')
                }
        except HttpError as error:
            error_msg = f"An error occurred while adding the event: {error}"
            logger.error(error_msg)
            return {"error": error_msg}

    # Example: Check for events happening now or soon
    async def get_current_or_next_event(self, lookahead_minutes: int = 30) -> Optional[Dict[str, Any]]:
        """
        Checks for events happening right now or within the next 'lookahead_minutes'.
        Args:
            lookahead_minutes: How many minutes into the future to check.
        Returns:
            A dictionary representing the event if found, otherwise None.
        """
        if not self.service:
            logger.error("Calendar service not initialized.")
            return None

        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(minutes=lookahead_minutes)).isoformat() + 'Z'

            logger.info(f"Checking for events between {time_min} and {time_max}")
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            if events:
                event = events[0] # Get the first (closest) event
                start = event['start'].get('dateTime', event['start'].get('date'))
                logger.info(f"Upcoming/Current event found: {event.get('summary')}")
                return {
                    "summary": event.get('summary', 'No Title'),
                    "start": start,
                    "id": event.get('id')
                }
            else:
                logger.info("No events found in the specified time window.")
                return None

        except HttpError as error:
            logger.error(f"An error occurred while checking for current/next event: {error}")
            return None




# Example usage (if run directly or for testing)  
# run in terminal for testing(uv run calendar_tool.py OR py calendar_tool.py)
# Tests include:
# listing 3 upcoming events
# listing more upcoming events(10)
# Check current or next event (within 30 minutes)
# Check within a longer timeframe
# Add a test event
# Calculate times for a test event (1 hour from now, lasting 30 minutes)
# Test different time formats
# Edge cases for listing events
# Different time windows for current/next event

# if __name__ == "__main__":
#     import asyncio
#     from datetime import datetime, timezone, timedelta
    
#     async def main():
#         print("🚀 Starting CalendarTool Test Suite...")
#         print("=" * 50)
        
#         # Initialize the tool
#         tool = CalendarTool()
        
#         # Test 1: List upcoming events (different quantities)
#         print("\n📅 TEST 1: Listing upcoming events")
#         print("-" * 30)
#         events = await tool.list_upcoming_events(3)
#         print(f"Next 3 events: {len(events)} found")
#         for i, event in enumerate(events, 1):
#             print(f"  {i}. {event.get('summary', 'No title')} - {event.get('start', 'No date')}")
        
#         # Test 2: List more events
#         print(f"\nFetching more events (10)...")
#         more_events = await tool.list_upcoming_events(10)
#         print(f"Next 10 events: {len(more_events)} found")
        
#         # Test 3: Check current or next event (within 30 minutes)
#         print("\n⏰ TEST 2: Checking current/next event (30 min window)")
#         print("-" * 30)
#         current_event = await tool.get_current_or_next_event(30)
#         if current_event:
#             print(f"Found current/upcoming event: {current_event['summary']} at {current_event['start']}")
#         else:
#             print("No events in the next 30 minutes")
        
#         # Test 4: Check within a longer timeframe
#         print(f"\nChecking within 2 hours...")
#         next_event_2h = await tool.get_current_or_next_event(120)
#         if next_event_2h:
#             print(f"Event within 2 hours: {next_event_2h['summary']} at {next_event_2h['start']}")
#         else:
#             print("No events in the next 2 hours")
        
#         # Test 5: Add a test event (uncomment to test)
#         print("\n➕ TEST 3: Adding a test event")
#         print("-" * 30)
        
#         # Calculate times for a test event (1 hour from now, lasting 30 minutes)
#         now = datetime.now(timezone.utc)
#         start_time = (now + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
#         end_time = (now + timedelta(hours=1, minutes=30)).isoformat().replace('+00:00', 'Z')
        
#         print(f"Adding test event from {start_time} to {end_time}")
#         result = await tool.add_event(
#             "🧪 Test Event from CalendarTool", 
#             start_time, 
#             end_time, 
#             "This is a test event created by the CalendarTool script. You can delete this."
#         )
        
#         if result.get('status') == 'success':
#             print(f"✅ Event created successfully!")
#             print(f"   Title: {result['summary']}")
#             print(f"   Start: {result['start']}")
#             print(f"   Event ID: {result['id']}")
#             print(f"   Link: {result.get('link', 'N/A')}")
#         else:
#             print(f"❌ Failed to create event: {result.get('error', 'Unknown error')}")
        
#         # Test 6: Test different time formats
#         print("\n🕐 TEST 4: Testing different time formats")
#         print("-" * 30)
        
#         # Test with different time formats (these should fail gracefully)
#         invalid_formats = [
#             ("Invalid format 1", "2024-13-45", "2024-13-46", "Should fail - invalid date"),
#             ("Invalid format 2", "not-a-date", "also-not-a-date", "Should fail - not a date"),
#         ]
        
#         for title, start, end, description in invalid_formats:
#             print(f"Testing {title}...")
#             result = await tool.add_event(title, start, end, description)
#             if 'error' in result:
#                 print(f"  ✅ Correctly caught error: {result['error']}")
#             else:
#                 print(f"  ❌ Should have failed but didn't: {result}")
        
#         # Test 7: Edge cases for listing events
#         print("\n🔍 TEST 5: Edge cases")
#         print("-" * 30)
        
#         # Test listing 0 events
#         zero_events = await tool.list_upcoming_events(0)
#         print(f"Requesting 0 events returned: {len(zero_events)} items")
        
#         # Test listing many events
#         many_events = await tool.list_upcoming_events(50)
#         print(f"Requesting 50 events returned: {len(many_events)} items")
        
#         # Test 8: Different time windows for current/next event
#         print("\n🎯 TEST 6: Different time windows")
#         print("-" * 30)
        
#         time_windows = [5, 15, 60, 240, 1440]  # 5 min, 15 min, 1 hour, 4 hours, 24 hours
#         for minutes in time_windows:
#             event = await tool.get_current_or_next_event(minutes)
#             if event:
#                 print(f"  Within {minutes} minutes: {event['summary']}")
#             else:
#                 print(f"  Within {minutes} minutes: No events")
        
#         print("\n" + "=" * 50)
#         print("🎉 Test Suite Complete!")
#         print("\nIf you want to test adding events, uncomment the add_event lines above")
#         print("and modify the times to be in the future.")
        
#     asyncio.run(main())
