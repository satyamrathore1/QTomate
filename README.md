# Queue & Subscription Adder

A small Streamlit app that lets you pick a queue type, store code, region,
and country code, then automatically pulls latest, creates a feature branch,
appends the rendered YAML block to your target file, commits, and pushes —
so all you need to do afterward is open the pull request on GitHub.

## 1. Prerequisites

- Python 3.9+
- `git` installed and available on your PATH
- A local clone of the target repository, already configured with a remote
  and working authentication (SSH key or a credential helper) — i.e. you can
  already run `git pull` / `git push` in that repo manually without being
  prompted in a way this script can't handle.

## 2. Install

```bash
cd queue_subscription_app
pip install -r requirements.txt
```

## 3. Configure

Open `config.py` and fill in:

- `REPO_PATH` — absolute path to your local clone
- `YAML_FILE_RELATIVE_PATH` — path to the target `.yaml` file, relative to
  the repo root
- `BASE_BRANCH` — usually `main` or `master`
- `STORE_CODES`, `REGIONS`, `COUNTRY_CODES` — your fixed dropdown lists

## 4. Add / edit queue templates

Each file in `templates/` is one queue type. `TRANSACTIONAL_CONSUMER_V1.txt`
is already set up from your sample, with `{STORE}`, `{REGION}`, and
`{COUNTRY}` as placeholders.

To add a new queue type, copy an existing template, adjust the fixed parts,
and replace the values that should vary with `{STORE}`, `{REGION}`, or
`{COUNTRY}` as needed. The filename (minus `.txt`) is what shows up in the
dropdown.

**Please double-check `TRANSACTIONAL_CONSUMER_V1.txt` against your real
requirements** — one assumption was made: the literal `GL` in the
`stockKeepingUnit/stock/update` topic lines was left as a fixed value
(not tied to the Region dropdown), since it looked like "Global" rather
than a region code. Let me know if that should actually track the selected
region instead.

## 5. Run

```bash
streamlit run app.py
```

This opens a browser tab. Pick your options, review the preview, and click
**Execute**. The app will:

1. Check the repo has no uncommitted changes (fails safely if it does)
2. Checkout and pull the base branch
3. Create/switch to a feature branch
4. Append the rendered block to the end of the target YAML file
5. `git add`, `git commit`, `git push`

You then open the PR on GitHub yourself.

## Notes / things to double check

- The app appends **raw text**, not a YAML-library re-serialization — this
  preserves your comments and exact formatting, but it also means it does
  **no YAML validation**. Consider giving the resulting file a lint pass
  (e.g. `yamllint`) or eyeballing the diff before opening the PR.
- No duplicate-check is done — if you run the same store/region/queue combo
  twice, it will append twice. Say the word if you'd like a check added that
  scans the file for an existing entry with the same name first.
- If your git setup ever prompts for username/password interactively,
  `subprocess` will hang waiting for input that can't be typed into the
  Streamlit log — get non-interactive push working from a normal terminal
  first (SSH key or a stored credential helper), then this will work too.
