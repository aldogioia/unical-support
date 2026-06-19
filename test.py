import google.generativeai as genai
import os
from dotenv import load_dotenv

# Carichiamo le variabili dal tuo file .env per prendere la GOOGLE_API_KEY
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("Errore: GOOGLE_API_KEY non trovata nel file .env")
    exit()

genai.configure(api_key=api_key)

print("=== MODELLI PER EMBEDDING (RAG) ===")
for m in genai.list_models():
    if 'embedContent' in m.supported_generation_methods:
        print(f"Nome Esatto: {m.name}")
        print(f"Descrizione: {m.description}\n")

print("=== MODELLI PER GENERAZIONE TESTO ===")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"Nome Esatto: {m.name}")