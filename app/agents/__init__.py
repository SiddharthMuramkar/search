"""ARCHITECTURES: name -> (description, run function). One line for each architecture."""

from app.agents import orchestrator, react, reflection

ARCHITECTURES = {
    "react": ("One agent in a loop: the model chooses each search and when to stop.", react.run),
    "orchestrator": (
        "A planner splits the question; parallel workers search each part; one call writes it up.",
        orchestrator.run,
    ),
    "reflection": (
        "Draft, critic, revise: the critic decides what to search next.",
        reflection.run,
    ),
}
