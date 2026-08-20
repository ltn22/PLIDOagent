#!/usr/bin/env python3
"""
clean_fiches.py

Batch-cleans the raw PASS fiches in documents/taf/ into structured records
(UE code, title, description, learning outcomes, competency blocks, campus,
responsable names) via an LLM, and caches the result to
documents/taf/cleaned.json.

Not a notebook cell: Gemini's free tier caps at 15 requests/minute, so ~275
fiches take at least ~20 minutes even with perfect pacing -- too slow to run
live in class, and nothing about it needs a human in the loop the way
browse_pass.py's SSO login does. Run this once; the notebook loads the cache.

Deduplicates by UE code first: a handful of fiches were captured more than
once (browse_pass.py followed a date-picker link that happened to reopen an
already-seen course's popup), so only the first copy of each UE code is sent
to the LLM.
"""
import json
import os
import re
import time

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv(override=True)

TAF_DIR = os.path.join("documents", "taf")
CACHE_PATH = os.path.join(TAF_DIR, "cleaned.json")
REQUESTS_PER_MINUTE = 12  # stay under Gemini free tier's 15 RPM cap


class Competency(BaseModel):
    code: str = Field(description="The competency block code, e.g. BC02-DSC-2")
    description: str = Field(description="What this competency block covers")
    raw_text: str = Field(description="The exact, verbatim text of this competency line as it "
                           "appears in the fiche -- copy it exactly, do not paraphrase or clean it up.")


class FicheExtract(BaseModel):
    ue_code: str = Field(description="The UE code, e.g. PA-DI-ADEEPL-B")
    title: str = Field(description="The course title, cleaned up -- no numbering, no UE code prefix")
    description: str = Field(description="Clean pedagogical description: what the course covers, its "
                              "content and prerequisites -- prose only, no PASS UI labels, table "
                              "clutter, or administrative metadata like credits or campus.")
    learning_outcome: str = Field(description="The intended learning outcomes ('Résultats "
                                   "d'apprentissages visés' section) -- what a student should be able "
                                   "to do after completing the course, not just what it covers.")
    competencies: list[Competency] = Field(description="Each competency block listed under 'III. "
                                            "Compétences développées dans l'UE' / 'Instanciations des "
                                            "blocs de compétences' -- code and description.")
    campus: str = Field(description="The campus/site the course is taught on (e.g. Brest, Rennes, "
                         "Nantes), from the 'UE proposée sur le site de' field.")
    responsables: list[str] = Field(description="Names of the UE responsable(s), exactly as listed "
                                     "in the Responsable(s) field.")


def load_cache():
    if os.path.exists(CACHE_PATH):
        return json.load(open(CACHE_PATH))
    return []


def save_cache(records):
    json.dump(records, open(CACHE_PATH, "w"), ensure_ascii=False, indent=2)


def find_ue_code(text):
    match = re.search(r"Code UE\s*\t?\s*(\S[\w-]*)", text)
    return match.group(1) if match else None


def deduplicated_files(files):
    """Keep only the first fiche seen for each UE code."""
    seen_codes = set()
    kept = []
    for filename in files:
        text = open(os.path.join(TAF_DIR, filename)).read()
        code = find_ue_code(text)
        if code and code in seen_codes:
            continue
        if code:
            seen_codes.add(code)
        kept.append((filename, text))
    return kept


def main(limit=None):
    llm = ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", google_api_key=os.environ["GOOGLE_API_KEY"])
    structured_llm = llm.with_structured_output(FicheExtract)

    files = sorted(f for f in os.listdir(TAF_DIR) if f.endswith(".txt"))
    to_process = deduplicated_files(files)
    print(f"{len(files)} files -> {len(to_process)} after deduplicating by UE code")

    records = load_cache()
    done_codes = {r["ue_code"] for r in records}
    print(f"{len(records)} already cached, resuming")

    if limit:
        to_process = to_process[:limit]

    delay = 60 / REQUESTS_PER_MINUTE
    for filename, text in to_process:
        code = find_ue_code(text)
        if code and code in done_codes:
            continue

        start = time.time()
        try:
            result = structured_llm.invoke(
                f"Extract the pedagogical content from this course fiche:\n\n{text}")
            records.append({"ue_code": result.ue_code, "title": result.title,
                             "description": result.description,
                             "learning_outcome": result.learning_outcome,
                             "competencies": [c.model_dump() for c in result.competencies],
                             "campus": result.campus,
                             "responsables": result.responsables, "source_file": filename})
            save_cache(records)  # write after every fiche -- resumable if interrupted
            print(f"  [{len(records)}] {result.ue_code}: {result.title}")
        except Exception as error:
            print(f"  FAILED on {filename}: {error}")

        elapsed = time.time() - start
        if elapsed < delay:
            time.sleep(delay - elapsed)

    print(f"\nDone: {len(records)} fiches cleaned, saved to {CACHE_PATH}")


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=limit)
