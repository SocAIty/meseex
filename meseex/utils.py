import inspect
from typing import Callable
from meseex.mr_meseex import MrMeseex


def _expects_mr_meseex_param(method: Callable) -> bool:
    """Checks if the method expects a MrMeseex parameter in its arguments."""
    for param in inspect.signature(method).parameters.values():
        if (param.annotation == MrMeseex
                or param.name == "mr_meseex"
                or (isinstance(param.annotation, type) and issubclass(param.annotation, MrMeseex))):
            return True
    return False
