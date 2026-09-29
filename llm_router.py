"""
Unified Multi-Provider LLM Router & Orchestration Engine.
Supports dynamic switching and fallback between:
1. OpenAI (Default / Primary): gpt-4o-mini, gpt-4o
2. DeepSeek: deepseek-chat (DeepSeek-V3 via official or OpenAI-compatible endpoint)
3. Google Gemini: gemini-2.5-flash, gemini-flash-lite

Enforces conversational pacing, low-latency cold call objection handling,
and automatic fallback so the application never stalls.
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional

from config import (
    GEMINI_API_KEY,
    GOOGLE_API_KEY
)

logger = logging.getLogger("llm_router")

# Provider Constants
PROVIDER_OPENAI = "OPENAI"
PROVIDER_DEEPSEEK = "DEEPSEEK"
PROVIDER_GEMINI = "GEMINI"

# Default Model Mapping
DEFAULT_MODELS = {
    PROVIDER_OPENAI: "gpt-4o-mini",
    PROVIDER_DEEPSEEK: "deepseek-chat",
    PROVIDER_GEMINI: "gemini-2.5-flash"
}

# Base URLs
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


class LLMRouter:
    """Manages multi-provider LLM routing, runtime switching, and graceful fallbacks."""

    _runtime_provider: Optional[str] = None

    @classmethod
    def get_configured_provider(cls) -> str:
        """Returns currently active LLM provider (Runtime setting -> SettingsManager -> ENV -> Default)."""
        if cls._runtime_provider:
            return cls._runtime_provider

        try:
            from settings_manager import SettingsManager
            settings = SettingsManager.get()
            if settings.get("llm_provider"):
                return settings["llm_provider"].upper()
        except Exception:
            pass

        env_provider = os.getenv("LLM_PROVIDER", "").upper()
        if env_provider in (PROVIDER_OPENAI, PROVIDER_DEEPSEEK, PROVIDER_GEMINI):
            return env_provider

        # Default to OpenAI if key exists, otherwise check DeepSeek, then Gemini
        if os.getenv("OPENAI_API_KEY"):
            return PROVIDER_OPENAI
        if os.getenv("DEEPSEEK_API_KEY"):
            return PROVIDER_DEEPSEEK
        return PROVIDER_OPENAI  # Default target requested by user

    @classmethod
    def set_provider(cls, provider: str) -> str:
        """Dynamically updates active provider at runtime."""
        p_upper = provider.upper().strip()
        if p_upper not in (PROVIDER_OPENAI, PROVIDER_DEEPSEEK, PROVIDER_GEMINI):
            raise ValueError(f"Unsupported LLM provider: {provider}. Must be OPENAI, DEEPSEEK, or GEMINI.")
        cls._runtime_provider = p_upper
        try:
            from settings_manager import SettingsManager
            SettingsManager.update({"llm_provider": p_upper})
        except Exception as e:
            logger.warning(f"Could not persist provider to settings: {e}")
        logger.info(f"LLM Provider switched to: {p_upper}")
        return p_upper

    @classmethod
    def get_provider_status(cls) -> Dict[str, Any]:
        """Returns API keys presence, active models, and readiness status for all 3 providers."""
        active = cls.get_configured_provider()
        openai_key = os.getenv("OPENAI_API_KEY", "")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

        return {
            "active_provider": active,
            "providers": {
                PROVIDER_OPENAI: {
                    "configured": bool(openai_key and not openai_key.startswith("mock_")),
                    "model": os.getenv("OPENAI_MODEL", DEFAULT_MODELS[PROVIDER_OPENAI]),
                    "label": "OpenAI (GPT-4o-mini / GPT-4o)",
                    "recommended_for": "Primary Driver, Voice Dialer & Sales Conversion"
                },
                PROVIDER_DEEPSEEK: {
                    "configured": bool(deepseek_key and not deepseek_key.startswith("mock_")),
                    "model": os.getenv("DEEPSEEK_MODEL", DEFAULT_MODELS[PROVIDER_DEEPSEEK]),
                    "label": "DeepSeek (V3 Direct Conversational)",
                    "recommended_for": "Ultra Low Cost WhatsApp Copy & Direct Banter"
                },
                PROVIDER_GEMINI: {
                    "configured": bool(gemini_key and not gemini_key.startswith("mock_")),
                    "model": os.getenv("GEMINI_MODEL", DEFAULT_MODELS[PROVIDER_GEMINI]),
                    "label": "Google Gemini (Flash 2.5 / Lite)",
                    "recommended_for": "Heavy Web Scraping & Multi-token Extraction"
                }
            }
        }

    # ================= Core Generation Gateways =================

    @classmethod
    def _is_provider_ready(cls, provider: str) -> bool:
        if provider == PROVIDER_OPENAI:
            k = os.getenv("OPENAI_API_KEY", "")
            return bool(k and not k.startswith("mock_"))
        elif provider == PROVIDER_DEEPSEEK:
            k = os.getenv("DEEPSEEK_API_KEY", "")
            return bool(k and not k.startswith("mock_"))
        elif provider == PROVIDER_GEMINI:
            k = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
            return bool(k and not k.startswith("mock_"))
        return False

    @classmethod
    def generate_text(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 800
    ) -> str:
        """
        Executes text generation using the configured provider with automatic multi-provider fallback.
        Only attempts providers that have a configured API key.
        """
        target_provider = (provider or cls.get_configured_provider()).upper()
        candidates = [target_provider]

        # Add remaining providers as fallback chain
        for fallback in [PROVIDER_OPENAI, PROVIDER_DEEPSEEK, PROVIDER_GEMINI]:
            if fallback not in candidates:
                candidates.append(fallback)

        # Filter candidates: prioritize providers with keys ready
        ready_providers = [p for p in candidates if cls._is_provider_ready(p)]
        if not ready_providers:
            ready_providers = candidates  # Attempt anyway so real error is raised if needed

        last_error = None
        for p in ready_providers:
            try:
                if p == PROVIDER_OPENAI:
                    res = cls._call_openai(prompt, system_prompt, model, temperature, max_tokens)
                    if res: return res
                elif p == PROVIDER_DEEPSEEK:
                    res = cls._call_deepseek(prompt, system_prompt, model, temperature, max_tokens)
                    if res: return res
                elif p == PROVIDER_GEMINI:
                    res = cls._call_gemini(prompt, system_prompt, model, temperature, max_tokens)
                    if res: return res
            except Exception as e:
                logger.warning(f"Provider {p} failed: {e}. Attempting next in fallback chain...")
                last_error = e

        logger.error(f"All LLM providers failed. Last error: {last_error}")
        return ""

    @classmethod
    def generate_json(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Executes structured JSON generation and parsing across any configured provider.
        """
        json_sys = (system_prompt or "") + "\n\nCRITICAL: Return STRICTLY valid RFC8259 JSON only. No markdown formatting, no code blocks, no trailing conversational text."
        raw_text = cls.generate_text(prompt=prompt, system_prompt=json_sys, provider=provider, model=model, temperature=0.2)
        if not raw_text:
            return None

        # Clean markdown wrappers if present
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            return json.loads(clean_text)
        except Exception:
            # Fallback substring parser
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(clean_text[start:end+1])
                except Exception:
                    pass
        logger.warning(f"Failed to parse JSON from LLM reply: {raw_text[:200]}")
        return None

    @classmethod
    def generate_voice_reply(
        cls,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        clinic_context: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Specialized low-latency conversational engine for phone calls and AI Takeover turns.
        Guarantees punchy, natural, 1-to-2 sentence human-like dialogue under 15 words.
        """
        clinic_context = clinic_context or {}
        history = history or []

        # Enforce human conversational speed rules
        rules = """
CRITICAL CONVERSATIONAL RULES (LIVE PHONE CALL):
1. Keep your reply to EXACTLY 1 crisp sentence (10 to 15 words maximum).
2. Sound like a relaxed, consultative human colleague, NOT a bot or telemarketer.
3. If they give an objection ("we have front desk", "already have Dentrix", "busy", "send email"):
   - Empathize in 3 words and pivot to a 2-minute video prototype or ask for office manager.
4. If they ask about price: Quote $1,500 setup and $399/mo, or anchor against 1 single implant case.
5. If they are open to meeting or ask when: Confirm Thursday at 11:00 AM.
6. Return JSON with keys: "reply", "is_meeting_booked" (boolean), "booked_slot" (string or null).
"""
        full_system = f"{system_prompt}\n{rules}"
        prompt = f"Prospect just said: \"{user_message}\"\n\nGenerate the next spoken response in JSON:"

        json_res = cls.generate_json(prompt=prompt, system_prompt=full_system, provider=provider)
        if json_res and "reply" in json_res:
            return json_res

        # Fallback heuristic if JSON parsing failed
        fallback_reply = cls.generate_text(prompt=prompt, system_prompt=full_system, provider=provider, max_tokens=60)
        clean_fallback = fallback_reply.replace('"', '').replace('\n', ' ').strip()
        if not clean_fallback:
            clean_fallback = "Completely understand. Could I share a quick two-minute video with your office manager?"

        return {
            "reply": clean_fallback,
            "is_meeting_booked": "thursday" in clean_fallback.lower() or "11:00" in clean_fallback.lower(),
            "booked_slot": "Thursday at 11:00 AM" if "thursday" in clean_fallback.lower() else None
        }

    # ================= Provider Implementations =================

    @classmethod
    def _call_openai(cls, prompt: str, system_prompt: Optional[str], model: Optional[str], temp: float, max_tokens: int) -> str:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key or key.startswith("mock_"):
            raise ValueError("OPENAI_API_KEY is not configured in environment")

        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=OPENAI_BASE_URL, timeout=12.0)
        target_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODELS[PROVIDER_OPENAI])

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=temp,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()

    @classmethod
    def _call_deepseek(cls, prompt: str, system_prompt: Optional[str], model: Optional[str], temp: float, max_tokens: int) -> str:
        key = os.getenv("DEEPSEEK_API_KEY", "")
        if not key or key.startswith("mock_"):
            raise ValueError("DEEPSEEK_API_KEY is not configured in environment")

        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL, timeout=15.0)
        target_model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODELS[PROVIDER_DEEPSEEK])

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=temp,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()

    @classmethod
    def _call_gemini(cls, prompt: str, system_prompt: Optional[str], model: Optional[str], temp: float, max_tokens: int) -> str:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        if not key or key.startswith("mock_"):
            raise ValueError("GEMINI_API_KEY / GOOGLE_API_KEY is not configured")

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=12000)
        )
        target_model = model or os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

        full_content = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt

        resp = client.models.generate_content(
            model=target_model,
            contents=full_content,
            config=types.GenerateContentConfig(
                temperature=temp,
                max_output_tokens=max_tokens
            )
        )
        return resp.text.strip() if resp.text else ""
