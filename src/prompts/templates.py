"""
Prompt templates for LLM-based job classification

This module contains default prompt templates and configuration loading logic.
Users can customize prompts by creating a prompts.yaml file.
"""

from pathlib import Path

from ..config import config

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# CV profile section (shown once in prompt)
CV_PROFILE_TEMPLATE = """You are matching jobs against this candidate's CV. Be STRICT and SELECTIVE.

============================================================
CANDIDATE PROFILE (CV)
============================================================
{cv_content}
============================================================
END OF CANDIDATE PROFILE
============================================================
"""

# Classification criteria (used in category definitions, shown once via build_category_guidance)
CV_CLASSIFICATION_CRITERIA = """Match jobs against the candidate's CV using these criteria (be realistic - expect most jobs to be Poor Match):

**Excellent Match:** Job is a near-perfect fit
- Job's CORE requirements match candidate's PRIMARY specialization and recent experience
- Required technologies/domains are CENTRAL to candidate's proven expertise (not just mentioned peripherally)
- Seniority level matches candidate's experience level
- Industry/domain aligns with candidate's background
- Candidate has demonstrated track record in this exact type of role
- Candidate could start immediately with minimal ramp-up

**Good Match:** Job is realistic but requires adaptation
- Majority of core requirements align with candidate's demonstrated experience
- Missing skills are learnable given candidate's strong foundation
- Domain/industry is closely related to candidate's background
- Candidate has proven ability to work with similar technologies/problems
- CRITICAL: Mere language/tool overlap is insufficient - look for domain and experience alignment

**Poor Match:** Job is NOT a realistic fit (this should be MOST jobs)
- Core requirements diverge significantly from candidate's specialization
- Required experience/expertise is not demonstrated in CV
- Domain/industry is unrelated to candidate's background
- Seniority level mismatch (too junior or too senior)
- Technologies overlap but domain/context is completely different
- Job description is too vague to assess proper fit
- Entry-level positions for experienced candidates (or vice versa)

Evaluation principles:
1. Match on SPECIALIZATION and DOMAIN, not just programming languages
2. Recent experience weighs more heavily than old experience
3. Core expertise vs. peripheral mentions matter
4. Industry/domain context is crucial
5. Be honest and selective - quality over quantity
6. When in doubt between Good and Poor, choose Poor"""

# Legacy template (kept for backward compatibility)
CV_MATCHING_TEMPLATE = CV_PROFILE_TEMPLATE + "\n" + CV_CLASSIFICATION_CRITERIA


def load_custom_prompts(config_path: str | None = None) -> dict[str, str]:
    """
    Load custom prompt templates from YAML config file.

    Args:
        config_path: Path to the prompts config file (defaults to value from paths_config.yaml)

    Returns:
        Dictionary of prompt names to template strings
    """
    if not YAML_AVAILABLE:
        return {}

    if config_path is None:
        config_path = config.get("paths.files.prompts", "prompts.yaml")

    config_file = Path(config_path)
    if not config_file.exists():
        return {}

    try:
        with open(config_file, encoding="utf-8") as f:
            prompts_config = yaml.safe_load(f)

        if not prompts_config or "prompts" not in prompts_config:
            return {}

        prompts = prompts_config["prompts"]

        # Validate structure: must be dict with string keys and string values
        if not isinstance(prompts, dict):
            print(
                f"Warning: 'prompts' in {config_path} must be a dictionary, "
                f"got {type(prompts).__name__}"
            )
            return {}

        # Validate all keys and values are strings
        for key, value in prompts.items():
            if not isinstance(key, str):
                print(
                    f"Warning: Prompt key in {config_path} must be string, got {type(key).__name__}"
                )
                return {}
            if not isinstance(value, str):
                print(
                    f"Warning: Prompt '{key}' in {config_path} must be string, "
                    f"got {type(value).__name__}"
                )
                return {}

        return prompts
    except Exception as e:
        print(f"Warning: Could not load custom prompts from {config_path}: {e}")
        return {}


def get_cv_matching_prompt(cv_content: str, custom_template: str | None = None) -> str:
    """
    Get the CV matching prompt with CV content inserted.

    Args:
        cv_content: The candidate's CV content
        custom_template: Optional custom template (uses default if None)

    Returns:
        Complete prompt with CV content inserted
    """
    template = custom_template or CV_MATCHING_TEMPLATE
    return template.format(cv_content=cv_content)
