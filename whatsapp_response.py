import logging
import os
from io import BytesIO
from typing import Dict

import httpx
from fastapi import APIRouter, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from graph import graph_builder
from modules.image import ImageToText
from modules.speech import SpeechToText, TextToSpeech
from settings import settings

logger = logging.getLogger(__name__)

# Global module instances
speech_to_text = SpeechToText()
text_to_speech = TextToSpeech()
image_to_text = ImageToText()

# Router for WhatsApp response
whatsapp_router = APIRouter()

# WhatsApp API credentials
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Add a simple in-memory store to prevent duplicate processing
processed_messages = set()


@whatsapp_router.api_route("/whatsapp_response", methods=["GET", "POST"])
async def whatsapp_handler(request: Request) -> Response:
    """Handles incoming messages and status updates from the WhatsApp Cloud API."""

    if request.method == "GET":
        params = request.query_params
        if params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN"):
            return Response(content=params.get("hub.challenge"), status_code=200)
        return Response(content="Verification token mismatch", status_code=403)

    try:
        data = await request.json()
        logger.info(f"Received webhook data: {data}")
        
        change_value = data["entry"][0]["changes"][0]["value"]
        
        if "messages" in change_value:
            message = change_value["messages"][0]
            message_id = message.get("id")
            from_number = message["from"]
            
            # Prevent duplicate processing
            if message_id in processed_messages:
                logger.info(f"Message {message_id} already processed, skipping")
                return Response(content="Message already processed", status_code=200)
            
            processed_messages.add(message_id)
            # Keep only last 1000 message IDs to prevent memory issues
            if len(processed_messages) > 1000:
                processed_messages.clear()
            
            session_id = from_number

            # Get user message and handle different message types
            content = ""
            if message["type"] == "audio":
                content = await process_audio_message(message)
            elif message["type"] == "image":
                # Get image caption if any
                content = message.get("image", {}).get("caption", "")
                logger.info(f"Received image message. Caption: {content}")
                
                # Download and analyze image
                try:
                    image_id = message["image"]["id"]
                    logger.info(f"Downloading image with ID: {image_id}")
                    image_bytes = await download_media(image_id)
                    logger.info(f"Downloaded image successfully. Size: {len(image_bytes)} bytes")
                    
                    # Analyze the image
                    description = await image_to_text.analyze_image(
                        image_bytes,
                        "Please describe what you see in this image in the context of our conversation.",
                    )
                    logger.info(f"Image analysis successful. Description length: {len(description)}")
                    content += f"\n[Image Analysis: {description}]"
                except Exception as e:
                    logger.error(f"Failed to analyze image: {e}", exc_info=True)
                    # Still include caption if available, but mark that image analysis failed
                    if not content:
                        content = "[Image received but could not be analyzed]"
            else:
                content = message["text"]["body"]

            logger.info(f"Processing message from {from_number}: {content}")

            try:
                async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as short_term_memory:
                    graph = graph_builder.compile(checkpointer=short_term_memory)
                    await graph.ainvoke(
                        {"messages": [HumanMessage(content=content)]},
                        {"configurable": {"thread_id": session_id}},
                    )

                    # Get the workflow type and response from the state
                    output_state = await graph.aget_state(config={"configurable": {"thread_id": session_id}})

                workflow = output_state.values.get("workflow", "conversation")
                response_message = output_state.values["messages"][-1].content

                # Handle different response types based on workflow
                success = False
                if workflow == "audio":
                    audio_buffer = output_state.values["audio_buffer"]
                    success = await send_response(from_number, response_message, "audio", audio_buffer)
                elif workflow == "image":
                    image_path = output_state.values["image_path"]
                    with open(image_path, "rb") as f:
                        image_data = f.read()
                    success = await send_response(from_number, response_message, "image", image_data)
                else:
                    success = await send_response(from_number, response_message, "text")

                if success:
                    logger.info("Message sent successfully")
                    return Response(content="Message processed successfully", status_code=200)
                else:
                    logger.error("Failed to send message to WhatsApp API")
                    # Still return 200 to prevent WhatsApp from retrying
                    return Response(content="Message processed but failed to send", status_code=200)

            except Exception as e:
                logger.error(f"Error processing graph: {e}", exc_info=True)
                # Return 200 to prevent retry loop
                return Response(content="Graph processing error", status_code=200)

        elif "statuses" in change_value:
            logger.info("Status update received")
            return Response(content="Status update received", status_code=200)

        else:
            logger.warning("Unknown event type received")
            return Response(content="Unknown event type", status_code=200)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Return 200 to prevent WhatsApp from retrying
        return Response(content="Webhook processing error", status_code=200)


async def download_media(media_id: str) -> bytes:
    """Download media from WhatsApp."""
    if not WHATSAPP_TOKEN:
        logger.error("WHATSAPP_TOKEN is not set in environment variables")
        raise ValueError(
            "WHATSAPP_TOKEN is not set. Please check your .env file and ensure WHATSAPP_TOKEN is configured."
        )
    
    if len(WHATSAPP_TOKEN) < 10:
        logger.warning(f"WHATSAPP_TOKEN appears to be invalid (too short: {len(WHATSAPP_TOKEN)} chars)")
    
    media_metadata_url = f"https://graph.facebook.com/v21.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info(f"Fetching media metadata from: {media_metadata_url}")
        logger.debug(f"Using token: {WHATSAPP_TOKEN[:10]}...{WHATSAPP_TOKEN[-10:] if len(WHATSAPP_TOKEN) > 20 else '***'}")
        
        try:
            metadata_response = await client.get(media_metadata_url, headers=headers)
            
            # Check for 401 Unauthorized specifically
            if metadata_response.status_code == 401:
                error_detail = metadata_response.text
                logger.error(f"Facebook API 401 Unauthorized error: {error_detail}")
                logger.error(
                    "Your WHATSAPP_TOKEN may be expired, invalid, or missing required permissions. "
                    "Please check:\n"
                    "1. The token is valid in your .env file\n"
                    "2. The token hasn't expired (Facebook tokens expire)\n"
                    "3. The token has the required permissions for media access\n"
                    "4. You're using the correct token for your WhatsApp Business API account"
                )
            
            metadata_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(
                    f"Authentication failed with Facebook API. "
                    f"Please verify your WHATSAPP_TOKEN is correct and has not expired."
                )
            raise
        metadata = metadata_response.json()
        logger.info(f"Media metadata: {metadata}")
        
        download_url = metadata.get("url")
        if not download_url:
            raise ValueError(f"No download URL found in metadata: {metadata}")

        logger.info(f"Downloading media from: {download_url}")
        media_response = await client.get(download_url, headers=headers)
        media_response.raise_for_status()
        
        content = media_response.content
        logger.info(f"Downloaded media successfully. Size: {len(content)} bytes")
        return content


async def process_audio_message(message: Dict) -> str:
    """Download and transcribe audio message."""
    audio_id = message["audio"]["id"]
    media_metadata_url = f"https://graph.facebook.com/v21.0/{audio_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    async with httpx.AsyncClient() as client:
        metadata_response = await client.get(media_metadata_url, headers=headers)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        download_url = metadata.get("url")

    # Download the audio file
    async with httpx.AsyncClient() as client:
        audio_response = await client.get(download_url, headers=headers)
        audio_response.raise_for_status()

    # Prepare for transcription
    audio_buffer = BytesIO(audio_response.content)
    audio_buffer.seek(0)
    audio_data = audio_buffer.read()

    return await speech_to_text.transcribe(audio_data)


async def send_response(
    from_number: str,
    response_text: str,
    message_type: str = "text",
    media_content: bytes = None,
) -> bool:
    """Send response to user via WhatsApp API."""
    
    # Validate response_text is not empty
    if not response_text or response_text.strip() == "":
        logger.warning(f"Empty response_text detected. Setting default message.")
        response_text = "I'm processing your request. Let me get back to you!"
        
    # Validate credentials first
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.error("Missing WhatsApp credentials")
        return False
    
    print(f"DEBUG: Sending message type: {message_type}")
    print(f"DEBUG: Response text: '{response_text}'")
    print(f"DEBUG: Response text length: {len(response_text) if response_text else 0}")
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    if message_type in ["audio", "image"]:
        try:
            mime_type = "audio/mpeg" if message_type == "audio" else "image/png"
            media_buffer = BytesIO(media_content)
            media_id = await upload_media(media_buffer, mime_type)
            json_data = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": message_type,
                message_type: {"id": media_id},
            }

            # Add caption for images
            if message_type == "image":
                json_data["image"]["caption"] = response_text
        except Exception as e:
            logger.error(f"Media upload failed, falling back to text: {e}")
            message_type = "text"

    if message_type == "text":
        json_data = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "text",
            "text": {"body": response_text},
        }

    logger.info(f"Sending to WhatsApp API - Headers: {headers}")
    logger.info(f"Sending to WhatsApp API - Payload: {json_data}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
                headers=headers,
                json=json_data,
            )
            
            logger.info(f"WhatsApp API response status: {response.status_code}")
            logger.info(f"WhatsApp API response body: {response.text}")
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
                return False
                
    except httpx.TimeoutException:
        logger.error("Timeout when sending message to WhatsApp API")
        return False
    except Exception as e:
        logger.error(f"Exception when sending message to WhatsApp API: {e}")
        return False


async def upload_media(media_content: BytesIO, mime_type: str) -> str:
    """Upload media to WhatsApp servers."""
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    files = {"file": ("response.mp3", media_content, mime_type)}
    data = {"messaging_product": "whatsapp", "type": mime_type}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/media",
            headers=headers,
            files=files,
            data=data,
        )
        result = response.json()

    if "id" not in result:
        raise Exception(f"Failed to upload media: {result}")
    return result["id"]