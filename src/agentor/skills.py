import json
import os
from dataclasses import dataclass

import frontmatter


@dataclass
class Skills:
    name: str
    description: str
    location: str

    @staticmethod
    def load_from_path(path: str) -> dict:
        """
        Parse metadata from a file or folder.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        if os.path.isdir(path) and os.path.exists(os.path.join(path, "SKILL.md")):
            return Skills.load_from_path(os.path.join(path, "SKILL.md"))

        if not path.endswith(".md"):
            raise ValueError("File must be a markdown file")

        data = frontmatter.load(path)
        name = data.get("name")
        description = data.get("description")
        location = path
        return Skills(name, description, location)

    def to_xml(self) -> str:
        return f"""
<skill>
  <name>{self.name}</name>
  <description>{self.description}</description>
  <location>{self.location}</location>
</skill>
"""

    def to_json(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__)
