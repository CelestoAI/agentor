# Agentor tool examples (end-to-end)

Each file in this folder shows an end-to-end flow:

1. create a tool instance,
1. attach it to an `Agentor` agent,
1. run a prompt through the agent,
1. print `result.final_output`.

## Files

- `calculator.py`
- `exa_search.py`
- `fetch.py`
- `git.py`
- `github.py`
- `gmail.py`
- `linkedin_scraper.py`
- `postgresql.py`
- `scrapegraphai.py`
- `shell.py`
- `shell_smolvm.py`
- `slack.py`
- `timezone.py`
- `weather.py`
- `web_search.py`

## Optional dependencies

Install optional tool extras as needed:

```bash
pip install "agentor[exa,git,postgres,github,slack,scrapegraph]"
```

For Gmail/Google tool examples:

```bash
pip install "agentor[google]"
```

For secure shell runtime with SmolVM:

```bash
pip install smolvm
```

## Run

```bash
python examples/tools/weather.py
```
