from types import CodeType
from typing import Any

def py_start_callback(code: CodeType, instruction_offset: int, /) -> None: ...
def py_end_callback(
    code: CodeType, instruction_offset: int, ret_or_exception: Any, /
) -> None: ...
