"""Explicit portrait slots for the tutorial, independent of the 250 case slots.

Reuses the registry's validated path lookup and pixmap caches. Character names
and professions come only from public metadata, never from the solution key.
"""

from src.gui.assets.portrait_registry import PortraitMappingEntry, PortraitRegistry


_SLOTS = {
    "A1": "prof_analyst_v01.png", "B1": "prof_baker_v01.png",
    "C1": "prof_doctor_v01.png", "D1": "prof_engineer_v01.png",
    "A2": "prof_florist_v01.png", "B2": "prof_guard_v01.png",
    "C2": "prof_historian_v01.png", "D2": "prof_illustrator_v01.png",
    "A3": "prof_journalist_v01.png", "B3": "prof_librarian_v01.png",
    "C3": "prof_musician_v01.png", "D3": "prof_carpenter_v01.png",
    "A4": "prof_analyst_v02.png", "B4": "prof_baker_v02.png",
    "C4": "prof_doctor_v02.png", "D4": "prof_engineer_v02.png",
}


class TutorialPortraitRegistry(PortraitRegistry):
    def __init__(self):
        super().__init__()
        self._tutorial_mappings = {}

    def set_tutorial_characters(self, characters):
        self._tutorial_mappings = {
            c.cell_id: PortraitMappingEntry(
                f"tutorial_{c.cell_id}", "tutorial_4x4", c.cell_id, c.name, c.profession,
                c.profession, _SLOTS[c.cell_id], "", _SLOTS[c.cell_id],
                f"portraits/{_SLOTS[c.cell_id]}",
            ) for c in characters
        }

    def get_mapping(self, puzzle_id, cell_id):
        if puzzle_id == "tutorial_4x4":
            return self._tutorial_mappings.get(cell_id)
        return super().get_mapping(puzzle_id, cell_id)
