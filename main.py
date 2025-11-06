from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

from whatsapp_response import whatsapp_router

app = FastAPI()
app.include_router(whatsapp_router)
