# Core CNF Encoder Documentation

This document covers the Core CNF Encoder implementation completed for the Griductive Solver project according to [TO_DO.md](TO_DO.md) and [AI - Project 2-1.pdf](AI%20-%20Project%202-1.pdf).

## Implemented Files

- [`src/encoder/variable_map.py`](../encoder/variable_map.py) — Deterministic primary variable mapping ($C_i$) and separate auxiliary variable allocation.
- [`src/encoder/cnf_encoder.py`](../encoder/cnf_encoder.py) — Automatic validation and CNF encoding for the 6 core clue templates, proved verdicts, and public knowledge bases ($KB_t$).
- [`src/encoder/__init__.py`](../encoder/__init__.py) — Package exports for `VariableMap`, `CharacterEntry`, `CNFEncoder`, `EncodedKB`, and coordinate utilities.
- [`tests/test_core_encoder.py`](../../tests/test_core_encoder.py) — Standalone unit tests using `Dict` inputs and exhaustive truth-table verification.

---

## 1. Variable Mapping (`VariableMap`)

`VariableMap` creates a deterministic bijection between characters/cells and positive SAT variable IDs:

- **Primary Variables ($C_i$)**: Assigned consecutive IDs `1 .. num_primary`, where `True` means **Criminal** and `False` means **Innocent**.
  - When characters have display names, IDs are sorted alphabetically by name (`(name.casefold(), name, coord)`).
  - When characters are pure grid coordinates (e.g., `VariableMap.from_puzzle({"size": 3})`), IDs are sorted in row-major order (`A1, B1, C1, A2, ...`).
  - Lookup via `get_primary(identifier)` or `resolve_canonical(identifier)` accepts either character name or grid coordinate (case-insensitive).
- **Auxiliary Variables**: Allocated via `allocate_aux(tag)` starting strictly after all primary variables (`num_primary + 1` onward).
  - Namespaces are kept strictly disjoint (`is_primary()`, `is_auxiliary()`).
  - Registering additional primary characters after auxiliary variables are allocated raises `RuntimeError`.
  - `reset_auxiliary()` clears auxiliary variables between fresh $KB_t$ encodings while preserving primary IDs.
  - `decode_model(model)` extracts only primary variables into `{character_key: "CRIMINAL" | "INNOCENT"}`.
- **Grid Region Queries**:
  - `cells_in_row(row)` — All characters in 1-based row `row`.
  - `cells_in_col(col)` — All characters in column letter `col`.
  - `neighbors_of(identifier)` — Up to 8 horizontal/vertical/diagonal neighbors of a cell (excluding the cell itself).

### Initializing `VariableMap`

```python
from src.encoder import VariableMap

# From a puzzle dictionary
vm = VariableMap.from_puzzle({
    "size": 3,
    "characters": {
        "A1": "Abel", "B1": "Bea", "C1": "Clara",
        "A2": "Derek", "B2": "Eliza", "C2": "Franz",
        "A3": "Grant", "B3": "Hannah", "C3": "Ivy",
    },
})

# Or from a list of character names (non-grid)
vm_simple = VariableMap.from_characters(["Abel", "Bea", "Clara"])
```

---

## 2. CNF Encoder (`CNFEncoder`)

`CNFEncoder(var_map, cardinality_encoding="sequential")` converts structured clues (as `Dict`s or duck-typed clue objects) and proved verdicts into standard DIMACS-style CNF clauses (`list[list[int]]`).

### Supported Core Clue Templates

| Clue Type | Logical Meaning | Example `Dict` Input |
|---|---|---|
| `FACT` | $C_i$ or $\neg C_i$ | `{"type": "FACT", "target": "Abel", "status": "INNOCENT"}` |
| `SAME` | $C_i \leftrightarrow C_j$ | `{"type": "SAME", "targets": ["Abel", "Bea"]}` |
| `DIFFERENT` | $C_i \oplus C_j$ | `{"type": "DIFFERENT", "targets": ["Bea", "Clara"]}` |
| `EXACTLY` | $\sum_{i \in R} C_i = k$ | `{"type": "EXACTLY", "k": 2, "region": {"kind": "row", "row": 1}}` |
| `AT_LEAST` | $\sum_{i \in R} C_i \ge k$ | `{"type": "AT_LEAST", "k": 1, "region": {"kind": "column", "column": "B"}}` |
| `AT_MOST` | $\sum_{i \in R} C_i \le k$ | `{"type": "AT_MOST", "k": 2, "region": {"kind": "neighbors", "cell": "B2"}}` |

Additional supported conveniences:
- `"NO"` is normalized to `EXACTLY(0, R)`.
- Flat clue dicts and nested `"params": {...}` dicts are both accepted.
- Region specifications support dict form (`{"kind": "row", "row": 1}`, `{"kind": "column", "column": "B"}`, `{"kind": "neighbors", "cell": "B2"}`, `{"kind": "explicit", "cells": [...]}`), raw lists (`["A1", "B1"]`), and string shorthands (`"row:1"`, `"col:B"`, `"neighbors:B2"`).

### Cardinality Encodings

- **`"sequential"` (default)**: Uses a bidirectional sequential counter ($s_{i,j} \leftrightarrow \sum_{m=0}^{i} l_m \ge j$) with auxiliary variables. For `EXACTLY(k, R)`, symmetry reduction counts $\min(k, |R| - k)$ with a single counter. Every valid primary assignment has a unique auxiliary variable extension.
- **`"binomial"`**: Direct combinatorial clause generation with 0 auxiliary variables (useful for small regions or experimental comparison).
- Boundary cases ($k = 0$ and $k = |R|$) emit direct unit clauses or empty tautologies without auxiliary variables.

### Validation & Knowledge Base Isolation

- Rejects unknown clue types, invalid statuses, unknown characters/cells, out-of-range rows/columns, duplicate or empty explicit regions, identical targets in `SAME`/`DIFFERENT`, and out-of-range counting parameters ($k < 0$ or $k > |R|$ or non-integer $k$).
- `encode_clue` raises `ValueError` if `"revealed": False` is explicitly set.
- `encode_verdicts` encodes proved verdicts as unit clauses and raises `ValueError` on conflicting statuses for the same character (including name/coordinate aliases).
- `encode_kb(revealed_clues, proved_verdicts)` and `encode_public_kb(public_kb)` construct:
  $$KB_t = \text{CNF}(\text{revealed clues}) \land \text{unit clauses}(\text{proved verdicts})$$
  ignoring unrevealed clues and any hidden fields, and returning an `EncodedKB` object with `.clauses`, `.stats()`, and `.to_dimacs()`.

### Usage Example

```python
from src.encoder import CNFEncoder, VariableMap

vm = VariableMap.from_puzzle({
    "size": 2,
    "characters": [
        {"name": "Abel", "coord": "A1"},
        {"name": "Bea", "coord": "B1"},
        {"name": "Clara", "coord": "A2"},
        {"name": "Derek", "coord": "B2"},
    ],
})
encoder = CNFEncoder(vm, cardinality_encoding="sequential")

kb = encoder.encode_kb(
    revealed_clues=[
        {"type": "EXACTLY", "k": 1, "region": {"kind": "row", "row": 1}},
        {"type": "SAME", "targets": ["Bea", "Clara"]},
        {"type": "DIFFERENT", "targets": ["Clara", "Derek"]},
    ],
    proved_verdicts={"Abel": "INNOCENT"},
)

print(kb.stats())
# {'primary_vars': 4, 'auxiliary_vars': ..., 'total_vars': ..., 'clauses': ..., 'clues': 3, 'verdicts': 1}
```

---

## 3. Running Tests

Run the standalone test suite with `pytest`:

```bash
python -m pytest -v tests/test_core_encoder.py
```

The suite verifies:
- Deterministic primary variable ordering (alphabetical and row-major) and strict primary/auxiliary separation.
- Grid region resolution (`row`, `column`, `neighbors`, `explicit`) and parameter validation errors.
- Direct CNF clause outputs for `Dict` clue inputs.
- Exhaustive truth-table equivalence across all $2^n$ assignments for $n \in \{1..8\}$ and $k \in \{0..n\}$ under both `"sequential"` and `"binomial"` encodings (including 1-to-1 auxiliary variable multiplicity for `"sequential"`).
- `KB_t` construction, unrevealed-clue filtering, conflicting-verdict rejection, and `EncodedKB` reporting.
