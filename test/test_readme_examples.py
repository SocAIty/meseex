import asyncio
import time
import random
from meseex import MeseexBox, MrMeseex, gather_results_async


# Basic Usage Example
def basic_usage_example():
    print("\n=== Basic Usage Example ===")
    
    # Define your task functions
    async def prepare(meex: MrMeseex) -> str:
        return f"I'm {meex.name}! Look at me cooking {meex.input['meal']}!"

    def cook(meex: MrMeseex) -> str:
        return f"{meex.prev_task_output}. Wubba lubba dub dub! Finished. Puff."

    # Create a MeseexBox with task methods
    meseex_box = MeseexBox({"prepare": prepare, "cook": cook})

    # Summon a Mr. Meseex to do your tasks
    meex = meseex_box.summon({"meal": "Salisbury steak"}, "Mr. MeCoox")

    # Wait for completion
    result = meex.wait_for_result()
    print(f"Sync Result: {result}")

    # Shutdown the box
    meseex_box.shutdown()


# Parallel Task Execution Example
async def parallel_execution_example():
    print("\n=== Parallel Task Execution Example ===")
    
    async def process_meal(meex: MrMeseex) -> str:
        meal = meex.input["meal"]
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Simulate work
        return f"Processed {meal}"
    
    # Create a MeseexBox
    meseex_box = MeseexBox({"process": process_meal})

    # Summon multiple Mr. Meseexes
    meCookz = [meseex_box.summon({"meal": f"steak_{i}"}) for i in range(25)]
    # Gather all results
    await gather_results_async(meCookz)
    # Shutdown the box
    meseex_box.shutdown()


# Advanced Example
async def advanced_example():
    print("\n=== Advanced Example ===")
    
    # Define task functions (sync and async)
    async def prepare_meal(meex: MrMeseex):
        # Access initial input
        meal = meex.input["meal"]
        meex.set_task_progress(0.5, f"Prepping {meal}...")
        await asyncio.sleep(random.uniform(0.1, 0.3))  # Reduced sleep time for testing
        return f"Prepared {meal}"

    async def cook_meal(meex: MrMeseex):
        # Access previous task's output
        preparation = meex.prev_task_output
        meex.set_task_progress(0.2, "Heating the pan...")
        time.sleep(random.uniform(0.1, 0.3))  # Reduced sleep time for testing
        meex.set_task_progress(0.7, "Searing nicely...")
        time.sleep(random.uniform(0.1, 0.3))  # Reduced sleep time for testing
        return f"{preparation}. Cooked perfectly!"

    # Use MeseexBox as an async context manager
    async with MeseexBox({"Prepare": prepare_meal, "Cook": cook_meal}) as meseex_box:
        # Summon multiple Meseexes for parallel cooking
        print("Summoning Meseex chefs...")
        meCookz = [
            meseex_box.summon({"meal": f"Steak {i+1}"}, f"Chef_{i+1}")
            for i in range(5)  # Let's cook 5 steaks in parallel
        ]
        # Gather results asynchronously
        results = await gather_results_async(meCookz, raise_on_error=True)
        print("\n--- Cooking Complete! ---")
        for name, result in results.items():
            print(f"{name}: {result}")


# Error Handling Example
async def error_handling_example():
    print("\n=== Error Handling Example ===")
    
    # Task that will raise an error
    async def i_will_fail(meex: MrMeseex):
        raise ValueError("Purpose fulfilled... by failing!")

    async with MeseexBox({"fail": i_will_fail}) as box1:
        meseex1 = box1.summon(name="Mr. Fail")
        await asyncio.sleep(0.5)  # Give it time to fail
        if meseex1.error:
            print(f"{meseex1.name} Error message: {meseex1.error.message}")
    
    # Debug: raise errors immediately
    print("\nTesting immediate error raising (this will show an error stack trace):")
    try:
        mb = MeseexBox({"fail": i_will_fail}, raise_on_meseex_error=True)
        meseex2 = mb.summon(name="Mr. Fail")
        await asyncio.sleep(0.5)  # Give it time to fail
    except Exception as e:
        print(f"Caught expected error: {e}")
    finally:
        if 'mb' in locals():
            await mb.shutdown()


# Run all examples
async def run_async_examples():
    await parallel_execution_example()
    await advanced_example()
    # await error_handling_example()
    print("\nAll examples completed!")

# Entry point
if __name__ == "__main__":
    basic_usage_example()
    asyncio.run(run_async_examples())
