"""
This module provides functionality for loading and parsing .msg files.

It contains two main functions:
- load_message_file: This function loads a .msg file and returns a Message object.
- msg_to_string: This function converts a .msg file to a plain text string.
"""

from typing import Union, Optional
import extract_msg
import os


def load_message_file(path: str) -> Optional[extract_msg.Message]:
    """Load a .msg file and return a Message object"""
    if not isinstance(path, str):
        raise ValueError("Path must be a string")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} does not exist")

    try:
        return extract_msg.Message(path)
    except extract_msg.utils.InvalidFileException:
        raise ValueError(f"{path} is not a valid .msg file")


def msg_to_string(path: str) -> str:
    """Convert a .msg file to a plain text string

    Args:
        path: Path to .msg file

    Returns:
        Plain text contents of .msg file

    Raises:
        ValueError if path is not a string
        FileNotFoundError if path does not exist
        ValueError if path is not a valid .msg file
    """
    msg: Optional[extract_msg.Message] = load_message_file(path)
    if not msg:
        raise FileNotFoundError(f"Could not load {path}")

    lines: list[str] = []
    lines.append(msg.sender)
    lines.append(str(msg.date))
    lines.append(msg.subject)
    lines.append(msg.body)

    return "\n".join(lines)


if __name__ == "__main__":
    print(msg_to_string("data/memo.msg"))
    print(msg_to_string("data/memo2.msg"))