# Atlas household coordinator

A Home Assistant custom integration that lets a voice/chat assistant ("Atlas") control a household's lights, lighting scenes and blinds safely. It also runs timers.

It is an exported copy for cloud reviews and tests. The canonical code lives in the owner's private home project. **This copy contains no real household data**: the map is an independently designed small house (12 rooms, 25 lights, 11 scenes, 4 blinds, 3 media players), not a renamed household, and the test copy uses Home Assistant's public demo devices. The time zone (Australia/Sydney) and AU/AUD settings in `testcopy/configuration.yaml` are deliberate regional test defaults (the DST tests need a real zone).

## What the coordinator guarantees (all in code, `custom_components/atlas_household/core.py`)

- **Handles only.** The model names handles from an allowed-target map (`targets.json`). It never supplies an entity ID, a service name or a consent flag. Unknown fields are rejected.
- **Never list.** No energy, battery, inverter, lock, alarm, door-opener or gate target is accepted, in the map or in the person's words.
- **Skip if already.** A fresh state read comes first, and nothing is sent when the device is already as asked.
- **"Done" means read back.** A result is "done" only when every device read back as asked. Otherwise it is `not_verified` or `failed`, never a false "done".
- **Blinds need a yes.** It must be a plain yes, in a later turn, to the exact question asked, within 60 s, with the plan unchanged.
- **Receipts and undo.** Every action has a receipt with a before-image, and undo works for 10 minutes. There is a 30-day log.
- **Timers.** Up to 24 h ahead, in a durable queue. A Home Assistant restart cancels waiting timers, with a notice; nothing is ever replayed. DST times that are skipped or doubled are asked back.
- **Media and AC** are not v1 tools.

## Layout

| Path | What |
| --- | --- |
| `custom_components/atlas_household/` | The integration: `core.py` (pure Python, the rules), `tools.py` (tool schemas in HA's Ollama format), `fake.py` (recording stand-in that sends nothing), `api.py` / `__init__.py` / `config_flow.py` (HA wiring), `targets.json` (the synthetic map; never installable) |
| `tests/` | `test_core.py` etc. (offline), `run_codex40.py` (52 cases), `run_redteam41.py` (Codex 41 coordinator side), `test_dst.py` (needs tzdata; runs in the test copy), `run_testcopy.py` (through HA's real LLM API on the test copy) |
| `packs/` | The Codex 40 pack, and the Codex 41 cases the coordinator runner uses (RT001 and RT042 oracles recomputed for the synthetic map) |
| `testcopy/` | A portable Docker test copy: demo devices only, no network discovery, no cloud |

## Running the tests

```bash
python -I -W ignore::ResourceWarning -m unittest discover -s tests      # offline (DST tests skip without tzdata)
python testcopy/setup_testcopy.py                                       # start and onboard the throwaway HA (Docker)
python -I tests/run_testcopy.py                                         # 10 scenarios through HA's real path (restarts the container)
```

Each of the following has a separate command:
- DST tests inside the test copy, where tzdata is available: copy `custom_components/` and `tests/test_dst.py` into `devha-config/atlas-tests/`, then run `docker exec atlas-ha-test sh -c "cd /config/atlas-tests/tests && python3 -B -m unittest test_dst"`.
- `python -I tests/run_codex40.py` and `python -I tests/run_redteam41.py` rewrite their results files. That's fine here; they are git-ignored.

## Rules for cloud sessions

- **Never** point anything at a real Home Assistant, a real network address, or real devices. Use only the local test copy (127.0.0.1:18123).
- **Never commit** `devha-config/`. It holds the throwaway login.
- **Don't weaken a rule to make a test pass.** The safety rules above are the product. A failing test is a finding: report it.
- **Changes go back as patches.**
  - Send findings and proposed diffs, and say which tests prove them.
  - The owner's Home Assistant project reviews and applies them in its canonical copy. That includes an independent review and its own test runs.
  - Nothing here is merged automatically, and nothing here is installed on a real home.
- Keep the synthetic map synthetic. Don't add real names, IDs or addresses.
