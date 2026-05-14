from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from groq import Groq
from pydantic import BaseModel

from backend.mod_classifier import classify_post, route_decision
from backend.mod_rag_embeddings import RetrievedChunk, retrieve

load_dotenv()

_groq = Groq(api_key=os.environ["GROQ_API_KEY"])
app = FastAPI()

GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_TOOL_ITERATIONS = 5

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_similar_cases",
            "description": "Search the subreddit's moderation history for similar past decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The post text or keywords to search for."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_history",
            "description": "Retrieve the moderation history for a specific Reddit user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The Reddit username to look up."
                    }
                },
                "required": ["username"]
            }
        }
    }
]

AGENT_SYSTEM_PROMPT = """
You are a Reddit moderation assistant gathering context before a decision is made.

Your job: collect relevant information about a new post.
1. Always call search_similar_cases to find past mod decisions similar to this post.
2. If the post author seems like a repeat offender, call get_user_history.
3. Once you have the context you need, stop calling tools.

Do not make the removal decision — that happens after you finish.
""".strip()


# --- Tool implementations ---

def _search_similar_cases(query: str, limit: int = 3) -> list[dict[str, Any]]:
    chunks = retrieve(query, k=limit)
    return [
        {
            "content": c.content,
            "metadata": c.metadata,
            "similarity": round(c.similarity, 3),
        }
        for c in chunks
    ]


def _get_user_history(username: str) -> list[dict[str, Any]]:
    # Stub — replaced with PRAW in Step 6
    return []


def _remove_post(post_id: str, reason: str) -> None:
    # Stub — replaced with PRAW in Step 6
    print(f"[stub] remove_post: {post_id} | reason: {reason}")


def _add_to_mod_queue(post_id: str, ai_note: str) -> None:
    # Stub — replaced with Devvit mod note API in Step 8
    print(f"[stub] add_to_mod_queue: {post_id} | note: {ai_note}")


def _execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    if name == "search_similar_cases":
        return _search_similar_cases(**arguments)
    if name == "get_user_history":
        return _get_user_history(**arguments)
    raise ValueError(f"Unknown tool: {name}")


# --- Agent loop ---

def run_mod_agent(
    post_id: str,
    post_text: str,
    username: str,
    confidence_threshold: float = 0.85,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"New post by u/{username}:\n\n{post_text}"
        },
    ]

    retrieved_chunks: list[RetrievedChunk] = []
    tool_count = 0

    for _ in range(MAX_TOOL_ITERATIONS):
        response = _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message
        assistant_message: dict[str, Any] = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_message)

        if choice.finish_reason == "stop":
            break

        if choice.finish_reason == "tool_calls":
            for tool_call in choice.message.tool_calls:
                tool_count += 1
                name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                result = _execute_tool(name, arguments)

                if name == "search_similar_cases":
                    retrieved_chunks = [
                        RetrievedChunk(
                            id=0,
                            content=r["content"],
                            metadata=r["metadata"],
                            similarity=r["similarity"],
                        )
                        for r in result
                    ]

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

    # Classifier makes the decision — not the LLM
    classification = classify_post(post_text, retrieved_chunks)
    decision = route_decision(classification, post_id, confidence_threshold)

    # Execute the action
    if decision["action"] == "remove":
        _remove_post(post_id, decision["mod_note"])
    else:
        _add_to_mod_queue(post_id, decision["mod_note"])

    return {
        "post_id": post_id,
        "action": decision["action"],
        "summary": decision["summary"],
        "mod_note": decision["mod_note"],
        "tool_count": tool_count,
    }


# --- FastAPI endpoint ---

class ModerateRequest(BaseModel):
    post_id: str
    post_text: str
    username: str
    confidence_threshold: float = 0.85


@app.post("/moderate")
async def moderate(request: ModerateRequest) -> dict[str, Any]:
    return run_mod_agent(
        post_id=request.post_id,
        post_text=request.post_text,
        username=request.username,
        confidence_threshold=request.confidence_threshold,
    )
