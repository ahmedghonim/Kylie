import base64
import logging
import os
from typing import Optional, Union

import httpx
from core.exceptions import ImageToTextError
from settings import settings


class ImageToText:
    """A class to handle image-to-text conversion using Google Cloud Vision API (Imagen-Visual Captioning)."""

    REQUIRED_ENV_VARS = ["GOOGLE_CLOUD_API_KEY"]

    def __init__(self):
        """Initialize the ImageToText class."""
        self._validate_env_vars()
        self.logger = logging.getLogger(__name__)
        self.api_key = settings.GOOGLE_CLOUD_API_KEY
        # Google Cloud Vision API endpoint for image annotation
        self.api_url = "https://vision.googleapis.com/v1/images:annotate"

    def _validate_env_vars(self) -> None:
        """Validate that environment variables are set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not getattr(settings, var, None)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please set GOOGLE_CLOUD_API_KEY in your .env file."
            )

    async def analyze_image(self, image_data: Union[str, bytes], prompt: str = "") -> str:
        """Analyze an image using Google Cloud Vision API (Visual Captioning).

        Args:
            image_data: Either a file path (str) or binary image data (bytes)
            prompt: Optional prompt/question about the image (not used with Vision API, but kept for compatibility)

        Returns:
            str: Description or analysis of the image

        Raises:
            ValueError: If the image data is empty or invalid
            ImageToTextError: If the image analysis fails
        """
        try:
            # Handle file path
            if isinstance(image_data, str):
                if not os.path.exists(image_data):
                    raise ValueError(f"Image file not found: {image_data}")
                with open(image_data, "rb") as f:
                    image_bytes = f.read()
            else:
                image_bytes = image_data

            if not image_bytes:
                raise ValueError("Image data cannot be empty")

            # Detect image format from magic bytes
            mime_type = "image/jpeg"  # default
            if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                mime_type = "image/png"
            elif image_bytes.startswith(b'\xff\xd8\xff'):
                mime_type = "image/jpeg"
            elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
                mime_type = "image/webp"
            elif image_bytes.startswith(b'GIF8'):
                mime_type = "image/gif"

            self.logger.info(f"Detected image format: {mime_type}, size: {len(image_bytes)} bytes")
            self.logger.info("Using Google Cloud Vision API (Imagen-Visual Captioning)")

            # Encode image to base64 for Google Cloud Vision API
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # Prepare request payload for Google Cloud Vision API
            # Using Visual Captioning feature (Imagen-Visual)
            # Note: Visual Captioning is available through LABEL_DETECTION and OBJECT_LOCALIZATION
            # We'll combine these to generate a comprehensive caption
            payload = {
                "requests": [
                    {
                        "image": {
                            "content": image_base64
                        },
                        "features": [
                            {
                                "type": "LABEL_DETECTION",
                                "maxResults": 10
                            },
                            {
                                "type": "OBJECT_LOCALIZATION",
                                "maxResults": 10
                            },
                            {
                                "type": "TEXT_DETECTION",
                                "maxResults": 10
                            }
                        ]
                    }
                ]
            }

            headers = {
                "Content-Type": "application/json",
            }

            # Google Cloud Vision API uses API key as query parameter
            params = {
                "key": self.api_key
            }

            self.logger.info(f"Making API call to Google Cloud Vision API")
            self.logger.info(f"Image size: {len(image_bytes)} bytes, MIME type: {mime_type}")

            # Make the API call to Google Cloud Vision API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    params=params,
                    json=payload,
                )

                self.logger.info(f"Google Cloud Vision API response status: {response.status_code}")

                if response.status_code != 200:
                    error_text = response.text
                    self.logger.error(f"Google Cloud Vision API error: {response.status_code} - {error_text}")
                    
                    # Parse error details if available
                    try:
                        error_json = response.json()
                        error_info = error_json.get("error", {})
                        error_message = error_info.get("message", error_text)
                        error_code = error_info.get("code", response.status_code)
                        error_reason = None
                        
                        # Check for specific error reasons
                        details = error_info.get("details", [])
                        for detail in details:
                            if detail.get("@type") == "type.googleapis.com/google.rpc.ErrorInfo":
                                error_reason = detail.get("reason")
                                break
                        
                        # Provide specific guidance for common errors
                        if error_code == 403 and error_reason == "API_KEY_SERVICE_BLOCKED":
                            error_guidance = (
                                "\n\n❌ Google Cloud Vision API is BLOCKED for your API key.\n\n"
                                "To fix this, you need to:\n"
                                "1. Enable the Vision API in Google Cloud Console:\n"
                                "   - Go to: https://console.cloud.google.com/apis/library/vision.googleapis.com\n"
                                "   - Select your project (project ID: 995856091136)\n"
                                "   - Click 'Enable'\n\n"
                                "2. Check API key restrictions:\n"
                                "   - Go to: https://console.cloud.google.com/apis/credentials\n"
                                "   - Find your API key\n"
                                "   - Make sure 'Cloud Vision API' is in the allowed APIs list\n"
                                "   - Or remove API restrictions temporarily for testing\n\n"
                                "3. Enable billing (if required):\n"
                                "   - Vision API may require billing to be enabled\n"
                                "   - Go to: https://console.cloud.google.com/billing\n"
                                "   - Link a billing account to your project\n\n"
                                "4. Verify the API key has correct permissions\n"
                            )
                            raise ImageToTextError(
                                f"Google Cloud Vision API error ({error_code}): {error_message}{error_guidance}"
                            )
                        else:
                            raise ImageToTextError(
                                f"Google Cloud Vision API error ({error_code}): {error_message}"
                            )
                    except Exception:
                        raise ImageToTextError(
                            f"Google Cloud Vision API error ({response.status_code}): {error_text}"
                        )

                result = response.json()

                self.logger.info(f"Google Cloud Vision API response received: {type(result)}")

                # Extract caption/description from Google Cloud Vision API response
                # Combine labels, objects, and text to create a comprehensive caption
                description_parts = []

                if "responses" in result and len(result["responses"]) > 0:
                    response_data = result["responses"][0]

                    # Extract labels (descriptive tags) - these form the main caption
                    labels = response_data.get("labelAnnotations", [])
                    if labels:
                        # Get top labels with their scores
                        top_labels = []
                        for label in labels[:5]:
                            desc = label.get("description", "")
                            score = label.get("score", 0)
                            if desc:
                                top_labels.append(desc)
                        if top_labels:
                            description_parts.append(", ".join(top_labels))

                    # Extract localized objects (what's in the image)
                    localized_objects = response_data.get("localizedObjectAnnotations", [])
                    if localized_objects:
                        object_names = [obj.get("name", "") for obj in localized_objects[:5] if obj.get("name")]
                        if object_names:
                            description_parts.append(f"Objects: {', '.join(object_names)}")

                    # Extract detected text (if any text in image)
                    text_annotations = response_data.get("textAnnotations", [])
                    if text_annotations and len(text_annotations) > 0:
                        # First annotation contains all detected text
                        full_text = text_annotations[0].get("description", "")
                        if full_text and len(full_text.strip()) > 0:
                            # Only add text if it's meaningful (not just a few characters)
                            if len(full_text.strip()) > 3:
                                description_parts.append(f"Text: {full_text[:100]}")

                # Combine all parts into a natural description
                if description_parts:
                    # Create a natural sentence from the parts
                    if len(description_parts) == 1:
                        description = description_parts[0]
                    else:
                        # Join with appropriate punctuation
                        description = ". ".join(description_parts)
                else:
                    # Fallback: use labels or create a generic description
                    if "responses" in result and len(result["responses"]) > 0:
                        response_data = result["responses"][0]
                        labels = response_data.get("labelAnnotations", [])
                        if labels:
                            description = labels[0].get("description", "Image analyzed but no description available")
                        else:
                            description = "Image analyzed but no specific details were detected"
                    else:
                        description = "Unable to generate image description"

                if not description or description.strip() == "":
                    raise ImageToTextError("Empty description received from Google Cloud Vision API")

                self.logger.info(f"Generated image description: {description[:100]}...")
                return description.strip()

        except ImageToTextError:
            # Re-raise our custom errors
            raise
        except httpx.TimeoutException as e:
            self.logger.error(f"Request timeout: {e}")
            raise ImageToTextError(f"Request timeout: {str(e)}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error in analyze_image: {e}", exc_info=True)
            raise ImageToTextError(f"Failed to analyze image: {str(e)}") from e
