# Meseex

> "I'm Mr. Meseex! Look at me! I run your tasks in parallel until completion!"

---

## 🧿 What is Meseex?

**Meseex** is a task orchestration framework for Python that helps you manage parallel workflows with elegance and style. 

Mr. Meseex exists to fulfill tasks and then vanishes from existence.

## 🚀 Features

- **Task Orchestration**: Run complex sequences of tasks with elegant transitions.
- **Async & Sync Support**: Seamlessly mix asynchronous and synchronous methods. 
- **Schwifty Progress Tracking**: Real-time visual progress with a rich terminal UI.
- **Thread-safe Operations**: No interdimensional cable-level tangles in your threads.
- **Robust Error Handling**: Capture errors with precision without creating a Cronenberg situation.
- **Lightweight**: Blazingly fast. Tiny codebase. Minimal dependencies.


## 🛠️ Installation

```bash
pip install meseex
```

## 🧪 Quick Start Guide

### Basic Usage

```python
from meseex import MrMeseex, MeseexBox

# Define your task functions
async def prepare(meex: MrMeseex) -> MrMeseex:
    return f"I'm {meex.name}! Look at me cooking {meex.input["meal"]}!"

def cook(meex: MrMeseex) -> MrMeseex:  #
    return f"{meex.prev_task_output}. Wubba lubba dub dub! Finished. Puff."

# Create a MeseexBox with task methods. 
meseex_box = MeseexBox({"prepare": prepare,"process": process})
# Summon a Mr. Meseex to do your tasks
meex = meseex_box.summon({"meal": "Salisbury bteak"}, "Mr. MeCoox")

# Wait for completion
result = await meex  # Mr. Meseex ceases to exist after completing the task
result = meex.wait_for_result() # or if you prefer to use it in sync context

```

### Parallel Task Execution

```python
from meseex import MeseexBox, gather_results
# Create a MeseexBox
meseex_box = MeseexBox(task_methods)
# Summon multiple Mr. Meseexes
meCookz = [meseex_box.summon({"meal": f"steak_{i}"}) for i in range(25)]
# Gather all results. Note you can also use - gather_results_async to fully leverage asyncio.
results = gather_results(meCookz)
```

Checkout the test files for more complete examples.


## 🧠 The Philosophy of Mr. Meseex

Like their Rick and Morty inspiration, Mr. Meseexes:

- **Exist to serve a purpose**: Each Meseex is created to perform it's specified tasks in it's defined order.
- **Want to complete their task quickly**: They're optimized for efficiency. Async methods are run in async context, other methods spawn a Thread in an ThreadPool.
- **Cease to exist after task completion**: Clean resource management.
- **Can work together**: Parallel and collaborative task execution.

But unlike the show version, our Meseexes are perfectly happy existing for complex, long-running tasks!

## 👁️ Vision

We believe Meseex is an essential building block for further development in agentic AI. The project provides infrastructure for:

- Building autonomous agent workflows.
- Supporting parallel execution with LLMs and genAI services.
- Giving the Meekz (Mr. Meseexes) truly agentic behavior.
- Running in Model Context Protocol (MCP)

Think of it as a portal gun for your tasks - opening doorways to efficient parallel processing dimensions.

## 🏢 Why is [Socaity.ai](https://www.socaity.ai) Creating This?

At [Socaity.ai](https://www.socaity.ai), we're using Meseex in our projects:

- **[SocaitySDK](https://github.com/SocAIty/socaity)** Use any AI model with a single line of code.
- **[FastTaskAPI](https://github.com/SocAIty/FastTaskAPI)**: Building APIs for genAI efficiently.
- **[fastSDK](https://github.com/SocaIty/fastsdk)**: Easily consuming APIs with minimal code.

We are working on an Agent and Agentic Workflow framework that leverags the Meseex architecutre.

## 📊 Advanced Examples

This example demonstrates:
- Setting task progress with messages (`set_task_progress`).
- Accessing initial `input` and `prev_task_output`.
- Summoning multiple Meseexes (`summon`) for parallel execution.
- Gathering results (`gather_results`).
- Automatic Progress Bar: When you run this code `asyncio.run(...)`, Meseex displays a dynamic progress bar in your terminal using `rich`.

```python
import asyncio
import time
import random
from meseex import MeseexBox, MrMeseex, gather_results_async

# Define task functions (sync and async)
async def prepare_meal(meex: MrMeseex):
    meal = meex.input["meal"]  # Access initial input
    meex.set_task_progress(0.5, f"Prepping {meal}...")
    await asyncio.sleep(random.uniform(0.5, 1.5))
    return f"Prepared {meal}"

async def cook_meal(meex: MrMeseex):
    preparation = meex.prev_task_output  # Access previous task's output
    meex.set_task_progress(0.2, "Heating the pan...")
    time.sleep(random.uniform(0.5, 1.5))
    meex.set_task_progress(0.7, "Searing nicely...")
    time.sleep(random.uniform(0.5, 1.5))
    return f"{preparation}. Cooked perfectly!"

# Use MeseexBox as an async context manager. -> No need to call shutdown.
async with MeseexBox({"Prepare": prepare_meal, "Cook": cook_meal}) as meseex_box:
    # Summon multiple Meseexes for parallel cooking
    # The Rich progress bar will automatically display in the terminal
    print("Summoning Meseex chefs...")
    meCookz = [
        meseex_box.summon({"meal": f"Steak {i+1}"}, f"Chef_{i+1}")
        for i in range(5) # Let's cook 5 steaks in parallel
    ]
    # Gather results asynchronously
    results = await gather_results_async(meCookz, raise_on_error=True)
    print("\n--- Cooking Complete! ---")
    for name, result in results.items():
        print(f"{name}: {result}")
```

## 🔧 API Reference

### MrMeseex

The individual "Job/task executor" that fulfills its purpose.
It behaves similar to a state machine for performing the different tasks.

The example shows how you can use it to:
- Getting statistics and metadata for a meseex box.
- Working with task_data.
- Accessing errors.

```python
# meex = MrMeseex(["task1", "task2" ...])
meex.set_task_data("Whatever data you like")  # This set's the data to an object stored for the given task.
meex.get_task_data("task1")
meex.progress # gives you the overall progress of Mr. Meseex not only of a specific task.
meex.task # gives you the name of the current task
meex.total_duration_ms # duration of all tasks in milliseconds.
meex.task_meta # Gives you statistic object; with execution time (duration_ms), progress, entered_at, left_at properties.
```

### MeseexBox

## 🔄 Error Handling

Meseex provides robust error handling out of the box:

```python
from meseex import MeseexBox, MrMeseex, TaskError
import asyncio

# Task that will raise an error
async def i_will_fail(meseex: MrMeseex):
    raise ValueError("Purpose fulfilled... by failing!")

async def main():
    async with MeseexBox({"fail": i_will_fail}) as box1:
        meseex1 = box1.summon(name="Mr. Fail")
        await meseex1 # Give it time to fail
        print(f"{meseex1.name} Error message: {meseex1.error.message}")
```
Debug: Raise errors immediately - if you want to throw an error and stop execution with it.
```python
mb = MeseexBox({"fail": i_will_fail}, raise_on_meseex_error=True)
mb.summon(name="Mr. Fail")  # Will print an error stack trace to the console.
```

## 💼 Contributing

Wanna get schwifty with the code? Contributions are welcome!

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/inter-dimensional-cable`)
3. Commit your changes (`git commit -m 'Add interdimensional feature'`)
4. Push to the branch (`git push origin feature/inter-dimensional-cable`)
5. Open a Pull Request

## 📜 License
You can use the project freely without limitations.

GPLv3 - See LICENSE file for details.

---

<p align="center">Developed with 🧿 by <a href="https://www.socaity.ai">Socaity.ai</a></p>
<p align="center">Remember: Existence is pain to a Meseex, but task completion brings them joy!</p>