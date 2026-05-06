from pathlib import Path

from agents import function_tool
from pydantic.dataclasses import dataclass

from src.utils import LoggerSetup

logger = LoggerSetup("SkillsTool")


@dataclass
class SkillManifest:
    name: str
    description: str


def _parse_skill_manifest(path: Path) -> SkillManifest | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    try:
        end = text.index("---", 3)
    except ValueError:
        return None
    front_matter = text[3:end].strip()
    data: dict[str, str] = {}
    for line in front_matter.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip()
    name = data.get("name", "")
    description = data.get("description", "")
    if not name:
        return None
    return SkillManifest(name=name, description=description)


def discover_skills(skills_dir: Path = Path("skills")) -> dict[str, SkillManifest]:
    manifests: dict[str, SkillManifest] = {}
    if not skills_dir.exists():
        return manifests
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            manifest = _parse_skill_manifest(skill_md)
            if manifest:
                manifests[manifest.name] = manifest
    return manifests


def make_skill_tools(skills_dir: Path = Path("skills")):
    manifests = discover_skills(skills_dir)
    logger.info("Discovered {n} skills", n=len(manifests))

    @function_tool(
        name_override="list_skills",
        description_override="List all available skills with their descriptions.",
    )
    async def list_skills() -> str:
        """List available skills."""
        if not manifests:
            return "No skills available."
        lines = [f"- {name}: {m.description}" for name, m in manifests.items()]
        return "\n".join(lines)

    @function_tool(
        name_override="read_skill",
        description_override="Read the full instructions for a skill by name.",
    )
    async def read_skill(skill_name: str) -> str:
        """Read the full SKILL.md instructions for a skill.

        Args:
            skill_name: The name of the skill to read
        """
        if skill_name not in manifests:
            return f"Unknown skill: {skill_name!r}. Use list_skills to see available skills."
        skill_path = skills_dir / skill_name / "SKILL.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        return f"Skill file not found for {skill_name!r}"

    return [list_skills, read_skill]
