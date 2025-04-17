from google.auth.transport.requests import Request
from google.oauth2 import service_account
import google.generativeai as genai

# Authenticate with the service account
credentials = service_account.Credentials.from_service_account_file(
    "credentials/red-button-442617-a9-89794f0a5b90.json"
)

with open("genai_text_input.txt","r",encoding="utf-8") as f:
    final_text=f.read()
# api_key="89794f0a5b90bd08593ce1249d64ee25a2e2e70c"
# genai.configure(credentials=credentials)

genai.configure(api_key="AIzaSyCuWhC9Wx80HDB7bOf1R_-yy1P3z7PiKlw")

model = genai.GenerativeModel(model_name="gemini-1.5-flash")
response = model.generate_content("Summarize this text in points : "+ final_text)
print(response.text)

