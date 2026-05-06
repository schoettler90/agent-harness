from harness.tools.skills import SkillManifest, _parse_skill_manifest, discover_skills


def test_discover_skills(sample_skills_dir):
    manifests = discover_skills(sample_skills_dir)
    assert "echo" in manifests
    assert isinstance(manifests["echo"], SkillManifest)
    assert manifests["echo"].description == "Echo tool for testing"


def test_discover_skills_empty(tmp_path):
    manifests = discover_skills(tmp_path / "nonexistent")
    assert manifests == {}


def test_parse_skill_manifest(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text("---\nname: test\ndescription: A test skill\n---\n# Test")
    result = _parse_skill_manifest(md)
    assert result is not None
    assert result.name == "test"
    assert result.description == "A test skill"


def test_parse_skill_manifest_no_frontmatter(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text("# No frontmatter here")
    result = _parse_skill_manifest(md)
    assert result is None
