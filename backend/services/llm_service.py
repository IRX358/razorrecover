# Universal LLM provider wrapper
# Supports Gemini and Claude with safe fallback when keys are unset

import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")


def ask_llm(system_prompt: str, user_message: str) -> str:
    if LLM_PROVIDER == "claude":
        return _ask_claude(system_prompt, user_message)
    else:
        return _ask_gemini(system_prompt, user_message)


def _ask_gemini(system_prompt: str, user_message: str) -> str:
    try:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return _fallback_response(user_message)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=system_prompt
        )
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        return _fallback_response(user_message, str(e))


def _ask_claude(system_prompt: str, user_message: str) -> str:
    try:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return _fallback_response(user_message)

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        return _fallback_response(user_message, str(e))


def _fallback_response(user_message: str, error: str = "") -> str:
    # Graceful fallback when API key is missing or offline
    note = f" (offline notice: {error})" if error else " (using deterministic fallback template)"
    return (
        "Based on pre-computed evidence, this recovery play targets a statistically abnormal "
        "failure cluster. Review the verified amounts and diagnosis confidence above for details."
        f"{note}"
    )
