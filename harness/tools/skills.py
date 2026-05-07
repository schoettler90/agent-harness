from pathlib import Path

from agents import function_tool
from agents.sandbox.capabilities.skills import LocalDirLazySkillSource
from agents.sandbox.entries import LocalDir

from harness.tools import register_tool
from src.utils import LoggerSetup

logger = LoggerSetup("SkillsTool")

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"
SKILLS_PATH = ".agents"  # virtual path label used by the SDK metadata


def _build_source(skills_dir: Path) -> LocalDirLazySkillSource:
    return LocalDirLazySkillSource(source=LocalDir(src=skills_dir))


@register_tool("skills")
def make_skills_tools(skills_dir: Path | None = None, **_: object):
    root = Path(skills_dir or DEFAULT_SKILLS_DIR).resolve()
    source = _build_source(root)

    @function_tool(
        name_override="list_skills",
        description_override=(
            "List available skills with their names and descriptions "
            "(parsed from SKILL.md frontmatter)."
        ),
    )
    async def list_skills() -> str:
        """List skill names and descriptions."""
        metadata = source.list_skill_metadata(skills_path=SKILLS_PATH)
        if not metadata:
            return "(no skills)"
        return "\n".join(f"- **{m.name}**: {m.description}" for m in metadata)

    @function_tool(
        name_override="load_skill",
        description_override="Load a skill's SKILL.md instructions by name.",
    )
    async def load_skill(name: str) -> str:
        """Read the SKILL.md for a named skill.

        Args:
            name: Skill name (matches frontmatter `name` or directory name).
        """
        matches = [
            m
            for m in source.list_skill_metadata(skills_path=SKILLS_PATH)
            if m.name == name or m.path.name == name
        ]
        if not matches:
            return f"Error: skill {name!r} not found"
        if len(matches) > 1:
            return f"Error: skill name {name!r} is ambiguous"
        skill_dir = root / matches[0].path.name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            return f"Error: SKILL.md missing for {name!r}"
        return skill_md.read_text(encoding="utf-8")

    return [list_skills, load_skill]
