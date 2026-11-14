# TGUL 2027 — Round 2 Web integration

## Installation in WSL2 Ubuntu 24.04

Place this zip in `/home/wangyifan/RM27_Client`, then:

    cd /home/wangyifan/RM27_Client
    python3 -m zipfile -e tgul_round2.zip .
    source sim/.venv/bin/activate
    python apply_tgul_round2.py
    python -m unittest discover -s sim/tests -t sim -p 'test_*.py' -v
    git diff --check

Start full 3v3 demo (ensure port 8000 is free):

    bash sim/run_sim.sh --no-video --mqtt-host 127.0.0.1 --mqtt-port 3333 --tgul-mode tgul_3v3 --current-robot-id 1

Infantry duel:

    bash sim/run_sim.sh --no-video --mqtt-host 127.0.0.1 --mqtt-port 3333 --tgul-mode tgul_infantry --current-robot-id 3

The Web 'full' demonstration spans all official phases. 'quick' compresses
that same timeline to 90 seconds; it is NOT a match type.

## What this does

- Renames the existing first-round rules and tests to `tgul2027_*`
  and replaces the corresponding identifiers (without changing rule values).
- Adds opt-in TGUL StateManager and MatchSimulationEngine adapters.
- Keeps the upstream mode unchanged when `--tgul-mode` is omitted.
- Initializes TGUL roster, starting HP, initial allowed ammunition and economy.
- Resets HP on the first self-check stage and advances all match phases.
- Disables automatic old-event and automated radar-message generation
  from the TGUL one-click timeline.

## Known limitations (important)

- This is an integration milestone. Existing MQTT `.proto` and legacy
  publisher are still for the upstream season and are NOT TGUL-compliant.
- Existing Web manual-stage controls and legacy background-loop mechanisms
  are not fully adapted yet. Validate using the ONE-CLICK simulation in full mode.
- TGUL 3v3 uses slots 1/3/4/7 and 101/103/104/107; the default active
  lineup is 1/3/7 and 101/103/107. The reserve infantry slots 4/104 are 0 HP.
- Infantry duel uses only 3/103; other display slots remain as 0 HP placeholders.
- No genuine control-zone/respawn/shooting/economy event-engine logic yet.
- Baseline tests have to be run in your actual WSL clone. The isolated
  sandbox validation used a stub of the upstream StateManager/engine interfaces.
