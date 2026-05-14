from __future__ import annotations

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from backend.mod_rag_embeddings import Document, index_documents

load_dotenv()

SAMPLE_DOCUMENTS = [
    Document(
        content="REMOVAL | Rule: No spam | Post: Buy 1000 upvotes for $5 DM me | Reason: unsolicited commercial offer",
        metadata={"type": "removal", "rule_id": "no_spam", "action": "removed"},
    ),
    Document(
        content="REMOVAL | Rule: No spam | Post: Get free Reddit followers click my link | Reason: spam link to external site",
        metadata={"type": "removal", "rule_id": "no_spam", "action": "removed"},
    ),
    Document(
        content="REMOVAL | Rule: No self-promotion | Post: Check out my YouTube channel I post daily | Reason: self-promotion without engagement",
        metadata={"type": "removal", "rule_id": "no_self_promotion", "action": "removed"},
    ),
    Document(
        content="REMOVAL | Rule: No hate speech | Post: All people from X country are criminals | Reason: xenophobic generalisation",
        metadata={"type": "removal", "rule_id": "no_hate_speech", "action": "removed"},
    ),
    Document(
        content="REMOVAL | Rule: No low-effort posts | Post: lol | Reason: no substance, single word post",
        metadata={"type": "removal", "rule_id": "no_low_effort", "action": "removed"},
    ),
    Document(
        content="APPROVAL | Rule: none | Post: Here is my analysis of the recent market trends with sources | Reason: quality original content",
        metadata={"type": "approval", "rule_id": None, "action": "approved"},
    ),
    Document(
        content="APPROVAL | Rule: none | Post: I made a tool that helps with X here is the GitHub | Reason: original useful contribution",
        metadata={"type": "approval", "rule_id": None, "action": "approved"},
    ),
    Document(
        content="REMOVAL | Rule: No spam | Post: Earn $500 a day working from home DM for details | Reason: financial spam",
        metadata={"type": "removal", "rule_id": "no_spam", "action": "removed"},
    ),
]

if __name__ == "__main__":
    print(f"Seeding {len(SAMPLE_DOCUMENTS)} documents...")
    index_documents(SAMPLE_DOCUMENTS)
    print("Done. Supabase mod_knowledge table seeded.")