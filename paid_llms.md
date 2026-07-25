# Getting API keys for well-known (often paid) LLMs

This page is optional: everything in this course works with the free servers (University of Rennes,
Google Gemini) and Ollama running locally. But if you want to compare their answers with other
well-known models — OpenAI's ChatGPT, Anthropic's Claude, Mistral, DeepSeek, or a whole catalog of
models through OpenRouter — here is how to get an API key for each. Most require adding a small
amount of credit (a few euros is enough for this course).

## OpenAI (ChatGPT)

* Go to https://platform.openai.com/ and log in (or create an account).
* Add a small amount of credit under **Settings > Billing**.
* Go to **Settings > API keys**, click **Create new secret key**, and copy it — it is only shown once.
* Add a line in the `.env` file: `OPENAI_API_KEY=<<copied key>>`

## Anthropic (Claude)

* Go to https://console.anthropic.com/ and log in (or create an account).
* Add a small amount of credit under **Settings > Billing**.
* Go to **Settings > API Keys**, click **Create Key**, and copy it — it is only shown once.
* Add a line in the `.env` file: `ANTHROPIC_API_KEY=<<copied key>>`

## Mistral

Mistral is a French company, and their API also has a free tier.

* Go to https://console.mistral.ai/ and log in (or create an account).
* Go to **API Keys**, click **Create new key**, and copy it.
* Add a line in the `.env` file: `MISTRAL_API_KEY=<<copied key>>`

## DeepSeek

* Go to https://platform.deepseek.com/ and log in (or create an account).
* Add a small amount of credit under **Billing**.
* Go to **API keys**, click **Create new API key**, and copy it.
* Add a line in the `.env` file: `DEEPSEEK_API_KEY=<<copied key>>`

## OpenRouter

OpenRouter is not a model provider itself, but a single gateway that gives access to many different
models (OpenAI, Anthropic, Mistral, DeepSeek, and more) — including some free ones — through one
API key and one endpoint.

* Go to https://openrouter.ai/ and log in (or create an account).
* Go to **Keys**, click **Create Key**, and copy it.
* Add a line in the `.env` file: `OPENROUTER_API_KEY=<<copied key>>`

## Using them

Like Rennes, Gemini and Ollama, all of these are queried through the very same `OpenAI` client, just
changing the `base_url` and the key:
* OpenAI: `OpenAI(api_key=os.getenv('OPENAI_API_KEY'))` (no `base_url` needed, it's the default one)
* Mistral, DeepSeek, OpenRouter, Anthropic: same `OpenAI` client, with their respective `base_url`
  (`https://api.mistral.ai/v1`, `https://api.deepseek.com`, `https://openrouter.ai/api/v1`,
  `https://api.anthropic.com/v1/`) and API key

Anthropic's OpenAI-compatible endpoint is currently in beta and does not expose every Claude-specific
feature; for full access to Claude's capabilities, use the native `anthropic` package instead
(`Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))`) — but for the simple chat completions we do in
this course, the `OpenAI` client works just as well and keeps our code consistent across providers.

Remember: `.env` is listed in [`.gitignore`](.gitignore), so these keys never get committed or pushed to GitHub.
