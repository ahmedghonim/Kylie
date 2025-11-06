import asyncio
import logging
from typing import List, Any, Dict, Optional
from datetime import datetime

from langchain_core.tools import BaseTool, tool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field

from .calendar_tool import CalendarTool

logger = logging.getLogger(__name__)

# Initialize the calendar tool globally
_calendar_tool = CalendarTool()

class ListEventsInput(BaseModel):
    """Input for listing calendar events."""
    max_results: int = Field(default=10, description="Maximum number of events to return (1-50)")

class AddEventInput(BaseModel):
    """Input for adding a calendar event."""
    summary: str = Field(description="Title/summary of the event")
    start_time: str = Field(description="Start time in ISO format (YYYY-MM-DDTHH:MM:SS)")
    end_time: str = Field(description="End time in ISO format (YYYY-MM-DDTHH:MM:SS)")
    description: str = Field(default="", description="Optional event description")

class GetCurrentEventInput(BaseModel):
    """Input for getting current/next event."""
    lookahead_minutes: int = Field(default=30, description="Minutes to look ahead for upcoming events")

@tool("list_upcoming_events", args_schema=ListEventsInput)
async def list_upcoming_events(max_results: int = 10) -> str:
    """
    List upcoming events from the user's calendar.
    Returns a formatted string with event details.
    """
    try:
        print(f"DEBUG: Calling list_upcoming_events with max_results={max_results}")
        events = await _calendar_tool.list_upcoming_events(max_results=max_results)
        print(f"DEBUG: Got events: {events}")
        
        if not events or (len(events) == 1 and "error" in events[0]):
            return "No upcoming events found or there was an error accessing the calendar."
        
        if isinstance(events, list) and len(events) > 0 and "error" in events[0]:
            return f"Error: {events[0]['error']}"
        
        formatted_events = []
        for event in events:
            if "error" not in event:
                summary = event.get('summary', 'No title')
                start = event.get('start', 'No start time')
                formatted_events.append(f"• {summary} - {start}")
        
        if not formatted_events:
            return "No upcoming events found."
        
        result = "Here are your upcoming events:\n" + "\n".join(formatted_events)
        print(f"DEBUG: Returning formatted result: {result}")
        return result
    
    except Exception as e:
        logger.error(f"Error in list_upcoming_events: {e}")
        error_msg = f"Sorry, I encountered an error while checking your calendar: {str(e)}"
        print(f"DEBUG: Returning error message: {error_msg}")
        return error_msg

@tool("add_calendar_event", args_schema=AddEventInput)
async def add_calendar_event(
    summary: str, 
    start_time: str, 
    end_time: str, 
    description: str = ""
) -> str:
    """
    Add a new event to the user's calendar.
    Returns confirmation or error message.
    """
    try:
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone('Africa/Kampala')  # Uganda timezone (UTC+3)
        
        # If times don't have timezone info, assume they're in local timezone
        if not start_time.endswith('Z') and '+' not in start_time[-6:]:
            # Parse the datetime and localize it
            start_dt = datetime.fromisoformat(start_time)
            start_dt = tz.localize(start_dt)
            start_time = start_dt.isoformat()
            
        if not end_time.endswith('Z') and '+' not in end_time[-6:]:
            end_dt = datetime.fromisoformat(end_time)
            end_dt = tz.localize(end_dt)
            end_time = end_dt.isoformat()
        
        print(f"DEBUG: Adding event with start_time={start_time}, end_time={end_time}")
        
        result = await _calendar_tool.add_event(
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            description=description
        )
        
        if "error" in result:
            return f"Failed to add event: {result['error']}"
        
        if result.get("status") == "success":
            return f"✅ Event '{result['summary']}' successfully added to calendar for {result['start']}"
        
        return f"Event added: {result}"
    
    except Exception as e:
        logger.error(f"Error in add_calendar_event: {e}")
        return f"Error adding event: {str(e)}"

@tool("get_current_or_next_event", args_schema=GetCurrentEventInput)
async def get_current_or_next_event(lookahead_minutes: int = 30) -> str:
    """
    Get the current event or next upcoming event within specified time window.
    Returns event details or a message if no events found.
    """
    try:
        event = await _calendar_tool.get_current_or_next_event(lookahead_minutes=lookahead_minutes)
        
        if not event:
            return f"No events found in the next {lookahead_minutes} minutes."
        
        if "error" in event:
            return f"Error: {event['error']}"
        
        if "message" in event:
            return event["message"]
        
        summary = event.get('summary', 'No title')
        start = event.get('start', 'Unknown time')
        
        return f"📅 Current/Next event: {summary} at {start}"
    
    except Exception as e:
        logger.error(f"Error in get_current_or_next_event: {e}")
        return f"Error getting current event: {str(e)}"

# Helper function to parse natural language time to ISO format
def parse_time_to_iso(time_str: str, date_context: str = None) -> str:
    """
    Parse natural language time to ISO format.
    This is a simple implementation - you might want to use a more robust library like dateutil.
    """
    try:
        # Simple patterns - extend as needed
        now = datetime.now()
        
        # Handle common patterns
        if "today" in time_str.lower():
            # Extract time and use today's date
            # This is simplified - implement proper parsing as needed
            pass
        elif "tomorrow" in time_str.lower():
            # Extract time and use tomorrow's date
            pass
        
        # For now, assume ISO format input
        return time_str
    except Exception:
        # Return as-is if parsing fails
        return time_str

def get_calendar_tools() -> List[BaseTool]:
    """
    Get all calendar tools for integration with LangGraph.
    """
    return [
        list_upcoming_events,
        add_calendar_event,
        get_current_or_next_event
    ]