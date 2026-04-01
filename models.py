import google.generativeai as genai

# Configure with your API key
genai.configure(api_key="AIzaSyAiBVHBlhVFOZMlBKlGFosjG-NZjNRlWN4")

try:
    models = genai.list_models()
    print("Available models:")
    for model in models:
        print(f"- {model.name} (supported methods: {model.supported_generation_methods})")
except Exception as e:
    print(f"Error listing models: {e}")