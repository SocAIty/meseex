from typing import List, Any, Optional, Dict, Union
import asyncio
from meseex import MrMeseex


async def gather_results_async(meekz: List[MrMeseex], timeout_s: Optional[float] = None, default_value: Any = None, raise_on_error: bool = False) -> Dict[str, Any]:
    """
    Asynchronously gather results from a list of Mr. Meseex instances.
    
    Args:
        meekz: List of Mr. Meseex instances to gather results from
        timeout_s: Optional timeout in seconds
        default_value: Value to return if the job has an error or times out.
        raise_on_error: If True, raise an exception if a job has an error or times out. Else fills remaining jobs with default_value.

    Returns:
        Dictionary mapping meseex_id to results
    """
    try:
        if timeout_s is not None:
            return await asyncio.wait_for(asyncio.gather(*(meseex for meseex in meekz)), timeout=timeout_s)
        else:
            return await asyncio.gather(*(meseex for meseex in meekz))
    except Exception as e:
        return {meseex.meseex_id: e for meseex in meekz}


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


