"""Deterministic font-slot allocation from script coexistence constraints.

Script scenes (with the verified home/bard/church transitions) are treated
as simultaneously visible, plus six-record
windows across section boundaries. This deliberately includes more text than a
single dialogue box. All menu sections are also combined into one constraint.
Fixed-width names have globally exclusive slots, since their renderer does not
call the translated-record hook. Shared glyphs are reloaded on EVERY use.
"""
import re
from collections import Counter


def allocate_slots(source, translations, fixed_names, available_codes):
    hangul = {c for s in [*translations.values(), *fixed_names.values()]
              for c in s if "가" <= c <= "힣"}
    sections, current, order, menu = [], [], [], []
    in_menu = False
    in_names = False
    scene_names = set()
    for line in source.splitlines():
        if line.startswith("//"):
            in_names = "Names" in line
            if current:
                sections.append(current)
                current = []
            if line == "// Intro Characters Names":
                in_menu = True
            if line == "// Chiberus - Start Of Game":
                in_menu = False
        match = re.match(r"\s*TextStyle[12]\(\$([0-9A-Fa-f]+),", line)
        if match:
            offset = int(match[1], 16)
            # Verified room transitions: the broad "Start Of Game" source
            # section contains the home, bard and church as separate scenes.
            # Keep all lines within each scene together, plus the existing
            # six-record windows spanning every boundary.
            if offset in (0x41B59, 0x41CB9) and current:
                sections.append(current)
                current = []
            current.append(offset)
            order.append(offset)
            if in_menu:
                menu.append(offset)
            if in_names:
                scene_names.update(c for c in translations[offset] if c in hangul)
    if current:
        sections.append(current)
    groups = sections + [menu] + [order[i:i + 6] for i in range(len(order))]
    graph = {c: set() for c in hangul}
    for group in groups:
        chars = {c for offset in group for c in translations[offset] if c in hangul}
        for c in chars:
            graph[c].update(chars - {c})
    fixed = {c for s in fixed_names.values() for c in s if c in hangul}
    # Combat caches name tilemaps before loading the battle font. Name slots
    # must survive that reload without depending on a previous dynamic copy.
    protected = fixed | scene_names
    for c in protected:
        graph[c] = hangul - {c}
        for other in hangul - {c}:
            graph[other].add(c)
    colors = {}
    while len(colors) < len(hangul):
        char = max(hangul - colors.keys(), key=lambda c: (
            len({colors[n] for n in graph[c] if n in colors}), len(graph[c]), c))
        used = {colors[n] for n in graph[char] if n in colors}
        color = next(i for i in range(len(hangul)) if i not in used)
        colors[char] = color
    count = max(colors.values()) + 1
    if count > len(available_codes):
        raise ValueError(f"coexisting font needs {count} slots; only {len(available_codes)} available")
    mapping = {c: available_codes[colors[c]] for c in sorted(hangul)}
    counts = Counter(mapping.values())
    shared = sorted(c for c in mapping if counts[mapping[c]] > 1)
    assert not (set(shared) & protected)
    for c, neighbors in graph.items():
        assert all(mapping[c] != mapping[n] for n in neighbors)
    return mapping, shared, groups, {
        "coexistence_groups": len(groups), "allocated_slots": count,
        "available_slots": len(available_codes), "shared_glyphs": len(shared),
        "protected_fixed_name_glyphs": len(fixed),
        "protected_scene_name_glyphs": len(scene_names),
        "protected_glyphs": sorted(protected),
        "group_rule": "whole script scenes (home/bard/church separated), combined menus, and six adjacent source records",
    }
