from langgraph.graph import END
from typing_extensions import Literal

from .state import AICompanionState
from settings import settings


def should_summarize_conversation(
    state: AICompanionState,
) -> Literal["summarize_conversation_node", "__end__"]:
    messages = state["messages"]

    if len(messages) > settings.TOTAL_MESSAGES_SUMMARY_TRIGGER:
        return "summarize_conversation_node"

    return END


def select_workflow(
    state: AICompanionState,
) -> Literal["conversation_node", "image_node", "audio_node", "tool_calling_node", "search_node"]:
    workflow = state["workflow"]

    if workflow == "image":
        return "image_node"
    elif workflow == "audio":
        return "audio_node"
    elif workflow == "tools":
        return "tool_calling_node"
    elif workflow == "search":
        return "search_node"
    else:
        return "conversation_node"