"""
run.py - Interactive Launcher and Pre-flight Verifier for UniFinder AI
Checks environment, prompts for API keys if missing, provides generation instructions,
and starts the FastAPI server.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def print_banner():
    banner = """
==============================================================================
   🎓 UniFinder AI — Higher-Ed, Admissions, PR & Career Multi-Agent Platform
   Palette: Forest Green (#0B2518) | Sand Beige (#FAF7F0) | Electric Purple (#7C3AED)
==============================================================================
"""
    print(banner)

def verify_and_guide_api_keys():
    google_key = os.getenv("GOOGLE_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    if google_key:
        print("✅ [Status]: Google Gemini API Key detected in environment.")
        return True
    elif groq_key:
        print("✅ [Status]: Groq API Key detected in environment.")
        return True

    print("⚠️  [NOTICE]: No API Key detected in `.env` yet.")
    print("-" * 78)
    print("UniFinder AI supports 100% FREE online LLMs. You can get a free key in 30s:")
    print()
    print("👉 Option 1 (Google Gemini - Recommended):")
    print("   1. Open: https://aistudio.google.com/app/apikey")
    print("   2. Sign in with any Google account & click 'Create API Key'")
    print("   3. It is 100% free with generous rate limits.")
    print()
    print("👉 Option 2 (Groq Cloud):")
    print("   1. Open: https://console.groq.com/keys")
    print("   2. Sign in & click 'Create API Key'")
    print()
    print("NOTE: You can enter your key right now, OR start the server and paste it")
    print("      directly into the web interface's 'API Settings' modal!")
    print("-" * 78)

    try:
        user_choice = input("Do you want to enter a Gemini/Groq key now? (y/N): ").strip().lower()
        if user_choice in ["y", "yes"]:
            provider = input("Which provider? (1 for Gemini, 2 for Groq): ").strip()
            entered_key = input("Paste your API key: ").strip()
            if entered_key:
                env_file = os.path.join(os.path.dirname(__file__), ".env")
                key_name = "GOOGLE_API_KEY" if provider != "2" else "GROQ_API_KEY"
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{key_name}={entered_key}\n")
                os.environ[key_name] = entered_key
                print(f"✅ Saved {key_name} to .env!")
                return True
    except (EOFError, KeyboardInterrupt):
        pass

    print("🚀 Launching server in hybrid mode! (You can enter your key in the Web UI)")
    return False

if __name__ == "__main__":
    print_banner()
    verify_and_guide_api_keys()

    import socket
    import uvicorn

    desired_port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")

    def get_free_port(target_host, start_port, max_tries=20):
        for candidate in range(start_port, start_port + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((target_host, candidate))
                    return candidate
                except OSError:
                    continue
        return start_port

    port = get_free_port(host, desired_port)
    if port != desired_port:
        print(f"⚠️  Port {desired_port} was already in use or locked by Windows.")
        print(f"🔄 Automatically shifted to free port: {port}")

    print(f"\n🌐 Starting UniFinder AI on http://{host}:{port}")
    print("👉 Open your browser to explore the Multi-Agent Admissions & PR Matrix!\n")

    uvicorn.run("app:app", host=host, port=port, reload=True)
