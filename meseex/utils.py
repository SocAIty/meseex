from typing import List, Any, Optional, Dict, Union
import asyncio
from meseex import MrMeseex


async def gather_results_async(
    meekz: List[MrMeseex],
    timeout_s: Optional[float] = None,
    default_value: Any = None,
    raise_on_error: bool = False,
    results_only: bool = False
) -> Union[Dict[str, Any], List[Any]]:
    """
    Asynchronously gather results from a list of Mr. Meseex instances.
    
    Args:
        meekz: List of Mr. Meseex instances to gather results from
        timeout_s: Optional timeout in seconds
        default_value: Value to return if the job has an error or times out.
        raise_on_error: If True, raise an exception if a job has an error or times out. Else fills remaining jobs with default_value.
        results_only: If True the results are returned as a list of results. Else the results are returned as a dictionary mapping meseex_id to results.

    Returns:
        Dictionary mapping meseex_id to results or list of results if results_only is True
    """
    results = {}
    
    async def get_result(meseex):
        try:
            result = await meseex
            if meseex.name not in results:
                results[meseex.name] = result
            else:
                results[meseex.meseex_id] = result
        except Exception as e:
            if raise_on_error:
                raise e
            print("Meseex failed: ", meseex.name, "with error: ", e)
            if meseex.name not in results:
                results[meseex.name] = default_value
            else:
                results[meseex.meseex_id] = default_value
    
    try:
        if timeout_s is not None:
            await asyncio.wait_for(asyncio.gather(*(get_result(meseex) for meseex in meekz)), timeout=timeout_s)
        else:
            await asyncio.gather(*(get_result(meseex) for meseex in meekz))
    except asyncio.TimeoutError:
        if raise_on_error:
            raise
        # For timed out tasks, set default value for any missing results
        for meseex in meekz:
            if meseex.name not in results and meseex.meseex_id not in results.values():
                if meseex.name not in results:
                    results[meseex.name] = default_value
                else:
                    results[meseex.meseex_id] = default_value
    
    if results_only:
        return list(results.values())
    return results


def gather_results(
    meekz: List[MrMeseex],
    timeout_s: Optional[float] = None,
    default_value: Any = None,
    raise_on_error: bool = False,
    results_only: bool = False
) -> Union[Dict[str, Any], List[Any]]:
    """
    Synchronously gather results from a list of Mr. Meseex instances.
    
    Args:
        meekz: List of Mr. Meseex instances to gather results from
        timeout_s: Optional timeout in seconds
        default_value: Value to return if the job has an error or times out
        raise_on_error: If True, raise an exception if a job has an error or times out. Else fills remaining jobs with default_value.
        results_only: If True the results are returned as a list of results. Else the results are returned as a dictionary mapping meseex_id to results.
    Returns:
        Dictionary mapping meseex_id to results
    """
    results = {}
    for meseex in meekz:
        try:
            if meseex.name not in results:
                results[meseex.name] = meseex.wait_for_result(timeout_s=timeout_s)
            else:
                results[meseex.meseex_id] = meseex.wait_for_result(timeout_s=timeout_s)
        except Exception as e:
            if raise_on_error:
                raise e
            print("Meseex failed: ", meseex.name, "with error: ", e)
            if meseex.name not in results:
                results[meseex.name] = default_value
            else:
                results[meseex.meseex_id] = default_value
    if results_only:
        return list(results.values())
    return results
