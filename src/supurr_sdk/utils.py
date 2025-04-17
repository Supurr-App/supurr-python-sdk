from typing import get_args, Any

def is_valid_literal(value: Any, literal_type: Any) -> bool:
    args = get_args(literal_type)
    if not args:
        raise TypeError("Provided type is not a Literal[...]")
    return value in args

