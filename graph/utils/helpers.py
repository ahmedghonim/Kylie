import re
from typing import List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq

from modules.image.image_to_text import ImageToText
from modules.image.text_to_image import TextToImage
from modules.speech import TextToSpeech
from modules.search import TavilySearch
from mycalendar.langchain_integration import get_calendar_tools
from settings import settings


def get_chat_model(temperature: float = 0.7):
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.TEXT_MODEL_NAME,
        temperature=temperature,
    )


def get_chat_model_with_tools(temperature: float = 0.7):
    """Get chat model with calendar tools bound to it."""
    model = get_chat_model(temperature=temperature)
    tools = get_calendar_tools()
    return model.bind_tools(tools)


def get_text_to_speech_module():
    return TextToSpeech()


def get_search_module():
    return TavilySearch()


def get_text_to_image_module():
    return TextToImage()


def get_image_to_text_module():
    return ImageToText()


def get_available_tools() -> List[BaseTool]:
    """Get all available tools for the agent."""
    return get_calendar_tools()


def remove_asterisk_content(text: str) -> str:
    """Remove content between asterisks from the text."""
    return re.sub(r"\*.*?\*", "", text).strip()


class AsteriskRemovalParser(StrOutputParser):
    def parse(self, text):
        return remove_asterisk_content(super().parse(text))