from __future__ import annotations

import runpy
from pathlib import Path


def resolve_prompt_path(prompts_dir: Path, prompt: str) -> Path:
    """把相对 prompts 目录或绝对路径解析为存在的 prompt 文件。"""
    candidate = Path(prompt)
    if candidate.is_file():
        return candidate.resolve()
    resolved = (prompts_dir / prompt).resolve()
    if resolved.is_file():
        return resolved
    raise FileNotFoundError(f"Prompt file not found: {prompt}")


def load_prompt_module(path: Path) -> dict:
    """加载 Python prompt 模块，返回其中定义的变量。"""
    return runpy.run_path(str(path))
