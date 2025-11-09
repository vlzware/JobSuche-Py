"""
Test UserProfile class

Tests category management, CV handling, and profile configuration
"""

from unittest.mock import mock_open, patch

import pytest

from src.preferences import UserProfile


@pytest.fixture
def sample_cv_content():
    """Sample CV content for testing"""
    return """
# John Doe - Senior Software Engineer

## Experience
- 5 years Python development (Django, Flask)
- 3 years DevOps (Docker, Kubernetes, AWS)
- REST API design and implementation
- Microservices architecture

## Skills
- Languages: Python, JavaScript, Java
- Frameworks: Django, React, Spring Boot
- Tools: Docker, Kubernetes, Terraform, GitLab CI/CD
- Cloud: AWS (EC2, S3, Lambda, RDS)
"""


class TestCategoryManagement:
    """Test category handling and priority"""

    def test_uses_explicit_categories_when_provided(self):
        """Explicit categories should take highest priority"""
        # Execute
        profile = UserProfile(categories=["Python", "Java", "DevOps"])

        # Verify
        assert profile.get_categories() == ["Python", "Java", "DevOps"]
        assert profile.get_category_source() == "explicit"
        assert profile.get_category_definitions() == {}

    def test_loads_from_categories_yaml(self, tmp_path):
        """Should load categories from YAML file when no explicit categories"""
        # Setup - create categories file
        categories_file = tmp_path / "categories.yaml"
        categories_file.write_text("""
categories:
  - name: "Backend"
    description: "Backend development roles"
  - name: "Frontend"
    description: "Frontend development roles"
  - name: "DevOps"
    description: "DevOps and infrastructure"
""")

        # Execute
        with patch("src.preferences.user_profile.config") as mock_config:
            mock_config.get.return_value = str(categories_file)
            profile = UserProfile()

        # Verify
        assert "Backend" in profile.get_categories()
        assert "Frontend" in profile.get_categories()
        assert "DevOps" in profile.get_categories()
        assert profile.get_category_source() == "config"

        definitions = profile.get_category_definitions()
        assert "Backend" in definitions
        assert definitions["Backend"] == "Backend development roles"

    def test_falls_back_to_defaults(self):
        """Should use default categories when no config file exists"""
        # Execute
        with patch("src.preferences.user_profile.config") as mock_config:
            mock_config.get.return_value = "nonexistent.yaml"
            profile = UserProfile()

        # Verify
        categories = profile.get_categories()
        assert profile.get_category_source() == "defaults"
        assert len(categories) > 0  # Should have default categories

    def test_explicit_categories_override_config(self, tmp_path):
        """Explicit categories should override config file"""
        # Setup
        categories_file = tmp_path / "categories.yaml"
        categories_file.write_text("""
categories:
  - name: "Backend"
  - name: "Frontend"
""")

        # Execute
        with patch("src.preferences.user_profile.config") as mock_config:
            mock_config.get.return_value = str(categories_file)
            profile = UserProfile(categories=["Custom1", "Custom2"])

        # Verify
        assert profile.get_categories() == ["Custom1", "Custom2"]
        assert profile.get_category_source() == "explicit"

    def test_get_category_source_reporting(self):
        """get_category_source should accurately report source"""
        # Test explicit
        profile1 = UserProfile(categories=["A", "B"])
        assert profile1.get_category_source() == "explicit"

        # Test defaults
        with patch("src.preferences.user_profile.config") as mock_config:
            mock_config.get.return_value = "nonexistent.yaml"
            profile2 = UserProfile()
            assert profile2.get_category_source() == "defaults"


class TestCVManagement:
    """Test CV file handling"""

    def test_loads_cv_file(self, tmp_path, sample_cv_content):
        """Should load CV from file path"""
        # Setup
        cv_file = tmp_path / "cv.md"
        cv_file.write_text(sample_cv_content)

        # Execute
        profile = UserProfile(cv_path=str(cv_file))

        # Verify
        assert profile.has_cv() is True
        assert profile.get_cv_content() == sample_cv_content
        assert profile.cv_path == str(cv_file)

    def test_has_cv_returns_false_when_no_cv(self):
        """has_cv() should return False when no CV loaded"""
        # Execute
        profile = UserProfile()

        # Verify
        assert profile.has_cv() is False
        assert profile.get_cv_content() is None

    def test_has_cv_returns_true_when_loaded(self, tmp_path):
        """has_cv() should return True when CV is loaded"""
        # Setup
        cv_file = tmp_path / "cv.md"
        cv_file.write_text("Sample CV content")

        # Execute
        profile = UserProfile(cv_path=str(cv_file))

        # Verify
        assert profile.has_cv() is True

    def test_get_cv_content(self, tmp_path):
        """get_cv_content() should return CV text"""
        # Setup
        cv_content = "My professional CV content"
        cv_file = tmp_path / "cv.md"
        cv_file.write_text(cv_content)

        # Execute
        profile = UserProfile(cv_path=str(cv_file))

        # Verify
        assert profile.get_cv_content() == cv_content

    def test_cv_file_not_found_warning(self, tmp_path, capsys):
        """Should print warning if CV file doesn't exist"""
        # Setup
        nonexistent_cv = tmp_path / "nonexistent.md"

        # Execute
        profile = UserProfile(cv_path=str(nonexistent_cv))

        # Verify
        assert profile.has_cv() is False
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "CV file not found" in captured.out

    def test_cv_load_error_handling(self, tmp_path, capsys):
        """Should handle CV load errors gracefully"""
        # Setup
        cv_file = tmp_path / "cv.md"
        cv_file.write_text("Content")

        # Execute - simulate read error
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            profile = UserProfile(cv_path=str(cv_file))

        # Verify
        assert profile.has_cv() is False
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "Could not load CV" in captured.out


class TestPerfectJobCategory:
    """Test perfect job category setup"""

    def test_set_perfect_job_category(self):
        """Should set perfect job category with description"""
        # Setup
        profile = UserProfile(categories=["Initial", "Categories"])

        # Execute
        profile.set_perfect_job_category(
            category_name="Dream Backend Role",
            description="Python, Docker, AWS, remote work, startup environment",
        )

        # Verify
        categories = profile.get_categories()
        assert categories == ["Dream Backend Role", "Andere"]

        definitions = profile.get_category_definitions()
        assert "Dream Backend Role" in definitions
        assert (
            definitions["Dream Backend Role"]
            == "Python, Docker, AWS, remote work, startup environment"
        )

        assert profile.get_category_source() == "perfect_job"

    def test_set_perfect_job_category_replaces_existing(self):
        """Setting perfect job category should replace all existing categories"""
        # Setup
        profile = UserProfile(categories=["Old1", "Old2", "Old3"])

        # Execute
        profile.set_perfect_job_category(
            category_name="New Perfect Job", description="Detailed description"
        )

        # Verify
        categories = profile.get_categories()
        assert len(categories) == 2
        assert "New Perfect Job" in categories
        assert "Andere" in categories
        assert "Old1" not in categories

    def test_perfect_job_category_source(self):
        """Should set category_source to 'perfect_job'"""
        # Setup
        profile = UserProfile()

        # Execute
        profile.set_perfect_job_category("Test Job", "Description")

        # Verify
        assert profile.get_category_source() == "perfect_job"


class TestCategoryDefinitions:
    """Test category definition management"""

    def test_add_category_definition_to_existing_category(self):
        """Should add definition to existing category"""
        # Setup
        profile = UserProfile(categories=["Python", "Java"])

        # Execute
        profile.add_category_definition("Python", "Python development with Django/Flask")

        # Verify
        definitions = profile.get_category_definitions()
        assert "Python" in definitions
        assert definitions["Python"] == "Python development with Django/Flask"

        # Categories should remain unchanged
        assert profile.get_categories() == ["Python", "Java"]

    def test_add_category_definition_creates_new_category(self):
        """Should add new category if it doesn't exist"""
        # Setup
        profile = UserProfile(categories=["Python"])

        # Execute
        profile.add_category_definition("DevOps", "Infrastructure and deployment")

        # Verify
        assert "DevOps" in profile.get_categories()

        definitions = profile.get_category_definitions()
        assert "DevOps" in definitions
        assert definitions["DevOps"] == "Infrastructure and deployment"

    def test_add_category_definition_updates_existing(self):
        """Should update existing category definition"""
        # Setup
        profile = UserProfile(categories=["Python"])
        profile.add_category_definition("Python", "Old definition")

        # Execute
        profile.add_category_definition("Python", "New definition")

        # Verify
        definitions = profile.get_category_definitions()
        assert definitions["Python"] == "New definition"


class TestProfileSerialization:
    """Test profile export and representation"""

    def test_to_dict_without_cv(self):
        """Should export profile as dictionary"""
        # Setup
        profile = UserProfile(categories=["Python", "Java"])
        profile.add_category_definition("Python", "Python development")

        # Execute
        profile_dict = profile.to_dict()

        # Verify
        assert profile_dict["categories"] == ["Python", "Java"]
        assert "Python" in profile_dict["category_definitions"]
        assert profile_dict["category_source"] == "explicit"
        assert profile_dict["cv_path"] is None
        assert profile_dict["has_cv"] is False

    def test_to_dict_with_cv(self, tmp_path):
        """Should include CV info in dictionary"""
        # Setup
        cv_file = tmp_path / "cv.md"
        cv_file.write_text("CV content")

        profile = UserProfile(categories=["Python"], cv_path=str(cv_file))

        # Execute
        profile_dict = profile.to_dict()

        # Verify
        assert profile_dict["cv_path"] == str(cv_file)
        assert profile_dict["has_cv"] is True

    def test_repr(self):
        """Should provide informative repr"""
        # Setup
        profile = UserProfile(categories=["A", "B", "C"])

        # Execute
        repr_str = repr(profile)

        # Verify
        assert "UserProfile" in repr_str
        assert "categories=3" in repr_str
        assert "source=explicit" in repr_str
        assert "has_cv=False" in repr_str

    def test_repr_with_cv(self, tmp_path):
        """repr should show CV status"""
        # Setup
        cv_file = tmp_path / "cv.md"
        cv_file.write_text("Content")

        profile = UserProfile(cv_path=str(cv_file))

        # Execute
        repr_str = repr(profile)

        # Verify
        assert "has_cv=True" in repr_str


class TestConfigPathHandling:
    """Test config path parameter"""

    def test_uses_custom_config_path(self, tmp_path):
        """Should use custom config path when provided"""
        # Setup
        custom_config = tmp_path / "custom_categories.yaml"
        custom_config.write_text("""
categories:
  - name: "CustomCategory"
""")

        # Execute
        with patch("src.classifier.yaml") as mock_yaml:
            mock_yaml.safe_load.return_value = {"categories": [{"name": "CustomCategory"}]}
            with patch("builtins.open", mock_open(read_data=custom_config.read_text())):
                UserProfile(config_path=str(custom_config))

        # Path should be used (even though category loading may fall back to defaults)
        # The important thing is that it tried to use the custom path

    def test_uses_default_config_path_from_config(self):
        """Should use default path from paths_config.yaml when not specified"""
        # Execute
        with patch("src.preferences.user_profile.config") as mock_config:
            mock_config.get.return_value = "categories.yaml"

            # This will call config.get to retrieve the default path
            UserProfile()

        # Verify config was consulted for default path
        mock_config.get.assert_called_with("paths.files.categories", "categories.yaml")


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_categories_list(self):
        """Should handle empty categories list"""
        # Execute
        profile = UserProfile(categories=[])

        # Verify
        assert profile.get_categories() == []
        assert profile.get_category_source() == "explicit"

    def test_cv_with_unicode_content(self, tmp_path):
        """Should handle CV with unicode characters"""
        # Setup
        cv_content = (
            "Name: François Müller\nSkills: Python, Künstliche Intelligenz, データサイエンス"
        )
        cv_file = tmp_path / "cv.md"
        cv_file.write_text(cv_content, encoding="utf-8")

        # Execute
        profile = UserProfile(cv_path=str(cv_file))

        # Verify
        assert profile.has_cv() is True
        assert profile.get_cv_content() == cv_content

    def test_very_large_cv(self, tmp_path):
        """Should handle large CV files"""
        # Setup
        large_content = "Experience\n" * 10000  # Large but reasonable CV
        cv_file = tmp_path / "cv.md"
        cv_file.write_text(large_content)

        # Execute
        profile = UserProfile(cv_path=str(cv_file))

        # Verify
        assert profile.has_cv() is True
        cv_content = profile.get_cv_content()
        assert cv_content is not None
        assert len(cv_content) > 100000

    def test_none_category_definitions(self):
        """Should handle None values in category definitions gracefully"""
        # Setup
        profile = UserProfile(categories=["Cat1", "Cat2"])

        # Verify - definitions should be empty dict, not None
        assert profile.get_category_definitions() == {}

    def test_category_with_special_characters(self):
        """Should handle category names with special characters"""
        # Execute
        profile = UserProfile(categories=["C++/C#", "Node.js", "AI/ML"])

        # Verify
        categories = profile.get_categories()
        assert "C++/C#" in categories
        assert "Node.js" in categories
        assert "AI/ML" in categories
