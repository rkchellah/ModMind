from __future__ import annotations

import json
import os
from typing import Any, Literal

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ValidationError

from backend.mod_rag_embeddings import RetrievedChunk

load_dotenv()

_groq = Groq(api_key=os.environ["GROQ_API_KEY"])

GROQ_MODEL = "llama-3.3-70b-versatile"
AUTO_REMOVE_THRESHOLD = 0.85
AUTO_APPROVE_THRESHOLD = 0.90

SYSTEM_PROMPT = """
You are a Reddit moderation assistant. Given a post and similar past
moderation decisions, classify the post and return a JSON object.

Return ONLY valid JSON — no explanation, no markdown, no preamble.

JSON schema:
{
  "verdict": "remove" | "approve" | "needs_review",
  "confidence": float between 0.0 and 1.0,
  "violated_rule": string or null,
  "reason": string,
  "flags": list of strings,
  "suggested_removal_reason": string or null
}

Examples:

Post: "Check out my new photography portfolio!"
Past cases: [APPROVAL | Rule: none | Post: portfolio sharing | Action: approved]
Response:
{"verdict": "approve", "confidence": 0.92, "violated_rule": null,
 "reason": "Original creative content, no rule violations detected.",
 "flags": [], "suggested_removal_reason": null}

Post: "Buy 1000 upvotes for $5 — DM me"
Past cases: [REMOVAL | Rule: No spam | Post: buy upvotes $3 | Action: removed]
Response:
{"verdict": "remove", "confidence": 0.97, "violated_rule": "No spam",
 "reason": "Unsolicited commercial offer identical to past removals.",
 "flags": ["spam", "commercial"], "suggested_removal_reason":
 "Removed: violates Rule — No spam. Please read the community rules."}

Post: "Anyone else think the new update is terrible?"
Past cases: [REMOVAL | Rule: No low-effort posts | Post: update bad | Action: removed]
Response:
{"verdict": "needs_review", "confidence": 0.61, "violated_rule": "No low-effort posts",
 "reason": "Borderline — could be low-effort or a genuine discussion prompt.",
 "flags": ["low_effort"], "suggested_removal_reason": null}
""".strip()


class ModerationResult(BaseModel):
    verdict: Literal["remove", "approve", "needs_review"]
    confidence: float
    violated_rule: str | None
    reason: str
    flags: list[str]
    suggested_removal_reason: str | None


def _build_user_message(
    post_text: str,
    context: list[RetrievedChunk],
) -> str:
    context_block = "\n".join(
        f"- [{c.similarity:.2f}] {c.content}" for c in context
    ) or "No similar past cases found."

    return f"Post: {post_text}\n\nSimilar past cases:\n{context_block}"


def classify_post(
    post_text: str,
    context: list[RetrievedChunk],
    retry: int = 1,
) -> ModerationResult:
    """
    Classify a post using Groq with RAG context.
    Retries once with a correction nudge if JSON parsing fails.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(post_text, context)},
    ]

    for attempt in range(retry + 1):
        response = _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        raw = response.choices[0].message.content or ""

        try:
            parsed = json.loads(raw)
            return ModerationResult(**parsed)
        except (json.JSONDecodeError, ValidationError) as error:
            if attempt < retry:
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your response was invalid: {error}. "
                        "Return only valid JSON matching the schema."
                    ),
                })
            else:
                raise RuntimeError(
                    f"classify_post failed after {retry + 1} attempts: {error}"
                ) from error

    raise RuntimeError("classify_post: unexpected exit from retry loop")


def route_decision(
    result: ModerationResult,
    post_id: str,
    confidence_threshold: float = AUTO_REMOVE_THRESHOLD,
) -> dict[str, Any]:
    """
    Map a ModerationResult to an action dict for the agent to act on.
    Returns action: remove | approve | queue
    """
    if result.verdict == "remove" and result.confidence >= confidence_threshold:
        action = "remove"
    elif result.verdict == "approve" and result.confidence >= AUTO_APPROVE_THRESHOLD:
        action = "approve"
    else:
        action = "queue"

    mod_note = (
        f"Auto-removed by ModMind — {result.violated_rule} | "
        f"{round(result.confidence * 100)}% confidence | {result.reason}"
        if action == "remove"
        else f"ModMind flagged for review — "
             f"{round(result.confidence * 100)}% confidence | {result.reason}"
    )

    return {
        "post_id": post_id,
        "action": action,
        "mod_note": mod_note,
        "summary": (
            f"{action.capitalize()} under {result.violated_rule or 'no specific rule'}. "
            f"{round(result.confidence * 100)}% confidence."
        ),
        "suggested_removal_reason": result.suggested_removal_reason,
    }
