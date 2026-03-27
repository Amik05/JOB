import json
import os
import re

import google.generativeai as genai

MODEL_NAME = "gemini-2.5-flash"

PROMPT_TEMPLATE = """You are an AI assistant helping a job seeker track their applications.

Analyze the following email and return ONLY valid JSON with no markdown, no preamble, no backticks:

{{
  "is_job_related": true or false,
  "company": "company name or Unknown",
  "role": "job title or Unknown",
  "recruiter_name": "recruiter name or Unknown",
  "recruiter_email": "recruiter email or Unknown",
  "category": one of ["interview_invite", "rejection", "follow_up_needed", "offer_received", "awaiting_response"],
  "summary": "one sentence summary of the email",
  "next_action": "specific action the applicant should take",
  "urgency": "high, medium, or low",
  "suggested_reply": "a short professional reply if category is interview_invite or follow_up_needed, otherwise empty string"
}}

Email Subject: {subject}
Email From: {sender}
Email Body: {body}"""


class Classifier:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(MODEL_NAME)

    def _strip_fences(self, text: str) -> str:
        """Remove markdown code fences that the model may include despite instructions."""
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def classify(self, email: dict) -> dict | None:
        """
        Classify a single email dict.
        Returns parsed classification dict, or None if not job-related or unparseable.
        """
        prompt = PROMPT_TEMPLATE.format(
            subject=email.get("subject", ""),
            sender=f"{email.get('sender_name', '')} <{email.get('sender_email', '')}>",
            body=email.get("body", "")[:4000],  # cap body to avoid token overrun
        )

        try:
            response = self.model.generate_content(prompt)
            raw = response.text
        except Exception as e:
            print(f"  Gemini API error for email '{email.get('subject')}': {e}")
            return None

        cleaned = self._strip_fences(raw)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"  Malformed JSON from Gemini for email '{email.get('subject')}': {e}")
            print(f"  Raw response snippet: {cleaned[:200]}")
            return None

        if not result.get("is_job_related", False):
            return None

        return result
