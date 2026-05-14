---
file: ARCHITECTURE.md
project: ModMind
---

# ModMind — Architecture

---

## What It Does in One Paragraph

When a post is submitted to a subreddit with ModMind installed, a Devvit trigger
fires and calls a FastAPI backend. The backend retrieves the 3 most similar past
mod decisions from a Supabase vector database, feeds them as context to Groq, and
returns a verdict: remove, approve, or queue for human review. If the confidence
is high enough, the post is auto-removed and the user receives a sticky comment
explaining why. If not, a mod note is attached so human mods can review with the
AI's reasoning already in front of them.

---

## System Diagram

```
Reddit (new post submitted)
        │
        ▼
  Devvit trigger (trigger.ts)
  onPostSubmit event fires
        │
        │  POST /moderate
        │  {post_id, post_text, username, confidence_threshold}
        ▼
  FastAPI backend (Render)
  mod_agent.py
        │
        ├──► search_similar_cases(query)
        │         │
        │         ▼
        │    mod_rag_embeddings.py
        │    embed(post_text) → OpenAI
        │    retrieve() → Supabase pgvector RPC
        │    returns 3 similar past decisions
        │
        ├──► get_user_history(username)
        │         │
        │         ▼
        │    PRAW mod log filtered by author
        │
        └──► classify_post(text, context)
                  │
                  ▼
             mod_classifier.py
             Groq llama-3.3-70b-versatile
             returns ModerationResult
             {verdict, confidence, violated_rule, reason}
                  │
                  ▼
             route_decision()
             confidence ≥ 0.85 → remove
             confidence ≥ 0.90 → approve
             else            → queue
                  │
                  ▼
        returns JSON response
        {post_id, action, summary, mod_note, tool_count}
        │
        ▼
  Devvit trigger reads action
        │
        ├── action=remove  → reddit.submission.mod.remove()
        │                    sticky comment with removal reason
        │
        ├── action=queue   → mod note attached with AI reasoning
        │
        └── action=approve → no action taken
```

---

## Data Flow

**At moderation time (every new post):**
```
Post submitted
  → Devvit calls /moderate
  → backend embeds post text (OpenAI)
  → pgvector returns 3 similar past cases
  → Groq classifies with RAG context
  → action returned to Devvit
  → Devvit acts on Reddit
```
Supabase is **read-only** during moderation. Nothing is written at action time.

**At indexing time (run periodically via script):**
```
index_modlog.py runs
  → PRAW pulls mod log from subreddit
  → each removal formatted as a content string
  → OpenAI embeds each string
  → stored in Supabase mod_knowledge table
```
This is what gives the RAG its knowledge base. Run it once to seed,
then periodically to keep it current.

---

## Supabase Schema

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Main knowledge table
CREATE TABLE mod_knowledge (
  id        bigserial PRIMARY KEY,
  content   text NOT NULL,
  metadata  jsonb,
  embedding vector(384)  -- sentence-transformers all-MiniLM-L6-v2 output
);

-- Index for fast cosine similarity search
CREATE INDEX ON mod_knowledge
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- RPC for similarity search
CREATE OR REPLACE FUNCTION match_mod_knowledge(
  query_embedding vector(384),
  match_count     int
)
RETURNS TABLE (
  id         bigint,
  content    text,
  metadata   jsonb,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    content,
    metadata,
    1 - (embedding <=> query_embedding) AS similarity
  FROM mod_knowledge
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

---

## Decision Thresholds

| Confidence | Action |
|---|---|
| ≥ 0.90 | Auto-approve — no action taken |
| ≥ 0.85 | Auto-remove — post removed, sticky comment sent |
| < 0.85 | Queue — mod note attached with AI reasoning |

Default threshold is 0.85. Mods can adjust via the Devvit settings panel (0.70–0.95).

---

## API Contract

**POST /moderate**

Request:
```json
{
  "post_id": "t3_abc123",
  "post_text": "Buy 1000 Reddit upvotes for $5. DM me.",
  "username": "spamuser99",
  "confidence_threshold": 0.85
}
```

Response:
```json
{
  "post_id": "t3_abc123",
  "action": "remove",
  "summary": "Removed under Rule 1. 91% confidence. 2 similar past cases retrieved.",
  "mod_note": "Auto-removed by ModMind — Rule 1 | 91% confidence | unsolicited commercial link",
  "tool_count": 2
}
```

Action values: `remove` | `approve` | `queue`

---

## Error Handling

| Failure | Behaviour |
|---|---|
| FastAPI timeout | Devvit catches → post queued with "AI check failed" note |
| Supabase unreachable | `retrieve()` returns empty list → classifier runs zero-shot |
| Groq API error | Retry once → if still failing, return `needs_review` verdict |
| PRAW error | `get_user_history()` returns empty list → agent continues without it |

The system never crashes the Devvit trigger. Every failure path ends in a safe default.

---

## Deployment

| Component | Host | Notes |
|---|---|---|
| FastAPI backend | Render free tier | GitHub deploy, auto-deploys on push to main |
| Supabase | Supabase free tier | pgvector enabled, service role key in Render env vars |
| Devvit app | Reddit Developer Platform | Installed per subreddit via App Directory |
| index_modlog.py | Run locally | One-time seed + periodic manual runs |