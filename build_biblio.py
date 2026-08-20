#!/usr/bin/env python3
"""
build_biblio.py

For each UE responsable found in documents/taf/, runs a real agent -- Brave search for
their research profile, OpenAlex for their recent publications, Gemini deciding what
to search for and when it has enough -- caching the result to documents/taf/biblio.json.

Google Scholar itself is deliberately not scraped: no official API, easily blocked
past a handful of automated requests, and against its terms of service at this scale
-- the same reasoning as the browse_pass.py warning, just for a different server.
OpenAlex is a free, open, no-key-required API built for exactly this.

Not a notebook cell: 167 teachers, each needing one or more Brave/OpenAlex searches
plus several Gemini calls to decide and synthesize, adds up to far more requests than
Gemini's free tier can absorb inside a single class session -- both the 15
requests/minute cap and, we found the hard way, a 500 requests/day cap too. Run this
once (across however many days it actually needs -- it resumes where it left off);
the notebook loads the cache.

--provider ollama exists for symmetry with clean_fiches.py but is NOT SAFE TO USE for
this script: tested on qwen3:8b, combining tools=[...] with output_type=ResearchProfile
made the model skip every tool call entirely and fabricate a complete, plausible-looking
profile out of nothing -- wrong research themes, invented publication titles, fake URLs
(https://scholar.google.com/citations?user=abc123, literally a placeholder-shaped fake
id). Verified by logging every tool invocation: zero calls, for a task that absolutely
needs them. clean_fiches.py's single structured-output call (no tools, just reformat
given text) doesn't have this failure mode -- this script's tool-using agent does. Stick
to --provider gemini here and wait out its quota rather than risk fabricated data about
real people.

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
SECONDS_PER_TEACHER = 20  # generous pacing -- up to 4 Gemini calls per teacher now (3 tools + answer)

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


@function_tool
def search_openalex_author(author_name: str):
    """Search OpenAlex for candidate authors matching a name, with their institution and
    work count -- common names return several candidates, use institution to pick the right one."""
    response = requests.get("https://api.openalex.org/authors",
                            params={"search": author_name, "per_page": 5}, timeout=15)
    if response.status_code != 200:
        return f"Search failed (HTTP {response.status_code})."
    authors = response.json().get("results", [])
    if not authors:
        return "No matching author found on OpenAlex."
    lines = []
    for author in authors:
        institutions = author.get("last_known_institutions") or []
        institution = institutions[0]["display_name"] if institutions else "unknown institution"
        lines.append(f"id={author['id'].rsplit('/', 1)[-1]} name={author['display_name']} "
                     f"institution={institution} works={author['works_count']}")
    return "\n".join(lines)


@function_tool
def get_recent_publications(openalex_author_id: str):
    """Fetch the 5 most recent publications for an OpenAlex author id (e.g. A5075497720)."""
    response = requests.get("https://api.openalex.org/works",
                            params={"filter": f"author.id:{openalex_author_id}",
                                    "sort": "publication_date:desc", "per_page": 5}, timeout=15)
    if response.status_code != 200:
        return f"Search failed (HTTP {response.status_code})."
    works = response.json().get("results", [])
    return "\n".join(f"{w['publication_year']}: {w['display_name']}" for w in works) or "No works found."


class Publication(BaseModel):
    title: str = Field(description="Publication title")
    year: int = Field(description="Publication year")


class ResearchProfile(BaseModel):
    research_themes: list[str] = Field(description="3-6 short research theme/keyword phrases")
    summary: str = Field(description="2-3 sentence synthesis of their research interests and focus")
    recent_publications: list[Publication] = Field(description="Up to 5 recent publications from "
                                                    "OpenAlex, only once matched to the right person "
                                                    "by institution -- leave empty rather than guessing "
                                                    "if no confident match exists.")
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


def build_model(provider):
    if provider == "ollama":
        print("WARNING: --provider ollama is verified UNSAFE for this script -- qwen3:8b "
              "skips every tool call and fabricates profiles (wrong themes, invented "
              "publications, fake URLs) when tools+output_type are combined. See the "
              "module docstring. Proceeding anyway, but don't trust what comes out.")
        client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        return OpenAIChatCompletionsModel(model="qwen3:8b", openai_client=client)
    client = AsyncOpenAI(base_url=GEMINI_BASE_URL, api_key=os.environ["GOOGLE_API_KEY"])
    return OpenAIChatCompletionsModel(model="gemini-flash-lite-latest", openai_client=client)


async def main(limit=None, provider="gemini"):
    gemini_model = build_model(provider)
    print(f"Provider: {provider}")

    agent = Agent(
        name="Faculty Research Profiler",
        instructions="Given a name and institution: (1) use search_scholar (once or twice, no more) "
                     "to find their academic profile and research interests; (2) use "
                     "search_openalex_author to find OpenAlex candidates, and pick the one whose "
                     "institution matches (IMT Atlantique, or a known co-affiliation like "
                     "CNRS/Lab-STICC/IMT); (3) use get_recent_publications with that id to list their "
                     "recent papers. If results are thin, ambiguous, or no OpenAlex match is "
                     "confident, say so and leave that field empty rather than inventing detail.",
        model=gemini_model,
        tools=[search_scholar, search_openalex_author, get_recent_publications],
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
            result = await Runner.run(agent, f"{name}, IMT Atlantique", max_turns=8)
            profile = result.final_output
            biblio[name] = {"research_themes": profile.research_themes, "summary": profile.summary,
                             "recent_publications": [p.model_dump() for p in profile.recent_publications],
                             "sources": profile.sources}
            save_cache(biblio)  # write after every teacher -- resumable if interrupted
            print(f"  [{len(biblio)}/{len(names)}] {name}: {', '.join(profile.research_themes[:3])}")
        except Exception as error:
            # A per-day quota error won't clear up by retrying the next teacher 20s later --
            # every remaining name would just fail the same way. Stop cleanly instead of
            # burning through the rest of the list; what's already cached stays cached, so
            # re-running later resumes right here.
            if "RESOURCE_EXHAUSTED" in str(error) or "429" in str(error):
                print(f"\nHit the daily quota after {len(biblio)} teachers -- stopping here. "
                      f"Re-run this script later (tomorrow, if it's the per-day cap) to resume.")
                break
            print(f"  FAILED on {name}: {error}")

        elapsed = time.time() - start
        if provider == "gemini" and elapsed < SECONDS_PER_TEACHER:
            time.sleep(SECONDS_PER_TEACHER - elapsed)

    print(f"\nDone: {len(biblio)} teachers profiled, saved to {BIBLIO_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("limit", type=int, nargs="?", default=None)
    parser.add_argument("--provider", choices=["gemini", "ollama"], default="gemini")
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, provider=args.provider))
