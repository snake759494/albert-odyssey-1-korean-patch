"""Exercise all translated records through the real Snes9x text renderer.

Only the in-memory test ROM redirects the opening's two pointer-map entries.
The shipped ROM is not changed. Restore a clean pre-dialogue state for each
case, press A, then compare the actual VRAM glyph bytes against the font source.
Also simulate all script coexistence groups in both directions and check every
encoded character after every load, including fixed equipment glyphs.
"""
import ctypes as C
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_OFFSETS = {int(value, 16) for value in sys.argv[1:]}
sys.path.insert(0, str(ROOT / "font_export"))
import build_korean_full_patch as build


def tile_bytes(vram, code):
    start = 0x8000 + (code // 16) * 0x200 + (code % 16) * 16
    return vram[start:start + 16] + vram[start + 0x100:start + 0x110]


def main():
    out = ROOT / "analysis_font_scan" / ("ai_review_focus" if REVIEW_OFFSETS else "ai_review")
    out.mkdir(exist_ok=True)
    rom = (ROOT / "Albert Odyssey - Korean Full.sfc").read_bytes()
    audit = json.loads((ROOT / "font_export/korean_full_patch_info.json").read_text(encoding="utf-8"))
    records = json.loads((ROOT / "analysis/full_dialogue_extracted.json").read_text(encoding="utf-8"))["records"]
    by_offset = {int(r["offset"], 16): r for r in records}
    mapping, meta = build.build_glyph_maps()
    # Expected glyph bytes come from independent font rendering, not remap data.
    font = build.ImageFont.truetype("C:/Windows/Fonts/gulim.ttc", 16)
    slots = {c: code+256*table for c,(code,table) in mapping.items()}
    expected = {c: build.korean_tile_bytes(build.korean_glyph(c, font)) for c in {*meta['table1'], *meta['table2']}}
    owners = {slots[c]: c for c in mapping}
    fixed = set(meta["layout"]["protected_glyphs"])
    # Battle names are cached across font loads: their boot-font bytes must
    # already be correct, before any translated record installs shared glyphs.
    boot_vram = b"\0" * 0x8000 + rom[build.FONT_OVERLAY_OFFSET:build.FONT_OVERLAY_OFFSET + build.FONT_OVERLAY_SIZE]
    for char in fixed:
        assert tile_bytes(boot_vram, slots[char]) == expected[char], ("font reload", char)
    static_checks = 0
    for group in meta["coexistence_groups"]:
        for sequence in (group, list(reversed(group))):
            visible = set(fixed)
            for offset in sequence:
                record = by_offset[offset]
                for char, target in record["dynamic_targets"].items():
                    owners[int(target, 16)] = char
                visible.update(c for c in record["korean"] if c in expected)
                for char in visible:
                    assert owners[slots[char]] == char, (record["offset"], char)
                    static_checks += 1

    print(f"static audit passed: {static_checks}", flush=True)
    # Reuse the existing core callbacks, but not the scripted run/unload loop.
    runner = ROOT / "analysis_font_scan/run_headless.py"
    namespace = {"__file__": str(runner), "__name__": "review_core"}
    sys.argv = [str(runner), str(ROOT / "Albert Odyssey - Korean Full.sfc"), str(out)]
    exec(compile(runner.read_text().split("for frame in range(5001):")[0], str(runner), "exec"), namespace)
    core, Info = namespace["core"], namespace["Info"]
    core.retro_unserialize.argtypes = [C.c_void_p, C.c_size_t]
    core.retro_unserialize.restype = C.c_bool
    print("core initialized", flush=True)
    for frame in range(1491):
        namespace["frame"] = frame
        core.retro_run()
    state_size = core.retro_serialize_size()
    state = C.create_string_buffer(state_size)
    assert core.retro_serialize(state, state_size)
    entries = {}
    for i in range(len(records)):
        address = build.TEXT_MAP_OFFSET + i * build.TEXT_MAP_ENTRY_SIZE
        entries[int.from_bytes(rom[address:address + 2], "little")] = address
    print("boot snapshot ready", flush=True)
    test_records = [r for r in records if not REVIEW_OFFSETS or int(r["offset"], 16) in REVIEW_OFFSETS]
    cases = [(r, r) for r in test_records]
    regression_pairs = [
        (0x44650, 0x4465F), (0x41CA4, 0x43E99), (0x43DF0, 0x43E84),
        (0x43EBC, 0x43ECD), (0x43EDF, 0x43F0E), (0x43F26, 0x43F2C),
        (0x43F2C, 0x43F3C), (0x41B59, 0x41B76), (0x41F98, 0x41FB1),
        (0x44327, 0x44342), (0x44353, 0x4436C), (0x41E06, 0x41E21),
    ]
    cases += [(by_offset[a], by_offset[b]) for a, b in regression_pairs]
    results, failures = [], []
    for case_index, pair in enumerate(cases):
        test_rom = bytearray(rom)
        for original, target in zip((0xB911, 0xC674), pair):
            source_entry = entries[int(target["original_pointer"], 16)]
            target_entry = entries[original]
            test_rom[target_entry + 2:target_entry + build.TEXT_MAP_ENTRY_SIZE] = rom[source_entry + 2:source_entry + build.TEXT_MAP_ENTRY_SIZE]
        core.retro_unload_game()
        data = C.create_string_buffer(bytes(test_rom))
        info = Info(b"review.sfc", C.cast(data, C.c_void_p), len(test_rom), None)
        assert core.retro_load_game(C.byref(info))
        assert core.retro_unserialize(state, state_size)
        if case_index == 0: print("first case restored", flush=True)
        for frame in range(1491, 1901):
            namespace["frame"] = frame
            core.retro_run()
        size = core.retro_get_memory_size(3)
        vram = C.string_at(core.retro_get_memory_data(3), size)
        assert vram[0xAA10:0xAA20] == bytes(16), 'A translated record overwrote the background clear tile'
        chars = {c for r in pair for c in r["korean"] if c in expected}
        bad = [c for c in sorted(chars) if tile_bytes(vram, slots[c]) != expected[c]]
        result = {"records": [r["offset"] for r in pair], "text": [r["korean"] for r in pair],
                  "checked_glyphs": len(chars), "mismatched_glyphs": bad}
        results.append(result)
        if bad:
            failures.append(result)
        if REVIEW_OFFSETS or case_index >= len(records) or bad or pair[0]["offset"] in ("0x43E65", "0x41FC4", "0x442B8", "0x442CF"):
            # Existing capture also exports state/RAM; retain only the PNG here.
            namespace["frame"] = case_index
            namespace["capture"]()
            for suffix in (".state", "_mem2.bin", "_mem3.bin"):
                (out / f"frame{case_index:04d}{suffix}").unlink(missing_ok=True)
        if case_index % 25 == 0:
            print(f"reviewed {case_index + 1}/{len(cases)}; failures={len(failures)}", flush=True)
    core.retro_unload_game()
    core.retro_deinit()
    report = {"rom_sha256": hashlib.sha256(rom).hexdigest(), "records": len(test_records),
              "runtime_cases": len(cases), "static_character_checks": static_checks,
              "coexistence_groups": len(meta["coexistence_groups"]),
              "failures": failures, "runtime_results": results,
              "scope": "Selected records through opening dialogue renderer, regression line pairs, and all static coexistence constraints; not full-game playthrough" if REVIEW_OFFSETS else "All extracted records through opening dialogue renderer, regression line pairs, and static coexistence constraints; not full-game playthrough"}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "runtime_results"}, ensure_ascii=False), flush=True)
    assert not failures, "actual VRAM glyph verification failed"


if __name__ == "__main__":
    main()
