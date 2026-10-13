"""ARCHITECTURES: name -> (description, run function). One line for each architecture."""

from app.agents import react

ARCHITECTURES = {
    "react": ("One agent in a loop: the model chooses each search and when to stop.", react.run),
}
