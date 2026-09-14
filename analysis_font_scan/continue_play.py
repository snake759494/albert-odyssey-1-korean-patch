"""Resume the verified game using real joypad inputs; save each reviewed step."""
import ctypes as C
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
commands = sys.argv[1].split(",") if len(sys.argv) > 1 else ["wait:1"]
qa = os.environ.get("AO_QA") == "1"
out = Path(os.environ.get("AO_REVIEW_DIR", ROOT / ("analysis_font_scan/ending_review" if qa else "analysis_font_scan/continuous_review")))
out.mkdir(exist_ok=True)
rom_path=Path(os.environ.get("AO_ROM", ROOT / "Albert Odyssey - Korean Full.sfc"))
rom_hash = hashlib.sha256(rom_path.read_bytes()).hexdigest()
hash_path = out / "rom_sha256.txt"
if hash_path.exists() and hash_path.read_text().strip() != rom_hash:
    raise RuntimeError("ROM changed: replay_continuous.py must regenerate the saved state first")
runner = ROOT / "analysis_font_scan/run_headless.py"
sys.argv = [str(runner), str(rom_path), str(out)]
ns = {"__file__": str(runner), "__name__": "continuous_core"}
exec(compile(runner.read_text().split("for frame in range(5001):")[0], str(runner), "exec"), ns)
core = ns["core"]
core.retro_unserialize.argtypes = [C.c_void_p, C.c_size_t]
core.retro_unserialize.restype = C.c_bool
state_path = out / "latest.state"
initial = ROOT / "analysis_font_scan/ai_review_story/frame42000.state"
state = C.create_string_buffer((state_path if state_path.exists() else initial).read_bytes())
assert core.retro_unserialize(state, len(state.raw) - 1)
ram = (C.c_ubyte * 131072).from_address(core.retro_get_memory_data(2))
move_points = os.environ.get("AO_MOVE_POINTS")
if qa and move_points is not None:
    assert 0 <= int(move_points) <= 15
    ram[0x8D] = int(move_points)
    for address in range(0x2B68, 0x2B6C):
        ram[address] = int(move_points)
if qa and os.environ.get("AO_NO_STAT_ASSIST") != "1":
    # Test-state assistance only; shipped ROM and story flags are untouched.
    for base in (0x200, 0x240, 0x280):
        ram[base + 8] = 0x0F
        ram[base + 9] = 0x27
        if os.environ.get("AO_REFRESH_ACTIONS") == "1" and ram[base + 2] != 0:
            ram[base + 2] = 0xC0
        ram[base + 3] = (ram[base + 3] & 0xF0) | 0x0E
buttons = {"b": 0, "y": 1, "select": 2, "start": 3, "up": 4, "down": 5,
           "left": 6, "right": 7, "a": 8, "x": 9, "l": 10, "r": 11}
pressed = set()
@ns["INPUT"]
def inp(port, device, index, ident):
    return int(port == int(os.environ.get("AO_PORT", "0")) and ident in pressed)
core.retro_set_input_state(inp)
log_path = out / "steps.jsonl"
step = len(log_path.read_text().splitlines()) + 1 if log_path.exists() else 1
for command in commands:
    key, duration = command.split(":")
    pressed = {buttons[k] for k in key.split("+")} if key != "wait" else set()
    cursor_before=bytes(ram[0xA3:0xA5])
    for _ in range(240 if duration == "tile" else int(duration)):
        core.retro_run()
        if duration == "tile" and bytes(ram[0xA3:0xA5]) != cursor_before:
            break
ns["frame"] = step
ns["capture"]()
(out / f"frame{step:04d}.state").replace(state_path)
for kind in (2, 3):
    (out / f"frame{step:04d}_mem{kind}.bin").replace(out / f"latest_mem{kind}.bin")
with log_path.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"step": step, "inputs": commands, "image": f"frame{step:04d}.png", "rom_sha256": rom_hash, "qa_assistance": qa and os.environ.get("AO_NO_STAT_ASSIST") != "1", "refresh_actions": os.environ.get("AO_REFRESH_ACTIONS") == "1", "move_points_override": move_points}) + "\n")
hash_path.write_text(rom_hash)
core.retro_unload_game()
core.retro_deinit()
print(out / f"frame{step:04d}.png")
