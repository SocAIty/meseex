from meseex.control_flow import polling_task, PollAgain, PollingException
from meseex import MrMeseex, MeseexBox
from asyncio import sleep


class FakeExternalService:
    def __init__(self):
        self.number_of_polls = 0
        self.data = {}

    async def get_data(self) -> str:
        self.number_of_polls += 1
        await sleep(1)
        if self.number_of_polls > 3:
            return "completed"
        else:
            return (self.number_of_polls - 1) * 0.33
        

fakeService = FakeExternalService()


@polling_task(timeout_seconds=10, poll_interval_seconds=0.1)
async def poll_task(meex: MrMeseex):
    data = await fakeService.get_data()
    if data == "completed":
        return data
    else:
        meex.set_task_progress(data, "API Working")
        return PollAgain()


async def reset_polls():
    fakeService.number_of_polls = 0


@polling_task(timeout_seconds=4, poll_interval_seconds=2)
async def failure_poll_task():
    data = await fakeService.get_data()
    if data == "completed":
        return data
    else:
        return PollAgain()


def test_polling():
    meseex_box = MeseexBox({
        "test_polling": poll_task,
        "reset_polls": reset_polls,
        "test_polling_with_error": failure_poll_task,
    })
    meex = meseex_box.summon({"test": "test"}, "test_meseex")
    meex.wait_for_result()

    assert meex.task_outputs[0] == "completed"
    assert isinstance(meex.error, PollingException)


if __name__ == "__main__":
    test_polling()
