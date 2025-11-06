# Kylie WhatsApp Agent Workflow Documentation

## Overview
This is an end-to-end WhatsApp agent that uses various AI services and LangGraph for conversation flow management. The agent can handle text, image, and audio inputs/outputs, and has capabilities for calendar management, internet search, and long-term memory.

## Technology Stack
- **Text Generation**: Groq (Llama 3.3 70B)
- **Image Understanding**: Google Cloud Vision API
- **Speech-to-Text**: Whisper (via Groq)
- **Text-to-Speech**: Eleven Labs
- **Image Generation**: Together.ai
- **Long-term Memory**: Qdrant (vector database)
- **Short-term Memory**: SQLite (conversation state)
- **Workflow Management**: LangGraph

## LangGraph Workflow Structure

### Workflow Flow

The workflow follows this sequence:

1. **Memory Extraction Node** → Extracts and stores important information from user messages
2. **Router Node** → Determines the type of response needed (conversation/image/audio/tools/search)
3. **Context Injection Node** → Adds current activity from Kylie's schedule
4. **Memory Injection Node** → Retrieves and injects relevant memories from vector database
5. **Workflow Branch** → Routes to one of:
   - **Conversation Node** → Generates text responses
   - **Image Node** → Generates images with textual responses
   - **Audio Node** → Generates audio responses (TTS)
   - **Tool Calling Node** → Handles calendar operations
   - **Search Node** → Performs internet search and generates responses
6. **Summarize Conversation Node** → Reduces conversation history when it exceeds thresholds

### Node Details

#### 1. Memory Extraction Node
- **Purpose**: Extracts and stores important information from user messages
- **Storage**: Qdrant vector database
- **Information Captured**: Name, occupation, hobbies, preferences, and other relevant personal details
- **Process**: Uses LLM to analyze message importance and format memories

#### 2. Router Node
- **Purpose**: Determines the appropriate response type
- **Outputs**: 
  - `conversation` - Normal text message
  - `image` - Image generation requested
  - `audio` - Audio response requested
  - `tools` - Calendar operations needed
  - `search` - Internet search needed
- **Decision Factors**: Analyzes conversation context and user intent

#### 3. Context Injection Node
- **Purpose**: Adds current activity from Kylie's schedule
- **Schedule Source**: Hardcoded Monday-Friday schedule
- **Output**: `current_activity` and `apply_activity` flag

#### 4. Memory Injection Node
- **Purpose**: Retrieves relevant memories from vector database
- **Search Method**: Semantic search in Qdrant
- **Context**: Based on recent conversation (last 3 messages)
- **Output**: `memory_context` string for character card

#### 5. Conversation Node
- **Purpose**: Generates text responses
- **Context Used**: 
  - Current activity from schedule
  - Memory context from vector database
  - Search results (if available)
  - Conversation summary (if available)
- **Output**: Text message response

#### 6. Image Node
- **Purpose**: Generates images with textual responses
- **Process**:
  1. Creates scenario from conversation context
  2. Generates image using Together.ai
  3. Generates textual response describing the image
- **Output**: Image file path and text response

#### 7. Audio Node
- **Purpose**: Generates audio responses
- **Process**:
  1. Generates text response
  2. Converts to speech using Eleven Labs TTS
- **Output**: Audio buffer (bytes) and text response

#### 8. Tool Calling Node
- **Purpose**: Handles calendar operations
- **Capabilities**:
  - List upcoming events
  - Add calendar events
  - Get current/next event
- **Calendar Integration**: Google Calendar API via direct LangChain tool integration
- **Context**: Uses current date, time, and timezone (Africa/Kampala)

#### 9. Search Node
- **Purpose**: Performs internet search and generates responses with search context
- **Search Provider**: Tavily Search API
- **Process**:
  1. Extracts search query from user message
  2. Performs search using Tavily API
  3. Formats search results
  4. Generates response incorporating search results
- **Output**: Text response with search results context, stores `search_results` in state
- **Use Cases**: Current events, news, recent information, factual queries

#### 10. Summarize Conversation Node
- **Purpose**: Reduces conversation history length
- **Trigger**: When total messages exceed 100 (configurable via `TOTAL_MESSAGES_SUMMARY_TRIGGER`)
- **Process**: 
  - Creates/extends conversation summary
  - Removes old messages (keeps last 75 by default)
- **Output**: Updated summary and reduced message history

## State Graph

The state graph tracks:
- `summary`: Conversation summary string
- `workflow`: Current workflow type (conversation/image/audio/tools/search)
- `audio_buffer`: Audio bytes for TTS
- `image_path`: Path to generated image file
- `current_activity`: Current activity from schedule
- `apply_activity`: Boolean flag for activity application
- `memory_context`: Retrieved memories from vector database
- `search_results`: Formatted search results from Tavily (when search is performed)
- `messages`: Conversation message history (inherited from MessagesState)

## Data Storage

- **Qdrant (Vector Database)**: Stores relevant information extracted from conversations
  - Used for long-term memory retrieval
  - Semantic search capabilities
  - Stores: user preferences, personal details, important facts

- **SQLite (Short-term Memory)**: Stores everything in the state graph
  - Conversation messages
  - State snapshots
  - Checkpointing for conversation continuity

## Calendar Tool Integration

The calendar tool uses **direct LangChain tool integration**:
- **Location**: `calendar/langchain_integration.py`
- **Tools Available**:
  - `list_upcoming_events`: Get upcoming calendar events
  - `add_calendar_event`: Add new events to calendar
  - `get_current_or_next_event`: Get current or next upcoming event
- **Integration Point**: Router detects calendar-related queries → Tool Calling Node → Calendar tools executed

## Search Integration

The search functionality uses Tavily Search API:
- **Location**: `modules/search/tavily_search.py`
- **Integration Point**: Router detects search intent → Search Node → Performs search → Generates response with search context
- **Configuration**: Requires `TAVILY_API_KEY` in environment variables
- **Features**: 
  - Internet search for current information
  - Results formatted and injected into response context
  - Search results stored in state for reference

## Workflow Triggers

### Router Decision Logic:
- **Calendar Keywords**: schedule, calendar, events, meetings, appointments, birthday, "what's on my", etc. → `tools`
- **Search Keywords**: "search for", "what is", "tell me about", "current news", "latest", etc. → `search`
- **Image Requests**: Explicit visual content requests → `image`
- **Audio Requests**: Explicit voice/audio requests → `audio`
- **Default**: Normal conversation → `conversation`

## Summary

The agent is a comprehensive WhatsApp companion that can:
- Have natural conversations with memory
- Generate images based on context
- Provide audio responses
- Manage calendar events
- Search the internet for current information
- Maintain both short-term (SQLite) and long-term (Qdrant) memory
- Adapt responses based on Kylie's schedule and personality

The workflow is designed to be modular and extensible, with clear separation of concerns between different node types. 