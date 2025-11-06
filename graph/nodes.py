import os
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig

from .state import AICompanionState
from graph.utils.chains import (
    get_character_response_chain,
    get_router_chain,
)
from graph.utils.helpers import (
    get_chat_model,
    get_text_to_image_module,
    get_text_to_speech_module,
    get_search_module,
)
from modules.memory.long_term.memory_manager import get_memory_manager
from modules.schedules.context_generation import ScheduleContextGenerator
from settings import settings


async def router_node(state: AICompanionState):
    chain = get_router_chain()
    response = await chain.ainvoke({"messages": state["messages"][-settings.ROUTER_MESSAGES_TO_ANALYZE :]})
    return {"workflow": response.response_type}


def context_injection_node(state: AICompanionState):
    schedule_context = ScheduleContextGenerator.get_current_activity()
    if schedule_context != state.get("current_activity", ""):
        apply_activity = True
    else:
        apply_activity = False
    return {"apply_activity": apply_activity, "current_activity": schedule_context}


async def conversation_node(state: AICompanionState, config: RunnableConfig):
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    search_context = state.get("search_results", "")

    chain = get_character_response_chain(
        state.get("summary", ""),
        with_tools=False,
        search_context=search_context
    )

    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "current_activity": current_activity,
            "memory_context": memory_context,
        },
        config,
    )
    return {"messages": AIMessage(content=response)}


async def image_node(state: AICompanionState, config: RunnableConfig):
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")

    chain = get_character_response_chain(state.get("summary", ""))
    text_to_image_module = get_text_to_image_module()

    scenario = await text_to_image_module.create_scenario(state["messages"][-5:])
    os.makedirs("generated_images", exist_ok=True)
    img_path = f"generated_images/image_{str(uuid4())}.png"
    await text_to_image_module.generate_image(scenario.image_prompt, img_path)

    # Inject the image prompt information as an AI message
    scenario_message = HumanMessage(content=f"<image attached by Ava generated from prompt: {scenario.image_prompt}>")
    updated_messages = state["messages"] + [scenario_message]

    response = await chain.ainvoke(
        {
            "messages": updated_messages,
            "current_activity": current_activity,
            "memory_context": memory_context,
        },
        config,
    )

    return {"messages": AIMessage(content=response), "image_path": img_path}


async def audio_node(state: AICompanionState, config: RunnableConfig):
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")

    chain = get_character_response_chain(state.get("summary", ""))
    text_to_speech_module = get_text_to_speech_module()

    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "current_activity": current_activity,
            "memory_context": memory_context,
        },
        config,
    )
    output_audio = await text_to_speech_module.synthesize(response)

    return {"messages": response, "audio_buffer": output_audio}


async def summarize_conversation_node(state: AICompanionState):
    model = get_chat_model()
    summary = state.get("summary", "")

    if summary:
        summary_message = (
            f"This is summary of the conversation to date between Ava and the user: {summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )
    else:
        summary_message = (
            "Create a summary of the conversation above between Ava and the user. "
            "The summary must be a short description of the conversation so far, "
            "but that captures all the relevant information shared between Ava and the user:"
        )

    messages = state["messages"] + [HumanMessage(content=summary_message)]
    response = await model.ainvoke(messages)

    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][: -settings.TOTAL_MESSAGES_AFTER_SUMMARY]]
    return {"summary": response.content, "messages": delete_messages}


async def memory_extraction_node(state: AICompanionState):
    """Extract and store important information from the last message."""
    if not state["messages"]:
        return {}

    memory_manager = get_memory_manager()
    await memory_manager.extract_and_store_memories(state["messages"][-1])
    return {}


def memory_injection_node(state: AICompanionState):
    """Retrieve and inject relevant memories into the character card."""
    memory_manager = get_memory_manager()

    # Get relevant memories based on recent conversation
    recent_context = " ".join([m.content for m in state["messages"][-3:]])
    memories = memory_manager.get_relevant_memories(recent_context)

    # Format memories for the character card
    memory_context = memory_manager.format_memories_for_prompt(memories)

    return {"memory_context": memory_context}


async def search_node(state: AICompanionState, config: RunnableConfig):
    """
    Node for handling internet search operations using Tavily.
    This node performs search and then routes to conversation node with search results.
    """
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    
    # Extract search query from user's last message
    user_message = state["messages"][-1].content if state["messages"] else ""
    
    # Perform search
    search_module = get_search_module()
    search_results_list = await search_module.search(query=user_message, max_results=5)
    
    # Format search results
    formatted_results = search_module.format_search_results(search_results_list)
    
    # Store search results in state
    search_results_str = formatted_results
    
    # generate response with search context
    chain = get_character_response_chain(
        state.get("summary", ""), 
        with_tools=False,
        search_context=search_results_str
    )
    
    # Create a context message with search results
    from langchain_core.messages import SystemMessage
    search_context_msg = SystemMessage(content=f"User asked: {user_message}\n\nSearch Results:\n{search_results_str}")
    
    # Generate response using search results
    response = await chain.ainvoke(
        {
            "messages": state["messages"] + [search_context_msg],
            "current_activity": current_activity,
            "memory_context": memory_context,
        },
        config,
    )
    
    return {
        "messages": AIMessage(content=response),
        "search_results": search_results_str
    }


async def tool_calling_node(state: AICompanionState, config: RunnableConfig):
    """
    Node for handling tool calls (calendar operations).
    This node will be used when the agent needs to use tools.
    """
    from datetime import datetime
    import pytz
    
    tz = pytz.timezone('Africa/Kampala')
    current_dt = datetime.now(tz)
    current_date = current_dt.strftime('%Y-%m-%d')
    current_time = current_dt.strftime('%H:%M')
    
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")

    print(f"DEBUG: tool_calling_node - Current date: {current_date}")
    print(f"DEBUG: tool_calling_node - Current time: {current_time}")
    print(f"DEBUG: tool_calling_node - Current activity: {current_activity}")
    print(f"DEBUG: tool_calling_node - Memory context: {memory_context}")
    print(f"DEBUG: tool_calling_node - Last message: {state['messages'][-1].content}")

    # Use the chain with tools enabled
    chain = get_character_response_chain(state.get("summary", ""), with_tools=True)

    print(f"DEBUG: Chain created with tools enabled")

    enhanced_messages = state["messages"].copy()
    
    # Add a system-like context message to help with date understanding
    from langchain_core.messages import SystemMessage
    date_context_msg = SystemMessage(content=f"Current date: {current_date}, Current time: {current_time}, Timezone: Africa/Kampala")
    enhanced_messages.insert(-1, date_context_msg)
    
    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "current_activity": current_activity,
            "memory_context": memory_context,
        },
        config,
    )
    
    print(f"DEBUG: Initial response type: {type(response)}")
    print(f"DEBUG: Initial response: {response}")
    print(f"DEBUG: Initial response content: {getattr(response, 'content', 'No content attr')}")
    print(f"DEBUG: Has tool_calls: {hasattr(response, 'tool_calls')}")
    if hasattr(response, 'tool_calls'):
        print(f"DEBUG: Tool calls: {response.tool_calls}")
        print(f"DEBUG: Tool calls length: {len(response.tool_calls) if response.tool_calls else 0}")
    
    # Handle tool calls if present
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"DEBUG: Processing {len(response.tool_calls)} tool calls")
        
        # The model wants to use tools
        from langchain_core.messages import ToolMessage
        from mycalendar.langchain_integration import get_calendar_tools
        
        tools = {tool.name: tool for tool in get_calendar_tools()}
        print(f"DEBUG: Available tools: {list(tools.keys())}")
        
        tool_messages = []
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            print(f"DEBUG: Executing tool {tool_name} with args {tool_args}")
            
            if tool_name in tools:
                try:
                    # Execute the tool using invoke method
                    tool_result = await tools[tool_name].ainvoke(tool_args)
                    print(f"DEBUG: Tool result: {tool_result}")
                    tool_messages.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call["id"]
                        )
                    )
                except Exception as e:
                    print(f"DEBUG: Tool execution error: {e}")
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error executing {tool_name}: {str(e)}",
                            tool_call_id=tool_call["id"]
                        )
                    )
            else:
                print(f"DEBUG: Tool {tool_name} not found in available tools")
        
        # Get final response after tool execution
        updated_messages = state["messages"] + [response] + tool_messages
        print(f"DEBUG: Getting final response with {len(tool_messages)} tool results")
        
        final_response = await chain.ainvoke(
            {
                "messages": updated_messages,
                "current_activity": current_activity,
                "memory_context": memory_context,
            },
            config,
        )
        
        print(f"DEBUG: Final response type: {type(final_response)}")
        print(f"DEBUG: Final response content: {getattr(final_response, 'content', 'No content attr')}")
        
        # Ensure we return an AIMessage with content
        from langchain_core.messages import AIMessage
        if hasattr(final_response, 'content') and final_response.content:
            return {"messages": final_response}
        else:
            # Fallback message if response is empty
            return {"messages": AIMessage(content="I've checked your calendar. Let me know if you need anything else!")}
    else:
        # No tool calls, this means the model didn't decide to use tools
        print(f"DEBUG: No tool calls generated - this might indicate an issue with tool binding")
        print(f"DEBUG: Response content: {getattr(response, 'content', 'No content')}")
        
        # Check if we have a valid text response
        if hasattr(response, 'content') and response.content and response.content.strip():
            return {"messages": response}
        else:
            # Generate a calendar response manually since tools weren't called
            print(f"DEBUG: Manually calling calendar tool since model didn't generate tool calls")
            try:
                from mycalendar.langchain_integration import list_upcoming_events
                # Use invoke method instead of __call__, and pass arguments correctly
                calendar_result = await list_upcoming_events.ainvoke({"max_results": 10})
                from langchain_core.messages import AIMessage
                return {"messages": AIMessage(content=f"Let me check your schedule for you!\n\n{calendar_result}")}
            except Exception as e:
                print(f"DEBUG: Manual calendar call failed: {e}")
                from langchain_core.messages import AIMessage
                return {"messages": AIMessage(content="I'd like to help you check your schedule, but I'm having trouble accessing your calendar right now. Please try again!")}