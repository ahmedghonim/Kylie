from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from core.prompts import CHARACTER_CARD_PROMPT, ROUTER_PROMPT
from graph.utils.helpers import AsteriskRemovalParser, get_chat_model, get_chat_model_with_tools


class RouterResponse(BaseModel):
    response_type: str = Field(
        description="The response type to give to the user. It must be one of: 'conversation', 'image', 'audio', or 'tools'"
    )


def get_router_chain():
    model = get_chat_model(temperature=0.3).with_structured_output(RouterResponse)

    prompt = ChatPromptTemplate.from_messages(
        [("system", ROUTER_PROMPT), MessagesPlaceholder(variable_name="messages")]
    )

    return prompt | model


def get_character_response_chain(summary: str = "", with_tools: bool = False, search_context: str = ""):
    """
    Get the character response chain, optionally with tools.
    
    Args:
        summary: Conversation summary to include in system message
        with_tools: Whether to bind calendar tools to the model
        search_context: Optional search results context to include
    """
    if with_tools:
        model = get_chat_model_with_tools()
    else:
        model = get_chat_model()
    
    from datetime import datetime
    import pytz
    
    tz = pytz.timezone('Africa/Kampala')
    current_dt = datetime.now(tz)
    current_date = current_dt.strftime('%Y-%m-%d')
    timezone_str = str(tz)
    
    base_system_message = CHARACTER_CARD_PROMPT

    if summary:
        base_system_message += f"\n\nSummary of conversation earlier between Kylie and the user: {summary}"

    # Add tool usage instructions when tools are available
    if with_tools:
        base_system_message += f"""

# Available Tools
You have access to calendar tools that allow you to:
- Check upcoming events on the user's calendar
- Add new events to their calendar  
- Get information about current or next events

CRITICAL CALENDAR RULES:
- TODAY'S DATE IS: {current_date}
- TIMEZONE IS: {timezone_str}
- When user says "today", always use {current_date}
- When user says times like "6pm", combine with {current_date}
- NEVER use wrong dates - always use current date context
- All times should be in {timezone_str} timezone

IMPORTANT: When the user asks about their schedule, calendar, or events, you MUST use the appropriate calendar tools.
For questions like "How's my schedule like next week" or "When's Amber's birthday", use the list_upcoming_events tool.
Always use tools for calendar-related queries - don't provide generic responses.

Use these tools when the user asks about their schedule, wants to add events, or needs reminders.
When using tools, always provide a friendly response along with the tool results.

DO NOT write function calls in text format like <function=...>. Use the proper tool calling mechanism.
"""

    # Add search context if available
    if search_context:
        base_system_message += f"\n\n# Search Results (for reference):\n{search_context}\n\nUse this information to provide accurate, up-to-date responses to the user's query."

    prompt_template = f"""{{system_message}}
    # Current Date and Time Context
    Today's date is: {current_date}
    Current timezone: {timezone_str}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template),
        MessagesPlaceholder(variable_name="messages"),
    ]).partial(system_message=base_system_message)

    chain = prompt | model
    
    # Always return the chain without AsteriskRemovalParser when tools are enabled
    # The parser might interfere with tool call detection
    if not with_tools:
        chain = chain | AsteriskRemovalParser()
    
    return chain