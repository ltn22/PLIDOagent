#!/usr/bin/env python3
"""
build_biblio.py

For each UE responsable found in documents/taf/, runs a real agent -- Brave search
plus Gemini deciding what to search for and when it has enough -- to find and
synthesize their research interests, caching the result to documents/taf/biblio.json.

Not a notebook cell: 167 teachers, each needing one or more Brave searches plus a
couple of Gemini calls to decide and synthesize, adds up to far more requests than
Gemini's free 15-requests-per-minute tier can absorb inside a single class session.
Run this once; the notebook loads the cache.

Names come straight from the raw fiches in documents/taf/ (not cleaned.json), so this
can run independently of clean_fiches.py's own progress.
"""
import asyncio
import json
import os
import re
import time

import requests
from agents import Agent, Runner, function_tool, OpenAIChatCompletionsModel
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

load_dotenv(override=True)

TAF_DIR = os.path.join("documents", "taf")
BIBLIO_PATH = os.path.join(TAF_DIR, "biblio.json")
SECONDS_PER_TEACHER = 15  # generous pacing -- each teacher can cost several Gemini calls

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
BRAVE_API_KEY = os.environ["BRAVE_API_KEY"]


@function_tool
def search_scholar(query: str):
    """Search the web for a researcher's academic profile and interests."""
    response = requests.get("https://api.search.brave.com/res/v1/web/search",
                            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
                            params={"q": query, "count": 5}, timeout=20)
    time.sleep(1.2)  # the free tier allows about one request per second
    if response.status_code != 200:
        return f"Search failed (HTTP {response.status_code})."
    results = response.json().get("web", {}).get("results", [])
    return "\n\n".join(f"{r['title']}: {r['url']}\n{r.get('description', '')}"
                        for r in results) or "No results found."


class ResearchProfile(BaseModel):
    research_themes: list[str] = Field(description="3-6 short research theme/keyword phrases")
    summary: str = Field(description="2-3 sentence synthesis of their research interests and focus")
    sources: list[str] = Field(description="URLs actually used to build this profile")


def load_cache():
    if os.path.exists(BIBLIO_PATH):
        return json.load(open(BIBLIO_PATH))
    return {}


def save_cache(biblio):
    json.dump(biblio, open(BIBLIO_PATH, "w"), ensure_ascii=False, indent=2)


def teacher_names():
    """Every responsable listed across the raw fiches -- independent of clean_fiches.py."""
    names = set()
    for filename in os.listdir(TAF_DIR):
        if not filename.endswith(".txt"):
            continue
        text = open(os.path.join(TAF_DIR, filename)).read()
        match = re.search(r"Responsable\(s\)\s*\t?\s*\n(.*?)\n\t?Equipe", text, re.DOTALL)
        if match:
            for line in match.group(1).strip().splitlines():
                line = line.strip()
                if line:
                    names.add(line)
    return sorted(names)


async def main(limit=None):
    gemini_client = AsyncOpenAI(base_url=GEMINI_BASE_URL, api_key=os.environ["GOOGLE_API_KEY"])
    gemini_model = OpenAIChatCompletionsModel(model="gemini-flash-lite-latest", openai_client=gemini_client)

    agent = Agent(
        name="Faculty Research Profiler",
        instructions="Given a name and institution, use search_scholar (once or twice, no more) to "
                     "find their academic/research profile, then synthesize their research themes and "
                     "interests. If results are thin or ambiguous, say so in the summary rather than "
                     "inventing detail.",
        model=gemini_model,
        tools=[search_scholar],
        output_type=ResearchProfile,
    )

    names = teacher_names()
    if limit:
        names = names[:limit]
    print(f"{len(names)} unique teachers")

    biblio = load_cache()
    print(f"{len(biblio)} already cached, resuming")

    for name in names:
        if name in biblio:
            continue
        start = time.time()
        try:
            result = await Runner.run(agent, f"{name}, IMT Atlantique", max_turns=6)
            profile = result.final_output
            biblio[name] = {"research_themes": profile.research_themes, "summary": profile.summary,
                             "sources": profile.sources}
            save_cache(biblio)  # write after every teacher -- resumable if interrupted
            print(f"  [{len(biblio)}/{len(names)}] {name}: {', '.join(profile.research_themes[:3])}")
        except Exception as error:
            print(f"  FAILED on {name}: {error}")

        elapsed = time.time() - start
        if elapsed < SECONDS_PER_TEACHER:
            time.sleep(SECONDS_PER_TEACHER - elapsed)

    print(f"\nDone: {len(biblio)} teachers profiled, saved to {BIBLIO_PATH}")


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(limit=limit))
