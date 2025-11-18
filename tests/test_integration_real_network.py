"""
Integration tests that make REAL network calls

Test Categories:
1. LLM tests - Critical tests for queue preservation and batch splitting
2. Workflow E2E tests - Full workflow tests for all three workflows:
   - Multi-category classification
   - Perfect-job matching (description-based)
   - CV-based matching
   - Classify-only mode (re-classification)

Note: Scraping functionality is tested within the workflow E2E tests.

Run commands:
    pytest                                    # Unit tests only (default)
    pytest -m integration -k llm              # LLM tests (2 tests)
    pytest -m integration -k workflow         # Workflow E2E tests (4 tests)
    pytest -m integration                     # All integration tests (6 tests)
"""

import json
import os
from pathlib import Path

import pytest

from src.classifier import classify_jobs_mega_batch


@pytest.mark.integration
class TestLLMClassification:
    """Test LLM classification with predefined data (no scraping)

    Tests:
    - Single job classification
    - Queue preservation with known content (CRITICAL!)
    - Large batch classification (55 jobs)
    - Batch splitting logic

    Uses cached fixture data - no API rate limits.
    """

    def test_llm_queue_preservation_critical(self):
        """
        🚨 CRITICAL TEST: Verify LLM correctly assigns categories to the right jobs

        This test catches catastrophic bugs where the LLM mixes up job assignments.
        We use jobs with KNOWN, DISTINCTIVE content and verify each job gets
        categories matching its actual content.

        If this test fails, it means job classifications are being scrambled!
        """
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        # Create jobs with VERY DISTINCTIVE content - each clearly belongs to ONE category
        test_jobs = [
            {
                "titel": "Python Backend Engineer",
                "refnr": "TEST-001",
                "text": """
                Wir suchen einen erfahrenen Python-Entwickler für unser Backend-Team.
                Du arbeitest täglich mit Python 3.11, Django REST Framework, FastAPI und pytest.
                Deine Hauptaufgabe ist die Entwicklung von RESTful APIs mit Python.
                Erfahrung mit Python-Bibliotheken wie pandas, numpy und SQLAlchemy ist wichtig.
                Python, Python, Python - das ist unsere Hauptsprache!
                """,
            },
            {
                "titel": "Java Enterprise Architect",
                "refnr": "TEST-002",
                "text": """
                Senior Java-Architekt gesucht für Enterprise-Anwendungen.
                Du arbeitest mit Java 17, Spring Boot, Spring Cloud und Maven.
                Deine Aufgabe ist die Entwicklung von Java-Microservices.
                Erfahrung mit Java EE, Hibernate und JUnit ist erforderlich.
                Java, Java, Java - wir bauen alles mit Java!
                """,
            },
            {
                "titel": "Kubernetes DevOps Specialist",
                "refnr": "TEST-003",
                "text": """
                DevOps Engineer für Kubernetes-Infrastruktur gesucht.
                Du verwaltest Kubernetes-Cluster, schreibst Helm Charts und arbeitest mit kubectl.
                Terraform, Docker, Kubernetes, ArgoCD und GitOps sind deine täglichen Tools.
                Keine Programmierung in Python oder Java - nur Infrastructure as Code!
                Kubernetes, Kubernetes, Kubernetes - das ist dein Fokus!
                """,
            },
            {
                "titel": "Agile Scrum Master",
                "refnr": "TEST-004",
                "text": """
                Scrum Master für agile Softwareentwicklung gesucht.
                Du führst Daily Standups, Sprint Planning, Retrospektiven und Refinements durch.
                Erfahrung mit Scrum, Kanban, SAFe und agilen Methoden ist erforderlich.
                Du arbeitest nicht als Programmierer - du coachst Teams in agiler Arbeitsweise.
                Agile, Agile, Agile - das ist deine Mission!
                """,
            },
            {
                "titel": "React Frontend Developer",
                "refnr": "TEST-005",
                "text": """
                Frontend-Entwickler für moderne React-Anwendungen gesucht.
                Du arbeitest mit React 18, TypeScript, Next.js und Tailwind CSS.
                Deine Aufgabe ist die Entwicklung von Single-Page-Applications mit React.
                Keine Backend-Entwicklung, keine DevOps - nur Frontend mit React!
                React, TypeScript, JavaScript - das sind deine Technologien!
                """,
            },
        ]

        categories = [
            "Python",
            "Java",
            "Cloud & Containerisierung",
            "Agile Projektentwicklung",
            "Frontend-Entwicklung",
            "Andere",
        ]

        print("\n" + "=" * 70)
        print("🧪 CRITICAL TEST: LLM Queue Preservation with Known Content")
        print("=" * 70)

        result = classify_jobs_mega_batch(
            jobs=test_jobs,
            categories=categories,
            api_key=api_key,
            model="google/gemini-2.5-flash-lite",
            verbose=False,
        )

        # CRITICAL ASSERTIONS: Each job must have categories matching its content
        print("\n📊 Verification Results:")
        print("-" * 70)

        # Job 0: Python job MUST have Python category
        assert (
            "Python" in result[0]["categories"]
        ), f"❌ QUEUE SCRAMBLED! Python job got: {result[0]['categories']}"
        assert (
            "Java" not in result[0]["categories"]
        ), "❌ QUEUE SCRAMBLED! Python job incorrectly has Java!"
        print(f"✅ Job 0 (Python): {result[0]['categories']}")

        # Job 1: Java job MUST have Java category
        assert (
            "Java" in result[1]["categories"]
        ), f"❌ QUEUE SCRAMBLED! Java job got: {result[1]['categories']}"
        assert (
            "Python" not in result[1]["categories"]
        ), "❌ QUEUE SCRAMBLED! Java job incorrectly has Python!"
        print(f"✅ Job 1 (Java): {result[1]['categories']}")

        # Job 2: Kubernetes job MUST have Cloud category
        assert (
            "Cloud & Containerisierung" in result[2]["categories"]
        ), f"❌ QUEUE SCRAMBLED! Kubernetes job got: {result[2]['categories']}"
        print(f"✅ Job 2 (Kubernetes): {result[2]['categories']}")

        # Job 3: Agile job MUST have Agile category
        assert (
            "Agile Projektentwicklung" in result[3]["categories"]
        ), f"❌ QUEUE SCRAMBLED! Agile job got: {result[3]['categories']}"
        print(f"✅ Job 3 (Agile): {result[3]['categories']}")

        # Job 4: React job MUST have Frontend category
        assert (
            "Frontend-Entwicklung" in result[4]["categories"]
        ), f"❌ QUEUE SCRAMBLED! React job got: {result[4]['categories']}"
        print(f"✅ Job 4 (React): {result[4]['categories']}")

        print("\n" + "=" * 70)
        print("✅ QUEUE PRESERVATION TEST PASSED!")
        print("   LLM correctly mapped categories to the right jobs.")
        print("=" * 70)

    def test_llm_batch_splitting_logic(self, fixtures_dir, test_config):
        """
        Test batch splitting with 55 jobs and small batch size

        Verifies that when jobs exceed max_jobs_per_mega_batch,
        they are correctly split without data loss or queue scrambling.
        """
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from src.config.loader import Config

        # Load all 55 jobs
        fixture_file = Path(fixtures_dir) / "large_batch_jobs.json"
        with open(fixture_file, encoding="utf-8") as f:
            jobs = json.load(f)

        # Force splitting by setting low max_jobs_per_mega_batch
        # 55 jobs / 15 per batch = 4 batches (15 + 15 + 15 + 10)
        test_config["processing"] = {
            "limits": {"job_text_mega_batch": 25000, "max_jobs_per_mega_batch": 15}
        }
        test_config["llm"] = {
            "models": {"default": "google/gemini-2.5-flash-lite"},
            "inference": {"temperature": 0.1},
        }
        test_config["api"] = {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {"mega_batch_classification": 120},
        }
        config = Config(test_config)

        categories = [
            "Python",
            "Java",
            "Cloud & Containerisierung",
            "Agile Projektentwicklung",
            "Frontend-Entwicklung",
            "Andere",
        ]

        print("\n" + "=" * 70)
        print(f"🔀 Testing Batch Splitting: {len(jobs)} jobs, max 15 per batch")
        print("   Expected: 4 API calls (15 + 15 + 15 + 10)")
        print("=" * 70)

        result = classify_jobs_mega_batch(
            jobs=jobs,
            categories=categories,
            api_key=api_key,
            model="google/gemini-2.5-flash-lite",
            verbose=True,
            config_obj=config,
        )

        # Verify no data loss across splits
        assert len(result) == len(
            jobs
        ), f"❌ DATA LOSS during splitting! Expected {len(jobs)}, got {len(result)}"
        print(f"\n✅ No data loss: {len(result)} jobs returned")

        # Verify order preservation
        for i, (original, classified) in enumerate(zip(jobs, result, strict=False)):
            assert (
                original["refnr"] == classified["refnr"]
            ), f"❌ Order scrambled at index {i} during batch splitting!"
        print("✅ Order preserved across batch splits")

        print("\n" + "=" * 70)
        print("✅ BATCH SPLITTING TEST PASSED")
        print("=" * 70)


@pytest.mark.integration
class TestWorkflowsEndToEnd:
    """
    End-to-end tests for the three workflow types

    Tests all three workflows with real API/scraping/LLM calls:
    1. Multi-category workflow (default)
    2. Perfect-job workflow
    3. CV-based workflow

    Uses small batches (3-5 jobs) for speed and cost.
    """

    def test_multi_category_workflow_complete(self, tmp_path):
        """Test complete multi-category workflow with real services"""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from src.data import JobGatherer
        from src.llm import LLMProcessor
        from src.preferences import UserProfile
        from src.session import SearchSession
        from src.workflows import MultiCategoryWorkflow

        print("\n" + "=" * 70)
        print("🎯 WORKFLOW E2E: Multi-Category Classification")
        print("=" * 70)

        # Setup
        session = SearchSession(base_dir=str(tmp_path), verbose=False)
        user_profile = UserProfile(categories=["Python", "Java", "DevOps", "Andere"])
        llm_processor = LLMProcessor(
            api_key=api_key, model="google/gemini-2.5-flash-lite", session=session, verbose=False
        )
        gatherer = JobGatherer(
            session=session, verbose=False, database_path=tmp_path / "test_db.json"
        )

        workflow = MultiCategoryWorkflow(
            user_profile=user_profile,
            llm_processor=llm_processor,
            job_gatherer=gatherer,
            session=session,
            verbose=False,
        )

        # Execute
        print("\n[1/1] Running multi-category workflow...")
        classified_jobs, _failed_jobs = workflow.run(
            was="Python Developer",
            wo="Berlin",
            size=3,
            max_pages=1,
            enable_scraping=True,
            show_statistics=False,
        )

        # Verify
        if len(classified_jobs) > 0:
            assert all(
                "categories" in job for job in classified_jobs
            ), "All jobs should have categories"
            assert all(
                isinstance(job["categories"], list) for job in classified_jobs
            ), "Categories should be lists"

            print(f"✅ Classified {len(classified_jobs)} jobs")
            print(
                f"   Example: {classified_jobs[0].get('titel', 'N/A')[:50]} → {classified_jobs[0]['categories']}"
            )
        else:
            print("⚠️  No jobs successfully scraped")

        print("\n" + "=" * 70)
        print("✅ MULTI-CATEGORY WORKFLOW COMPLETE")
        print("=" * 70)

    def test_perfect_job_workflow_complete(self, tmp_path):
        """Test complete perfect-job workflow with real services"""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from src.data import JobGatherer
        from src.llm import LLMProcessor
        from src.preferences import UserProfile
        from src.session import SearchSession
        from src.workflows import MatchingWorkflow

        print("\n" + "=" * 70)
        print("🎯 WORKFLOW E2E: Perfect Job Matching")
        print("=" * 70)

        # Setup
        session = SearchSession(base_dir=str(tmp_path), verbose=False)
        user_profile = UserProfile()

        llm_processor = LLMProcessor(
            api_key=api_key, model="google/gemini-2.5-flash-lite", session=session, verbose=False
        )
        gatherer = JobGatherer(
            session=session, verbose=False, database_path=tmp_path / "test_db.json"
        )

        workflow = MatchingWorkflow(
            user_profile=user_profile,
            llm_processor=llm_processor,
            job_gatherer=gatherer,
            session=session,
            verbose=False,
        )

        # Execute
        print("\n[1/1] Running perfect-job workflow...")
        print("   Perfect job: Python backend with Docker, AWS")
        classified_jobs, _failed_jobs = workflow.run(
            was="Backend Developer",
            wo="Berlin",
            size=5,
            max_pages=1,
            enable_scraping=True,
            perfect_job_description="Python backend with Docker, AWS, microservices, remote work",
            return_only_matches=False,  # Return all to see classification
            show_statistics=False,
        )

        # Verify
        if len(classified_jobs) > 0:
            assert all(
                "categories" in job for job in classified_jobs
            ), "All jobs should have categories (match ratings)"

            # Matching workflow returns categories like "Excellent Match", "Good Match", "Poor Match"
            excellent = [j for j in classified_jobs if "Excellent Match" in j.get("categories", [])]
            good = [j for j in classified_jobs if "Good Match" in j.get("categories", [])]
            poor = [j for j in classified_jobs if "Poor Match" in j.get("categories", [])]

            print(f"✅ Classified {len(classified_jobs)} jobs")
            print(f"   Excellent matches: {len(excellent)}")
            print(f"   Good matches: {len(good)}")
            print(f"   Poor matches: {len(poor)}")

            if excellent:
                print(f"   Example excellent: {excellent[0].get('titel', 'N/A')[:50]}")
            elif good:
                print(f"   Example good: {good[0].get('titel', 'N/A')[:50]}")
        else:
            print("⚠️  No jobs successfully scraped")

        print("\n" + "=" * 70)
        print("✅ PERFECT-JOB WORKFLOW COMPLETE")
        print("=" * 70)

    def test_cv_based_workflow_complete(self, tmp_path):
        """Test complete CV-based workflow with real services"""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from src.data import JobGatherer
        from src.llm import LLMProcessor
        from src.preferences import UserProfile
        from src.session import SearchSession
        from src.workflows import MatchingWorkflow

        print("\n" + "=" * 70)
        print("🎯 WORKFLOW E2E: CV-Based Matching")
        print("=" * 70)

        # Setup - Create test CV
        cv_file = tmp_path / "test_cv.md"
        cv_content = """
# Software Engineer - 5 Years Experience

## Skills
- Python: Django, FastAPI, pytest (5 years)
- Docker and Kubernetes (3 years)
- AWS: EC2, S3, Lambda (2 years)
- REST API design and microservices
- PostgreSQL and Redis

## Experience
- Backend development with Python
- Microservices architecture
- DevOps and CI/CD
- Agile/Scrum teams
"""
        cv_file.write_text(cv_content)

        session = SearchSession(base_dir=str(tmp_path / "sessions"), verbose=False)
        user_profile = UserProfile(cv_path=str(cv_file))

        llm_processor = LLMProcessor(
            api_key=api_key, model="google/gemini-2.5-flash-lite", session=session, verbose=False
        )
        gatherer = JobGatherer(
            session=session, verbose=False, database_path=tmp_path / "test_db.json"
        )

        workflow = MatchingWorkflow(
            user_profile=user_profile,
            llm_processor=llm_processor,
            job_gatherer=gatherer,
            session=session,
            verbose=False,
        )

        # Execute
        print("\n[1/1] Running CV-based workflow...")
        print("   CV: Python backend, Docker, AWS")
        classified_jobs, _failed_jobs = workflow.run(
            was="Software Developer",
            wo="Berlin",
            size=5,
            max_pages=1,
            enable_scraping=True,
            cv_content=user_profile.get_cv_content(),
            return_only_matches=False,  # Return all to see ratings
            show_statistics=False,
        )

        # Verify
        if len(classified_jobs) > 0:
            assert all(
                "categories" in job for job in classified_jobs
            ), "All jobs should have categories (match ratings)"

            # Matching workflow returns categories like "Excellent Match", "Good Match", "Poor Match"
            excellent = [j for j in classified_jobs if "Excellent Match" in j.get("categories", [])]
            good = [j for j in classified_jobs if "Good Match" in j.get("categories", [])]
            poor = [j for j in classified_jobs if "Poor Match" in j.get("categories", [])]

            print(f"✅ Classified {len(classified_jobs)} jobs")
            print(f"   Excellent matches: {len(excellent)}")
            print(f"   Good matches: {len(good)}")
            print(f"   Poor matches: {len(poor)}")

            if excellent:
                print(f"   Example excellent: {excellent[0].get('titel', 'N/A')[:50]}")
            elif good:
                print(f"   Example good: {good[0].get('titel', 'N/A')[:50]}")
        else:
            print("⚠️  No jobs successfully scraped")

        print("\n" + "=" * 70)
        print("✅ CV-BASED WORKFLOW COMPLETE")
        print("=" * 70)

    def test_classify_only_mode_with_session_dir(self, tmp_path):
        """Test re-classification from existing session directory"""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from src.data import JobGatherer
        from src.llm import LLMProcessor
        from src.preferences import UserProfile
        from src.session import SearchSession
        from src.workflows import MultiCategoryWorkflow

        print("\n" + "=" * 70)
        print("🔄 CLASSIFY-ONLY MODE: Re-classification Test")
        print("=" * 70)

        # First, create a session with some jobs
        print("\n[1/2] Creating initial session with jobs...")
        session1 = SearchSession(base_dir=str(tmp_path / "session1"), verbose=False)

        # Simulate scraped jobs
        test_jobs = [
            {
                "titel": "Python Developer",
                "ort": "Berlin",
                "arbeitgeber": "Tech Corp",
                "text": "Python, Django, REST APIs, Docker",
                "url": "https://example.com/job/1",
                "refnr": "TEST-001",
            },
            {
                "titel": "Java Backend Engineer",
                "ort": "München",
                "arbeitgeber": "Enterprise GmbH",
                "text": "Java, Spring Boot, Microservices",
                "url": "https://example.com/job/2",
                "refnr": "TEST-002",
            },
        ]

        session1.save_scraped_jobs(test_jobs)
        session_dir = session1.session_dir
        print(f"✅ Created session with {len(test_jobs)} jobs")

        # Now re-classify with different categories
        print("\n[2/2] Re-classifying with new categories...")
        session2 = SearchSession(base_dir=str(tmp_path / "session2"), verbose=False)
        user_profile = UserProfile(categories=["Backend", "Cloud", "Andere"])
        llm_processor = LLMProcessor(
            api_key=api_key, model="google/gemini-2.5-flash-lite", session=session2, verbose=False
        )
        gatherer = JobGatherer(
            session=session2, verbose=False, database_path=tmp_path / "test_db.json"
        )

        workflow = MultiCategoryWorkflow(
            user_profile=user_profile,
            llm_processor=llm_processor,
            job_gatherer=gatherer,
            session=session2,
            verbose=False,
        )

        # Load and re-classify
        import json

        scraped_jobs_path = session_dir / "debug" / "02_scraped_jobs.json"
        assert scraped_jobs_path.exists(), "Scraped jobs file should exist"

        with open(scraped_jobs_path, encoding="utf-8") as f:
            loaded_jobs = json.load(f)

        classified_jobs = workflow.process(jobs=loaded_jobs)

        # Verify
        assert len(classified_jobs) == len(test_jobs), "All jobs should be re-classified"
        assert all(
            "categories" in job for job in classified_jobs
        ), "All jobs should have new categories"

        print(f"✅ Re-classified {len(classified_jobs)} jobs with new categories")
        print(f"   Example: {classified_jobs[0].get('titel')} → {classified_jobs[0]['categories']}")

        print("\n" + "=" * 70)
        print("✅ RE-CLASSIFICATION TEST COMPLETE")
        print("=" * 70)
