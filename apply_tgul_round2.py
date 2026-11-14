#!/usr/bin/env python3
"""Apply the second TGUL integration step to a locally cloned RM27_Client."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "sim/server/main.py"
SCRIPT = ROOT / "sim/run_sim.sh"

if not MAIN.is_file() or not SCRIPT.is_file():
    raise SystemExit("Run this script from the repository root after extracting the zip.")

changes = {}


def replace_once(content, old, new, filename):
    if new in content:
        return content
    if content.count(old) != 1:
        raise RuntimeError(
            f"Expected exactly one occurrence in {filename}: {old!r}; "
            "upstream may have changed. No source files were patched."
        )
    return content.replace(old, new, 1)


main = MAIN.read_text(encoding="utf-8")
main = replace_once(
    main,
    "from server.state_manager import StateManager",
    "from server.state_manager import StateManager\n"
    "from server.tgul2027_rules import MatchMode\n"
    "from server.tgul2027_simulation import "
    "TGULStateManager, TGULMatchSimulationEngine",
    "main.py",
)
main = replace_once(
    main,
    "args = parser.parse_args()",
    "parser.add_argument(\n"
    '    "--tgul-mode",\n'
    "    choices=[mode.value for mode in MatchMode],\n"
    "    default=None,\n"
    "    help='Enable TGUL 2027 simulation instead of the legacy rules',\n"
    ")\n"
    "args = parser.parse_args()",
    "main.py",
)
main = replace_once(
    main,
    "state_manager = StateManager()\n"
    "state_manager.current_robot_id = args.current_robot_id",
    "state_manager = (\n"
    "    TGULStateManager(args.tgul_mode) if args.tgul_mode else StateManager()\n"
    ")\n"
    "state_manager.current_robot_id = args.current_robot_id\n"
    "if args.tgul_mode:\n"
    "    state_manager.sync_current_robot_view()",
    "main.py",
)
main = replace_once(
    main,
    "match_simulation_engine = MatchSimulationEngine(",
    "match_simulation_engine = (\n"
    "    TGULMatchSimulationEngine if args.tgul_mode else MatchSimulationEngine\n"
    ")(",
    "main.py",
)
changes[MAIN] = main

shell = SCRIPT.read_text(encoding="utf-8")
shell = replace_once(
    shell,
    "        --current-robot-id)",
    "        --tgul-mode)\n"
    '            SERVER_ARGS+=("$1" "$2")\n'
    "            shift 2\n"
    "            ;;\n"
    "        --current-robot-id)",
    "run_sim.sh",
)
changes[SCRIPT] = shell

old_rule = ROOT / "sim/server/rmul2027_rules.py"
new_rule = ROOT / "sim/server/tgul2027_rules.py"
old_test = ROOT / "sim/tests/test_rmul2027_rules.py"
new_test = ROOT / "sim/tests/test_tgul2027_rules.py"

for old, new in ((old_rule, new_rule), (old_test, new_test)):
    if old.exists() and new.exists():
        raise RuntimeError(f"Both {old.name} and {new.name} exist; resolve first.")
    if not old.exists() and not new.exists():
        raise FileNotFoundError(
            f"Neither {old} nor {new} exists. Complete round 1 first."
        )
    content = (old if old.exists() else new).read_text(encoding="utf-8")
    content = content.replace("RMUL", "TGUL").replace("rmul", "tgul")
    changes[new] = content

# Verify all inputs before doing any writes.
expected_new_module = ROOT / "sim/server/tgul2027_simulation.py"
expected_new_test = ROOT / "sim/tests/test_tgul2027_integration.py"
if not expected_new_module.exists() or not expected_new_test.exists():
    raise RuntimeError("Extract the full TGUL round 2 zip to the repo root first.")

for old, new in ((old_rule, new_rule), (old_test, new_test)):
    if old.exists():
        old.rename(new)

for path, content in changes.items():
    path.write_text(content, encoding="utf-8")

print("TGUL round 2 integration applied successfully.")
print("Next: run python -m unittest discover -s sim/tests -t sim -p 'test_*.py' -v")
