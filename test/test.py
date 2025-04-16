import asyncio
import random
import time
from meseex import MeseexBox, MrMeseex, gather_results


def test_basic_job_manager_operations():
    """Test basic JobManager functionality with mixed sync and async methods."""
    async def async_phase1(job: MrMeseex):
        await asyncio.sleep(0.1)
        job.set_task_data("Please let me die")
        return "Fulfilling my purpose " + job.input

    def sync_phase2(job: MrMeseex):
        time.sleep(random.randint(1, 4))
        return job.prev_task_output + ". Working on it"

    async def async_phase3(job: MrMeseex):
        await asyncio.sleep(0.1)
        task_data = job.get_task_data(0)
        return job.prev_task_output + " Done. " + task_data

    tasks = {
        "Init": async_phase1,
        "Look at me": sync_phase2,
        "Processing": async_phase3
    }

    job_manager = MeseexBox(tasks)
    
    # Submit multiple jobs with slight delays
    job1 = job_manager.summon("testing MeseexBox", "Meseex1")
    job2 = job_manager.summon("annoying MeseexBox", "Meseex2")
    
    # Wait for jobs to complete
    results = gather_results([job1, job2], raise_on_error=True)

    # Verify job1 results
    assert job1.is_terminal
    assert job2.is_terminal
   
    assert results['Meseex1'] == "Fulfilling my purpose testing MeseexBox. Working on it Done. Please let me die"
    assert results['Meseex2'] == "Fulfilling my purpose annoying MeseexBox. Working on it Done. Please let me die"

    job_manager.shutdown()


def test_custom_phase_order():
    """Test JobManager with a custom phase order."""
    async def task1(job: MrMeseex):
        await asyncio.sleep(0.1)
        job.set_task_data("phase1")

    def task2(job: MrMeseex):
        time.sleep(0.1)
        job.set_task_data("phase2")
        return "Im ending in 2"

    async def task3(job: MrMeseex):
        await asyncio.sleep(0.1)
        job.set_task_data("phase3")
        return "Holla"

    # Define custom phase order
    phase_methods = [task1, task2, task3]

    job_manager = MeseexBox(phase_methods)
    
    # Create job with custom phase order
    job = MrMeseex(tasks=[2, 1], name="Mr. Skip task 1")
    job_manager.summon_meseex(job)
    
    # Wait for job to complete
    job.wait_for_result()
    
    # Verify results
    assert job.is_terminal
    assert job.result == "Im ending in 2"
    
    job_manager.shutdown()


def test_job_manager_with_errors():
    """Test JobManager handling of job errors."""
    async def async_phase1(job: MrMeseex):
        await asyncio.sleep(0.1)
        return "phase1"

    def sync_phase2(job: MrMeseex):
        time.sleep(0.1)
        raise ValueError("Test error in phase2")

    async def async_phase3(job: MrMeseex):
        await asyncio.sleep(0.1)
        job.set_task_data("phase3")

    phase_methods = {
        0: async_phase1,
        1: sync_phase2,
        2: async_phase3
    }

    job_manager = MeseexBox(phase_methods)
    
    job = job_manager.summon("test", "Mr. Error")
    job.wait_for_result()
    # Verify job failed and only completed first phase
    assert job.meseex_id in job_manager.meseex_store.failed_ids
    assert job.result is None
    assert job.task_outputs == {0: "phase1"}
    assert job.error is not None

    job_manager.shutdown()


if __name__ == "__main__":
    test_basic_job_manager_operations()
    test_job_manager_with_errors()
    test_custom_phase_order()


