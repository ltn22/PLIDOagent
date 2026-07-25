# PLIDOagent

Course materials for the "Agentic AI" course, built around a running example: a philosophy
professor who writes an assignment, has it answered by several LLMs, and grades the results.

## Course structure

* [`Part_1_philosopher.ipynb`](Part_1_philosopher.ipynb) — Part 1: setting up the working
  environment (uv, Ollama, API keys) and querying different LLM servers through a common API.
  Further parts will be added as the course progresses.

## Do I need uv to open the notebooks?

No. A `.ipynb` file is plain text (JSON), so you can **read** it without installing anything:

* on GitHub/GitLab it renders directly in the browser,
* in VS Code, the built-in notebook viewer displays it even before any Python environment is set up.

You only need **uv** (and a Python environment) to actually **run** the code cells and query the
LLMs. The exact steps are given inside `Part_1_philosopher.ipynb` (section "Working Environment");
in short:

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. `uv self update` to check the installation
3. `uv sync` to create the `.venv` and install the dependencies listed in `pyproject.toml`
4. In VS Code / Jupyter, select the resulting virtual environment as the notebook's kernel
5. Create a `.env` file at the root of the project with your API keys (`RENNES_API_KEY`,
   `GOOGLE_API_KEY`, ...) — see the notebook for where to obtain them
