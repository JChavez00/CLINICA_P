
import os
from dotenv import load_dotenv
from groq import Groq

# Leer y actualizar variables desde .env
load_dotenv(override=True)

api_key = os.getenv("GROQ_API_KEY")
modelo = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

if not api_key:
    raise RuntimeError("No se encontró GROQ_API_KEY")

print("Modelo que se utilizará:", modelo)

cliente = Groq(api_key=api_key)

respuesta = cliente.chat.completions.create(
    model=modelo,
    messages=[
        {
            "role": "system",
            "content": (
                "Eres un asistente administrativo "
                "de un policlínico. "
                "Responde en español."
            )
        },
        {
            "role": "user",
            "content": (
                "¿Qué indicadores administrativos "
                "debe analizar un policlínico?"
            )
        }
    ],
    temperature=0.2,
    max_completion_tokens=500
)

print("\nRESPUESTA DE GROQ:\n")
print(respuesta.choices[0].message.content)
