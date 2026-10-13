from __future__ import annotations


def derive_section_tags(chapter_title: str, section_title: str, section_path: str) -> list[str]:
    """Classify chunks for Azure Search tag-boost scoring (Collection(Edm.String) field)."""
    blob = f"{chapter_title} {section_title} {section_path}".upper()
    tags: list[str] = []

    if any(
        token in blob
        for token in ("TROUBLESHOOTING", "DIAGNOSTIC", "FAULT", "ERROR CODE", "TROUBLE SHOOT")
    ):
        tags.append("troubleshooting")
    if any(token in blob for token in ("MAINTENANCE", "SERVICE DATA", "LUBRICATION")):
        tags.append("maintenance")
    if any(token in blob for token in ("SAFETY", "WARNING", "CAUTION", "DANGER")):
        tags.append("safety")
    if any(token in blob for token in ("SPECIFICATION", "SPECIFICATIONS", "CAPACITY", "RATING")):
        tags.append("specifications")
    if any(token in blob for token in ("OPERATION", "OPERATING", "CONTROLS")):
        tags.append("operation")

    if not tags:
        tags.append("general")
    return tags
