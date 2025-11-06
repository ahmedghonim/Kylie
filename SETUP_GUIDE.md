# Setup Guide

This guide will walk you through setting up Kylie from scratch, including creating a virtual environment, installing dependencies, obtaining API keys, and configuring WhatsApp integration.

## 1. Create a Virtual Environment

A virtual environment isolates your project's dependencies from your system Python packages.

**Steps:**

1. **Navigate to the project directory:**
   ```bash
   cd path/to/Kylie
   ```

2. **Create the virtual environment:**
   ```bash
   python -m venv venv
   ```
   (On some systems, use `python3` instead of `python`)

3. **Activate the virtual environment:**
   - **Windows:**
     ```bash
     venv\Scripts\activate
     ```
   - **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

   Your terminal prompt should now show `(venv)` indicating the environment is active.

## 2. Install Required Packages

With the virtual environment activated, install all dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs all packages listed in `requirements.txt` including FastAPI, LangChain, LangGraph, and other dependencies.

## 3. Obtain API Keys

You'll need API keys from several services. 

**Note:** If there's a `.env.example` file in the project, you can use it as a template. Copy it to `.env` and fill in your actual API keys.

Create a `.env` file in the project root directory and add your keys there.

### 3.1 Groq API Key (for LLM and Speech-to-Text)

1. Go to [https://console.groq.com/](https://console.groq.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key and add to `.env`:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

### 3.2 ElevenLabs API Key and Voice ID (for Text-to-Speech)

1. Go to [https://elevenlabs.io/](https://elevenlabs.io/)
2. Sign up or log in
3. Navigate to your profile settings or API section
4. Generate an API key
5. To get a Voice ID:
   - Go to the Voice Library
   - Select a voice you want to use
   - Copy the Voice ID from the voice settings
6. Add to `.env`:
   ```env
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ELEVENLABS_VOICE_ID=your_voice_id_here
   ```

### 3.3 Together AI API Key (for Image Generation)

1. Go to [https://together.ai/](https://together.ai/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Add to `.env`:
   ```env
   TOGETHER_API_KEY=your_together_api_key_here
   ```

### 3.4 Google Cloud API Key (for Image Understanding)

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Cloud Vision API**:
   - Go to "APIs & Services" > "Library"
   - Search for "Cloud Vision API"
   - Click "Enable"
4. Create an API key:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the generated key
5. Do not Restrict the API key to Cloud Vision API only for testing purposes
6. Add to `.env`:
   ```env
   GOOGLE_CLOUD_API_KEY=your_google_cloud_api_key_here
   ```

### 3.5 Tavily API Key (for Internet Search)

1. Go to [https://tavily.com/](https://tavily.com/)
2. Sign up or log in
3. Navigate to your dashboard to get your API key
4. Add to `.env`:
   ```env
   TAVILY_API_KEY=your_tavily_api_key_here
   ```

### 3.6 Qdrant Setup (for Long-term Memory)

You have two options:

**Option A: Qdrant Cloud (Recommended for beginners)**

1. Go to [https://cloud.qdrant.io/](https://cloud.qdrant.io/)
2. Sign up for a free account
3. Create a new cluster
4. Get your cluster URL and API key from the dashboard
5. Add to `.env`:
   ```env
   QDRANT_URL=your_cluster_url_here
   QDRANT_API_KEY=your_qdrant_api_key_here
   ```

**Option B: Local Qdrant (Advanced)**

1. Install Qdrant locally or run via Docker
2. Add to `.env`:
   ```env
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   QDRANT_URL=http://localhost:6333
   ```

## 4. WhatsApp Business API Setup

### 4.1 Create a Meta App

1. Go to [https://developers.facebook.com/](https://developers.facebook.com/)
2. Click "My Apps" > "Create App"
3. Select "Business" as the app type
4. Fill in app details and create the app

### 4.2 Add WhatsApp Product

1. In your app dashboard, click "Add Product"
2. Find "WhatsApp" and click "Set Up"
3. Follow the setup wizard

### 4.3 Get Access Token and Phone Number ID

1. In the WhatsApp section, go to "API Setup"
2. You'll see:
   - **Temporary Access Token**: Copy this (it expires in 24 hours, you'll need to generate a permanent one later)
   - **Phone Number ID**: Copy this number
3. Add to `.env`:
   ```env
   WHATSAPP_TOKEN=your_temporary_access_token_here
   WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
   ```

### 4.4 Set Up Webhook Verification Token

1. In the WhatsApp section, go to "Configuration"
2. Under "Webhook", click "Edit"
3. Create a verification token (any random string, e.g., `my_secure_verify_token_123`)
4. Add to `.env`:
   ```env
   WHATSAPP_VERIFY_TOKEN=your_verification_token_here
   ```

**Note:** You'll configure the webhook URL in the next section after setting up ngrok.

## 5. Google Calendar API Setup (First Time)

### 5.1 Enable Google Calendar API

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Select your project (or create a new one)
3. Go to "APIs & Services" > "Library"
4. Search for "Google Calendar API"
5. Click "Enable"

### 5.2 Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" (unless you have a Google Workspace)
   - Fill in required app information
   - Add your email as a test user
   - Save and continue through the steps
4. Back in Credentials, create OAuth client ID:
   - Application type: "Desktop app" or "Other"
   - Name it (e.g., "Kylie Calendar")
   - Click "Create"
5. Download the credentials JSON file
6. Rename it to `credentials.json` and place it in the `mycalendar/` directory

### 5.3 First-Time Authorization

1. Run your application (see section 7)
2. The first time the calendar tool is used, it will:
   - Open a browser window
   - Ask you to sign in with your Google account
   - Request permission to access your calendar
   - Generate a `token.json` file in the `mycalendar/` directory
3. This `token.json` file stores your authorization and will be reused for future requests

## 6. Set Up ngrok for Local Development

ngrok creates a public URL that tunnels to your local server, which is required for WhatsApp webhooks.

### 6.1 Install ngrok

1. Download ngrok from [https://ngrok.com/download](https://ngrok.com/download)
2. Extract the executable to a folder in your PATH (or add it to PATH)
3. Verify installation:
   ```bash
   ngrok version
   ```

### 6.2 Authenticate ngrok

1. Sign up for a free account at [https://ngrok.com/](https://ngrok.com/)
2. Get your authtoken from the dashboard
3. Authenticate:
   ```bash
   ngrok config add-authtoken your_authtoken_here
   ```

### 6.3 Start ngrok Tunnel

1. Make sure your application will run on port 8000 (default)
2. In a new terminal window, run:
   ```bash
   ngrok http 8000
   ```
3. You'll see output like:
   ```
   Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
   ```
4. Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

### 6.4 Configure WhatsApp Webhook

1. Go back to your Meta app dashboard
2. Navigate to WhatsApp > Configuration
3. Under "Webhook", click "Edit"
4. Set the **Callback URL** to:
   ```
   https://your-ngrok-url.ngrok-free.app/whatsapp_response
   ```
   Replace `your-ngrok-url` with your actual ngrok URL
5. Set the **Verify Token** to the same value you set in `.env` (`WHATSAPP_VERIFY_TOKEN`)
6. Click "Verify and Save"
7. Subscribe to message events by clicking "Manage" next to "Webhook fields" and selecting "messages"

**Important:** 
- The ngrok URL changes each time you restart ngrok (unless you have a paid plan)
- You'll need to update the webhook URL in Meta whenever you restart ngrok
- Keep ngrok running while testing your application

## 7. Complete .env File

Your `.env` file should now look like this:

```env
# Groq (LLM and STT)
GROQ_API_KEY=your_groq_api_key

# ElevenLabs (TTS)
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_voice_id

# Together AI (Image Generation)
TOGETHER_API_KEY=your_together_api_key

# Google Cloud (Image Understanding)
GOOGLE_CLOUD_API_KEY=your_google_cloud_api_key

# Tavily (Search)
TAVILY_API_KEY=your_tavily_api_key

# Qdrant (Memory)
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key

# WhatsApp
WHATSAPP_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=your_verify_token
```

## 8. Run the Application

1. **Make sure your virtual environment is activated**

2. **Start the application:**
   ```bash
   uvicorn main:app --reload
   ```
   
   Or if you have a run script:
   ```bash
   python main.py
   ```
   
   The application will start on `http://localhost:8000`

3. **Keep ngrok running** in a separate terminal window

4. **Test the setup:**
   - Send a WhatsApp message to your registered phone number
   - Check the application logs to see if messages are being received
   - Visit `http://127.0.0.1:4040` to see ngrok's request inspector

## 9. Troubleshooting

### WhatsApp Webhook Not Receiving Messages
- Verify ngrok is running and the URL is correct
- Check that the webhook URL in Meta matches your ngrok URL + `/whatsapp_response`
- Ensure the verify token matches in both `.env` and Meta dashboard
- Check that you've subscribed to message events

### Google Calendar Authorization Issues
- Make sure `credentials.json` is in the `mycalendar/` directory
- Delete `token.json` and re-authorize if you get permission errors
- Ensure Google Calendar API is enabled in your Google Cloud project

### API Key Errors
- Verify all API keys in `.env` are correct and not expired
- Check that you've enabled the required APIs in each service's dashboard
- For Google Cloud, ensure billing is enabled (some APIs require it)

### ngrok URL Changes
- Free ngrok URLs change on each restart
- Update the webhook URL in Meta dashboard each time
- Consider ngrok's paid plan for a static URL

## 10. Next Steps

- Test sending text messages to your WhatsApp number
- Try sending voice notes and images
- Test calendar operations (list events, add events)
- Test search functionality
- Monitor the application logs for any errors

---

**Note:** Keep your `.env` file secure and never commit it to version control. The `.gitignore` file should already exclude it.

