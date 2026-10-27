"""AvatarCast-native declarative overlay components.

A component declares *what* appears on *which word* of the timeline.
It never hard-codes seconds, and it never invents data: if the required
props are missing, the component is dropped (not rendered with a guess)
and the drop is reported so the caller can see it.

Components shipped here are AvatarCast's own set. They are not a pack
imported from another project, and their names are deliberately generic:
PriceTag, FactCard, MapRoute, QuoteCard.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# component name -> required props (all must be present and non-empty)
COMPONENT_SPECS: dict[str, tuple[str, ...]] = {
    "PriceTag": ("value",),
    "FactCard": ("claim", "evidence"),
    "MapRoute": ("places",),
    "QuoteCard": ("quote", "source"),
}


@dataclass
class Component:
    use: str
    at: str  # "<segment_id>:<anchor text>", resolved against the timeline
    props: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return a list of problems; empty means the component is renderable."""
        problems: list[str] = []
        if self.use not in COMPONENT_SPECS:
            problems.append(f"unknown component: {self.use!r}")
            return problems
        if not self.at or ":" not in self.at:
            problems.append("at must be '<segment_id>:<anchor text>'")
        for key in COMPONENT_SPECS[self.use]:
            value = self.props.get(key)
            if value is None or value == "" or value == []:
                problems.append(f"missing required prop {key!r} for {self.use}")
        return problems


def filter_renderable(raw: list[dict]) -> tuple[list[Component], list[dict]]:
    """Split raw component specs into renderable ones and dropped ones.

    Dropped entries are returned with their problems, so nothing is
    silently skipped: the caller logs them into qa.json / edit.json.
    """
    ok: list[Component] = []
    dropped: list[dict] = []
    for item in raw:
        comp = Component(
            use=item.get("use", ""),
            at=item.get("at", ""),
            props=item.get("props", {}) or {},
        )
        problems = comp.validate()
        if problems:
            dropped.append({"spec": item, "problems": problems})
        else:
            ok.append(comp)
    return ok, dropped
