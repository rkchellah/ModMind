# ModMind — AI Moderation Assistant for Reddit

ModMind learns from your subreddit's own moderation history and automatically
enforces your community's standards — no rule-writing required.

---

## The Problem

Reddit's AutoModerator handles basic keyword filtering but requires technical
rule-writing knowledge most volunteer mods don't have — and it has no memory.
Every moderation decision is made from scratch, with no way to enforce
consistency across a mod team or across time.

Reddit moderators collectively spend a minimum of 466 hours per day performing
moderating actions across the platform — all unpaid volunteers.

---

## How ModMind Solves It

ModMind uses your subreddit's own removal history as its rulebook. When a new
post is submitted, ModMind:

1. Finds the 3 most similar past moderation decisions from your community
2. Uses AI to classify the post based on those past decisions
3. Auto-removes clear violations with a sticky comment explaining why
4. Flags borderline posts for human review with the AI's reasoning attached

No regex. No rule syntax. No technical knowledge required.

---

## How It Works

```
New post submitted
        ↓
ModMind trigger fires
        ↓
Retrieves similar past mod decisions (RAG)
        ↓
AI classifies: remove / queue / approve
        ↓
Acts automatically — removal reason sent to user
```

---

## Features

- **Automatic removal** — clear violations removed instantly with a sticky
  comment explaining why, so the user understands what rule they broke
- **Smart queuing** — borderline posts flagged with AI reasoning so mods
  can make informed decisions without starting from scratch
- **Full audit trail** — every AI action logged as a mod note, fully visible
  to the mod team
- **Configurable threshold** — adjust the confidence level via the settings
  panel to match your community's tolerance for automation
- **No setup required** — installs from the App Directory and works on the
  next post submission

---

## Installing ModMind

1. Go to [developers.reddit.com/apps/modmind-bot](https://developers.reddit.com/apps/modmind-bot)
2. Click **Install**
3. Select the subreddit you moderate
4. ModMind starts working immediately on the next post submission

---

## Configuration

After installing, go to your subreddit's mod settings to adjust:

| Setting | Default | Range | Description |
|---|---|---|---|
| Confidence threshold | 0.85 | 0.70 – 0.95 | Minimum confidence required to auto-remove a post |

Posts below the threshold are queued for human review instead of auto-removed.
Raising the threshold makes ModMind more conservative. Lowering it makes it
more aggressive.

---

## What Mods See

**When a post is auto-removed:**

The post is removed and the user receives a sticky comment:

> *Removed: violates Rule — No spam. Please read the community rules.*

A mod note is attached to the removed post:

> *Auto-removed by ModMind — No spam | 93% confidence | unsolicited commercial offer*

**When a post is flagged for review:**

The post stays up. A mod note appears in the queue:

> *ModMind flagged for review — 74% confidence | borderline self-promotion, may qualify as original content*

Mods can then approve or remove with full context already in front of them.

---

## Communities That Would Benefit

**r/startups** — High volume of spam and self-promotion violations that follow
predictable patterns. ModMind would handle the obvious cases instantly, freeing
mods for nuanced decisions.

**r/learnprogramming** — Large mod team with consistency challenges. ModMind
enforces the same standard across all mods, all shifts, all time zones.

**r/personalfinance** — Context-dependent violations that require understanding
past precedent. ModMind surfaces similar past decisions so mods never start
from scratch.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Platform | Devvit (Reddit Developer Platform) |
| Agent backend | Python + FastAPI |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | Supabase pgvector |
| LLM | Groq — llama-3.3-70b-versatile |
| Hosting | Render |

---

## Architecture

```
Devvit trigger (TypeScript)
    onPostSubmit → POST /moderate
            ↓
    FastAPI backend (Python, Render)
            ↓
    sentence-transformers
    embed post text → 384-dim vector
            ↓
    Supabase pgvector
    cosine similarity → 3 similar past decisions
            ↓
    Groq llama-3.3-70b-versatile
    classify with RAG context
            ↓
    action: remove | queue | approve
            ↓
    Devvit executes on Reddit
```

## License

MIT