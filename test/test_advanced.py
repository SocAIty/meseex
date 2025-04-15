import asyncio
import time
import random
from meseex import MeseexBox, MrMeseex, gather_results


class TestingMeseexBox:
    def __init__(self):
        self.job_manager = MeseexBox({
            "I'm Mr. Meseex": self.async_phase1,
            "Golf course": self.async_phase2,
            1: self.sync_phase2,
            2: self.async_phase3
        })
        self.test_data = "Custom data"
        
    async def async_phase1(self, job: MrMeseex):
        await asyncio.sleep(random.randint(1, 3))
        return job.input["test"] + self.test_data
        
    async def async_phase2(self, job: MrMeseex):
        await asyncio.sleep(random.randint(1, 2))
        job.task_progress = 0.2, "Can do."
        await asyncio.sleep(random.randint(1, 2))
        job.task_progress = 0.3, "Going to be a good day."
        await asyncio.sleep(random.randint(1, 2))
        return job.prev_task_output
        
    def sync_phase2(self, job: MrMeseex):
        time.sleep(random.randint(1, 2))
        job.task_progress = 0.2, "Shoulders"
        time.sleep(random.randint(1, 2))
        job.task_progress = 0.3, "Common you can do it Jerry."
        time.sleep(random.randint(1, 2))
        job.task_progress = 0.8, "Almost done."
        time.sleep(random.randint(1, 2))
        return job.prev_task_output + "_1"
        
    async def async_phase3(self, job: MrMeseex):
        return job.prev_task_output + "_2"
        
    async def process_jobs(self):
        job1 = self.job_manager.summon({"test": "Input 1 "}, "job1")
        job2 = self.job_manager.summon({"test": "Input 2 "}, "job2")

        result1 = await job1
        result2 = await job2

        return result1, result2
    
    def stress_test(self):
        jobs = [
            self.job_manager.summon({"test": f"Input {i} "}, f"stress_{i}")
            for i in range(25)
        ]
        # wait for all jobs to complete
        results = gather_results(jobs, results_only=True)
        return results

    def run(self):
        return asyncio.run(self.process_jobs())


def test_advanced():
    processor = TestingMeseexBox()
    
    print("Running advanced test..")

    result1, result2 = processor.run()
    assert result1 == "Input 1 Custom data_1_2"
    assert result2 == "Input 2 Custom data_1_2"

    print("Running stress test..")
    results = processor.stress_test()
    for i, result in enumerate(results):
        assert result == f"Input {i} Custom data_1_2"

    print("Shutting down..")
    processor.job_manager.shutdown(graceful=True)


if __name__ == "__main__":
    test_advanced()
