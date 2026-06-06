import os
import platform
import subprocess
from pathlib import Path

from ..register import register_tool


@register_tool(
    name="run_bash",
    description="执行bash命令并返回输出结果",
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的bash命令",
            },
            "timeout": {
                "type": "integer",
                "description": "命令超时时间(秒), 默认120",
            },
        },
        "required": ["command"],
    },
)
def run_bash(command: str, timeout: int = 120) -> str:
    # shell=True allows complex commands but trusts model-generated input.
    # In a multi-tenant or internet-facing deployment this would need sandboxing.
    try:
        # Ensure subprocesses output UTF-8 (especially Python on Windows,
        # which defaults to the system ANSI code page for piped stdout).
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"

        # On Windows, cmd.exe defaults to the system ANSI code page (e.g., gbk).
        # Switch to UTF-8 (code page 65001) so builtins like dir/type output UTF-8.
        if platform.system() == "Windows":
            command = f"chcp 65001 >nul && {command}"

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return output or "[无输出]"
    except subprocess.TimeoutExpired:
        return f"命令超时 ({timeout}s): {command}"
    except Exception as e:
        return f"命令执行失败: {e}"


@register_tool(
    name="read_file",
    description="读取文件内容, 支持指定起止行和行数范围",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件路径(绝对路径)",
            },
            "offset": {
                "type": "integer",
                "description": "起始行号(从1开始), 默认1",
            },
            "limit": {
                "type": "integer",
                "description": "读取行数, 默认全部",
            },
        },
        "required": ["file_path"],
    },
)
def read_file(file_path: str, offset: int = 1, limit: int = -1) -> str:
    path = Path(file_path)
    if not path.exists():
        return f"文件不存在: {file_path}"
    if not path.is_file():
        return f"路径不是文件: {file_path}"

    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except UnicodeDecodeError:
        try:
            lines = path.read_text(encoding="gbk").split("\n")
        except Exception as e:
            return f"读取文件失败 (编码错误): {e}"
    except Exception as e:
        return f"读取文件失败: {e}"

    total = len(lines)
    start = max(0, offset - 1)
    end = min(total, start + limit) if limit > 0 else total
    selected = lines[start:end]

    result = []
    for i, line in enumerate(selected, start=offset):
        result.append(f"{i}\t{line}")
    return "\n".join(result)


@register_tool(
    name="glob",
    description="按glob模式搜索文件, 返回匹配的文件路径列表",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "glob匹配模式, 如 **/*.py",
            },
            "path": {
                "type": "string",
                "description": "搜索起始目录, 默认当前工作目录",
            },
        },
        "required": ["pattern"],
    },
)
def glob(pattern: str, path: str = ".") -> str:
    base = Path(path)
    if not base.exists():
        return f"目录不存在: {path}"

    matches = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return f"未找到匹配 '{pattern}' 的文件"

    return "\n".join(str(m) for m in matches)
