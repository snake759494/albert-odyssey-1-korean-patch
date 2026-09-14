"""Replay the reviewed joypad route on a freshly booted rebuilt ROM."""
import ctypes as C
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = Path(os.environ.get('AO_ROUTE_OUT', ROOT / "analysis_font_scan/freeze_route"))
out.mkdir(exist_ok=True)
steps = [json.loads(line) for line in (ROOT / "analysis_font_scan/continuous_review/steps.jsonl").read_text().splitlines()]
runner = ROOT / "analysis_font_scan/run_story_probe.py"
rom_path = Path(os.environ.get('AO_ROM', ROOT / 'Albert Odyssey - Korean Full.sfc'))
sys.argv = [str(runner), str(rom_path), str(out), "42000"]
ns = {"__file__": str(runner), "__name__": "replay_core"}
exec(compile(runner.read_text().split("for frame in range(END_FRAME+1):")[0], str(runner), "exec"), ns)
core = ns["core"]
for frame in range(42001):
    ns["frame"] = frame
    core.retro_run()
    if frame % 10000 == 0:
        print(f"fresh boot {frame}/42000", flush=True)
size = core.retro_serialize_size()
state = C.create_string_buffer(size)
assert core.retro_serialize(state, size)
(out / "boot.state").write_bytes(state.raw)
buttons = {"b": 0, "y": 1, "select": 2, "start": 3, "up": 4, "down": 5,
           "left": 6, "right": 7, "a": 8, "x": 9, "l": 10, "r": 11}
pressed = set()
@ns["INPUT"]
def inp(port, device, index, ident):
    return int(port == 0 and ident in pressed)
core.retro_set_input_state(inp)
for step in steps:
    for command in step["inputs"]:
        key, duration = command.split(":")
        pressed = {buttons[k] for k in key.split("+")} if key != "wait" else set()
        for _ in range(int(duration)):
            core.retro_run()
    ns["frame"] = step["step"]
    ns["capture"]()
    (out / f"frame{step['step']:04d}.state").replace(out / "latest.state")
    for kind in (2, 3):
        (out / f"frame{step['step']:04d}_mem{kind}.bin").replace(out / f"latest_mem{kind}.bin")
    print(f"replayed step {step['step']}/{len(steps)}", flush=True)
core.retro_unload_game()
core.retro_deinit()
rom_hash = hashlib.sha256(rom_path.read_bytes()).hexdigest()
(out / "rom_sha256.txt").write_text(rom_hash)
for step in steps:
    step["rom_sha256"] = rom_hash
(out / "steps.jsonl").write_text("".join(json.dumps(step) + "\n" for step in steps))
