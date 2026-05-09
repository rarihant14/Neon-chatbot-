from sarvamai import SarvamAI
import base64

client = SarvamAI(
    api_subscription_key="sk_73wo348e_j9sxo3hIJXPG7L9FrZP14vhc"
)

response = client.text_to_speech.convert(
    text="Hello, how are you?",
    target_language_code="hi-IN"
    ,
)

# 👇 get base64 string
audio_base64 = response.audios[0]

# 👇 convert to bytes
audio_bytes = base64.b64decode(audio_base64)

# 👇 save file
with open("output.wav", "wb") as f:
    f.write(audio_bytes)

print("Audio saved successfully")