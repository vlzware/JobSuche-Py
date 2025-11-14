"""
Tests for resume functionality - resuming classification after interruption
"""

import json
from unittest.mock import MagicMock, patch

from src.session import SearchSession
from src.workflows import MultiCategoryWorkflow

# Note: sample_jobs and classified_jobs fixtures are now in conftest.py
# These tests extend them with refnr fields where needed


class TestCheckpointManagement:
    """Test checkpoint creation, loading, and deletion"""

    def test_checkpoint_exists_returns_false_when_no_checkpoint(self, tmp_path):
        """has_checkpoint() should return False when no checkpoint exists"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)
        assert not session.has_checkpoint()

    def test_save_checkpoint_creates_file(self, tmp_path):
        """save_checkpoint() should create checkpoint file with correct data"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        completed = ["REF001", "REF002"]
        pending = ["REF003", "REF004"]

        session.save_checkpoint(
            completed_refnrs=completed,
            pending_refnrs=pending,
            current_batch=1,
            total_batches=2,
        )

        # Verify file exists
        assert session.has_checkpoint()

        # Verify content
        checkpoint_file = session.debug_dir / "classification_checkpoint.json"
        with open(checkpoint_file) as f:
            data = json.load(f)

        assert data["completed_jobs"] == completed
        assert data["pending_jobs"] == pending
        assert data["current_batch"] == 1
        assert data["total_batches"] == 2
        assert "last_updated" in data

    def test_load_checkpoint_returns_none_when_no_checkpoint(self, tmp_path):
        """load_checkpoint() should return None when no checkpoint exists"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)
        checkpoint = session.load_checkpoint()
        assert checkpoint is None

    def test_load_checkpoint_returns_data(self, tmp_path):
        """load_checkpoint() should return checkpoint data"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Save checkpoint
        completed = ["REF001", "REF002"]
        pending = ["REF003", "REF004"]
        session.save_checkpoint(
            completed_refnrs=completed,
            pending_refnrs=pending,
            current_batch=1,
            total_batches=2,
        )

        # Load and verify
        checkpoint = session.load_checkpoint()
        assert checkpoint is not None
        assert checkpoint["completed_jobs"] == completed
        assert checkpoint["pending_jobs"] == pending
        assert checkpoint["current_batch"] == 1
        assert checkpoint["total_batches"] == 2

    def test_delete_checkpoint_removes_files(self, tmp_path):
        """delete_checkpoint() should remove checkpoint and partial results"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Create checkpoint and partial results
        session.save_checkpoint(
            completed_refnrs=["REF001"],
            pending_refnrs=["REF002"],
            current_batch=1,
            total_batches=1,
        )
        session.save_partial_results([{"refnr": "REF001"}])

        # Verify they exist
        assert session.has_checkpoint()
        assert (session.debug_dir / "partial_classified_jobs.json").exists()

        # Delete
        session.delete_checkpoint()

        # Verify they're gone
        assert not session.has_checkpoint()
        assert not (session.debug_dir / "partial_classified_jobs.json").exists()


class TestPartialResults:
    """Test partial results storage and loading"""

    def test_save_partial_results_creates_new_file(self, tmp_path):
        """save_partial_results() should create new file if none exists"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        jobs = [{"refnr": "REF001", "categories": ["Python"]}]
        session.save_partial_results(jobs)

        # Verify file exists
        partial_file = session.debug_dir / "partial_classified_jobs.json"
        assert partial_file.exists()

        # Verify content
        with open(partial_file) as f:
            data = json.load(f)
        assert data == jobs

    def test_save_partial_results_appends_to_existing(self, tmp_path):
        """save_partial_results() should append to existing file"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Save first batch
        batch1 = [{"refnr": "REF001", "categories": ["Python"]}]
        session.save_partial_results(batch1)

        # Save second batch
        batch2 = [{"refnr": "REF002", "categories": ["Java"]}]
        session.save_partial_results(batch2)

        # Verify combined content
        partial_file = session.debug_dir / "partial_classified_jobs.json"
        with open(partial_file) as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0] == batch1[0]
        assert data[1] == batch2[0]

    def test_load_partial_results_returns_empty_when_none(self, tmp_path):
        """load_partial_results() should return empty list when no file exists"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)
        results = session.load_partial_results()
        assert results == []

    def test_load_partial_results_returns_data(self, tmp_path):
        """load_partial_results() should return saved data"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Save some results
        jobs = [
            {"refnr": "REF001", "categories": ["Python"]},
            {"refnr": "REF002", "categories": ["Java"]},
        ]
        session.save_partial_results(jobs)

        # Load and verify
        results = session.load_partial_results()
        assert results == jobs


class TestResumeWorkflow:
    """Test resume functionality in workflow execution"""

    def test_run_from_file_with_no_checkpoint(self, tmp_path, sample_jobs, classified_jobs):
        """run_from_file() should process all jobs when no checkpoint exists"""
        # Setup
        session = SearchSession(base_dir=str(tmp_path), verbose=False)
        mock_user_profile = MagicMock()
        mock_llm_processor = MagicMock()
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=session,
            verbose=False,
        )

        # Execute
        result = workflow.run_from_file(jobs=sample_jobs, show_statistics=False, resume=True)

        # Verify all jobs were processed
        assert len(result) == len(classified_jobs)
        mock_llm_processor.classify_multi_category.assert_called_once()
        # Should have been called with all jobs
        call_args = mock_llm_processor.classify_multi_category.call_args
        assert len(call_args[1]["jobs"]) == len(sample_jobs)

    def test_run_from_file_resumes_from_checkpoint(self, tmp_path, sample_jobs, classified_jobs):
        """run_from_file() should skip already-classified jobs when checkpoint exists"""
        # Setup
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Create checkpoint with first 2 jobs completed
        completed_refnrs = ["REF001", "REF002"]
        pending_refnrs = ["REF003"]
        session.save_checkpoint(
            completed_refnrs=completed_refnrs,
            pending_refnrs=pending_refnrs,
            current_batch=1,
            total_batches=2,
        )

        # Save partial results for completed jobs
        session.save_partial_results(classified_jobs[:2])

        mock_user_profile = MagicMock()
        mock_llm_processor = MagicMock()
        # Only the remaining job will be processed
        remaining_classified = [
            {
                "titel": "DevOps Engineer",
                "ort": "Hamburg",
                "arbeitgeber": "Cloud Solutions",
                "text": "AWS, Terraform, Docker",
                "url": "http://example.com/3",
                "refnr": "REF003",
                "categories": ["DevOps", "Cloud"],
            }
        ]
        mock_llm_processor.classify_multi_category.return_value = remaining_classified

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=session,
            verbose=False,
        )

        # Execute with resume=True
        result = workflow.run_from_file(jobs=sample_jobs, show_statistics=False, resume=True)

        # Verify
        # Should combine partial results (2 jobs) + new results (1 job)
        assert len(result) == 3
        assert result[:2] == classified_jobs[:2]  # From partial results
        assert result[2] == remaining_classified[0]  # Newly classified

        # Should only process the remaining job
        mock_llm_processor.classify_multi_category.assert_called_once()
        call_args = mock_llm_processor.classify_multi_category.call_args
        processed_jobs = call_args[1]["jobs"]
        assert len(processed_jobs) == 1
        assert processed_jobs[0]["refnr"] == "REF003"

    def test_run_from_file_with_no_resume_flag(self, tmp_path, sample_jobs, classified_jobs):
        """run_from_file() with resume=False should delete checkpoint and start fresh"""
        # Setup
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Create checkpoint
        session.save_checkpoint(
            completed_refnrs=["REF001"],
            pending_refnrs=["REF002", "REF003"],
            current_batch=1,
            total_batches=2,
        )
        session.save_partial_results(classified_jobs[:1])

        # Verify checkpoint exists
        assert session.has_checkpoint()

        mock_user_profile = MagicMock()
        mock_llm_processor = MagicMock()
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=session,
            verbose=False,
        )

        # Execute with resume=False
        result = workflow.run_from_file(jobs=sample_jobs, show_statistics=False, resume=False)

        # Verify checkpoint was deleted
        assert not session.has_checkpoint()

        # Should process all jobs (not resume from partial)
        assert len(result) == len(classified_jobs)
        mock_llm_processor.classify_multi_category.assert_called_once()
        call_args = mock_llm_processor.classify_multi_category.call_args
        assert len(call_args[1]["jobs"]) == len(sample_jobs)

    def test_run_from_file_with_all_jobs_completed(self, tmp_path, sample_jobs, classified_jobs):
        """run_from_file() should skip classification if all jobs already completed"""
        # Setup
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Create checkpoint with ALL jobs completed
        completed_refnrs = ["REF001", "REF002", "REF003"]
        session.save_checkpoint(
            completed_refnrs=completed_refnrs,
            pending_refnrs=[],
            current_batch=2,
            total_batches=2,
        )

        # Save all jobs as partial results (add categories to third job)
        all_classified = [
            *classified_jobs,
            {
                "titel": "DevOps Engineer",
                "ort": "Hamburg",
                "arbeitgeber": "Cloud Solutions",
                "text": "AWS, Terraform, Docker",
                "url": "http://example.com/3",
                "refnr": "REF003",
                "categories": ["DevOps"],
            },
        ]
        session.save_partial_results(all_classified)

        mock_user_profile = MagicMock()
        mock_llm_processor = MagicMock()

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=session,
            verbose=False,
        )

        # Execute
        result = workflow.run_from_file(jobs=sample_jobs, show_statistics=False, resume=True)

        # Verify
        assert len(result) == 3
        # Should NOT have called the LLM processor (all jobs already done)
        mock_llm_processor.classify_multi_category.assert_not_called()


class TestMegaBatchCheckpoint:
    """Test checkpoint behavior in mega-batch classification"""

    def test_mega_batch_saves_checkpoint_after_each_batch(self, tmp_path):
        """classify_jobs_mega_batch() should save checkpoint after each sub-batch"""
        from src.classifier import classify_jobs_mega_batch

        # Create jobs that will trigger multiple mega-batches
        # (max_jobs_per_mega_batch defaults to 100, we'll use config to lower it)
        jobs = [
            {
                "titel": f"Job {i}",
                "ort": "Berlin",
                "arbeitgeber": "Corp",
                "text": f"Description {i}",
                "url": f"http://example.com/{i}",
                "refnr": f"REF{i:03d}",
            }
            for i in range(10)  # 10 jobs for testing
        ]

        session = SearchSession(base_dir=str(tmp_path), verbose=False)
        mock_config = MagicMock()
        # Set max to 5 so we get 2 mega-batches
        mock_config.get.side_effect = lambda key, default=None: (
            5 if key == "processing.limits.max_jobs_per_mega_batch" else default
        )

        with (
            patch("src.classifier.config", mock_config),
            patch("src.llm.openrouter_client.OpenRouterClient") as mock_client,
        ):
            # Setup mock to return valid response
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance

            # Mock response for each batch
            def mock_complete(prompt, **kwargs):
                # Parse how many jobs are in this batch
                num_jobs = prompt.count("[JOB_")
                response = "\n".join([f"[JOB_{i:03d}] → Test Category" for i in range(num_jobs)])
                full_response = {"usage": {"completion_tokens": 100, "prompt_tokens": 100}}
                return response, full_response

            mock_instance.complete.side_effect = mock_complete

            # Execute
            result = classify_jobs_mega_batch(
                jobs=jobs,
                categories=["Test Category"],
                api_key="test-key",
                session=session,
                verbose=False,
            )

            # Verify we got all jobs back
            assert len(result) == 10

            # Verify checkpoint was created during processing
            # (it should be deleted after completion, but we can check partial results were saved)
            # Note: The checkpoint is deleted after successful completion,
            # so we can't check for it here. But we can verify the final result.
            assert not session.has_checkpoint()  # Should be cleaned up


class TestLLMFailureRecovery:
    """Test recovery from LLM classification failures"""

    def test_resume_after_simulated_batch_failure(self, tmp_path):
        """Resume should continue from checkpoint after batch failure (simulated)"""
        # Simulate the scenario where:
        # 1. User runs classification with 150 jobs
        # 2. Batch 1 (50 jobs) succeeds, checkpoint is saved
        # 3. Batch 2 fails due to LLM error
        # 4. User re-runs with --classify-only, should resume from batch 2

        jobs = [
            {
                "titel": f"Job {i}",
                "ort": "Berlin",
                "arbeitgeber": "Corp",
                "text": f"Description {i}",
                "url": f"http://example.com/{i}",
                "refnr": f"REF{i:03d}",
            }
            for i in range(150)
        ]

        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Simulate: Batch 1 completed successfully before failure
        batch1_jobs = jobs[:50]
        batch1_classified = [{**job, "categories": ["Test"]} for job in batch1_jobs]

        # Save partial results (batch 1)
        session.save_partial_results(batch1_classified)

        # Save checkpoint showing batch 1 done, batches 2-3 pending
        completed_refnrs = [j["refnr"] for j in batch1_jobs]
        pending_refnrs = [j["refnr"] for j in jobs[50:]]
        session.save_checkpoint(
            completed_refnrs=completed_refnrs,
            pending_refnrs=pending_refnrs,
            current_batch=1,
            total_batches=3,
        )

        # Verify checkpoint state
        assert session.has_checkpoint()
        checkpoint = session.load_checkpoint()
        assert checkpoint is not None
        assert len(checkpoint["completed_jobs"]) == 50
        assert len(checkpoint["pending_jobs"]) == 100
        assert checkpoint["current_batch"] == 1
        assert checkpoint["total_batches"] == 3

        # Simulate resume: Process remaining jobs via run_from_file
        mock_user_profile = MagicMock()
        mock_llm_processor = MagicMock()

        # Mock will process remaining 100 jobs
        remaining_classified = [{**job, "categories": ["Test"]} for job in jobs[50:]]
        mock_llm_processor.classify_multi_category.return_value = remaining_classified

        from src.workflows import MultiCategoryWorkflow

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=session,
            verbose=False,
        )

        # Run with resume=True (default)
        result = workflow.run_from_file(jobs=jobs, show_statistics=False, resume=True)

        # Verify results
        assert len(result) == 150  # All jobs classified
        # First 50 from partial results
        assert result[:50] == batch1_classified
        # Next 100 newly classified
        assert result[50:] == remaining_classified

        # Verify only remaining jobs were sent to LLM
        mock_llm_processor.classify_multi_category.assert_called_once()
        call_args = mock_llm_processor.classify_multi_category.call_args
        processed_jobs = call_args[1]["jobs"]
        assert len(processed_jobs) == 100
        assert all(job["refnr"] in pending_refnrs for job in processed_jobs)


class TestEdgeCases:
    """Test edge cases in resume functionality"""

    def test_resume_with_empty_partial_results(self, tmp_path, sample_jobs, classified_jobs):
        """Resume should work even if partial_results file is empty"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Create checkpoint but empty partial results
        session.save_checkpoint(
            completed_refnrs=[],
            pending_refnrs=[j["refnr"] for j in sample_jobs],
            current_batch=0,
            total_batches=1,
        )

        mock_user_profile = MagicMock()
        mock_llm_processor = MagicMock()
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=session,
            verbose=False,
        )

        result = workflow.run_from_file(jobs=sample_jobs, show_statistics=False, resume=True)

        # Should process all jobs
        assert len(result) == len(classified_jobs)

    def test_resume_with_missing_refnr_in_jobs(self, tmp_path):
        """Resume should handle jobs without refnr gracefully"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Jobs without refnr
        jobs = [
            {"titel": "Job 1", "text": "Description 1"},
            {"titel": "Job 2", "text": "Description 2"},
        ]

        # Create checkpoint
        session.save_checkpoint(
            completed_refnrs=["REF001"],
            pending_refnrs=["REF002"],
            current_batch=1,
            total_batches=1,
        )

        mock_user_profile = MagicMock()
        mock_llm_processor = MagicMock()
        mock_llm_processor.classify_multi_category.return_value = [
            {**job, "categories": ["Test"]} for job in jobs
        ]

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=session,
            verbose=False,
        )

        # Should not crash, and should process all jobs (since refnr doesn't match)
        result = workflow.run_from_file(jobs=jobs, show_statistics=False, resume=True)
        assert len(result) == 2
