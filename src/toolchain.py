"""
Centralized Toolchain Utility
Locates yosys, verilator, iverilog, and vvp, and executes subprocesses directly (cross-platform).
"""

import os
import shutil
import subprocess
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()


def get_toolchain_path():
    """Get the OSS CAD Suite path if defined in environment or fallback."""
    # Look for OSS_CAD_SUITE_PATH in environment variables
    oss_path = os.environ.get("OSS_CAD_SUITE_PATH")
    if not oss_path:
        # Fallback to the hardcoded E:\oss-cad-suite path on Windows if it exists
        if os.path.exists(r"E:\oss-cad-suite"):
            oss_path = r"E:\oss-cad-suite"
    return oss_path


def get_tool_path(tool_name):
    """
    Resolve the absolute path of a tool.
    Checks PATH first, then falls back to OSS CAD Suite bin folder.
    """
    # 1. Search PATH first
    resolved = shutil.which(tool_name)
    if resolved:
        return resolved

    # On Windows, add .exe check just in case
    if os.name == 'nt' and not tool_name.endswith('.exe'):
        resolved = shutil.which(tool_name + '.exe')
        if resolved:
            return resolved

    # 2. Check in OSS_CAD_SUITE_PATH
    oss_path = get_toolchain_path()
    if oss_path:
        bin_dir = os.path.join(oss_path, "bin")
        tool_in_bin = os.path.join(bin_dir, tool_name)
        resolved = shutil.which(tool_in_bin)
        if resolved:
            return resolved

        if os.name == 'nt' and not tool_name.endswith('.exe'):
            resolved = shutil.which(tool_in_bin + '.exe')
            if resolved:
                return resolved

    # Return the name directly and let subprocess fail with FileNotFoundError if not found
    return tool_name


def setup_toolchain_env():
    """Setup appropriate environment variables for the toolchain."""
    env = os.environ.copy()
    oss_path = get_toolchain_path()

    if oss_path:
        bin_dir = os.path.join(oss_path, "bin")
        lib_dir = os.path.join(oss_path, "lib")
        # Prepend to PATH so spawned child tools are resolved
        env["PATH"] = bin_dir + os.pathsep + lib_dir + os.pathsep + env.get("PATH", "")
        # Set VERILATOR_ROOT
        verilator_root = os.path.join(oss_path, "share", "verilator")
        if os.path.isdir(verilator_root):
            env["VERILATOR_ROOT"] = verilator_root

    return env


def run_tool(tool_name, args, **kwargs):
    """
    Run a tool with direct subprocess call.
    Automatically resolves the tool path and sets up the environment.
    """
    tool_path = get_tool_path(tool_name)
    env = setup_toolchain_env()

    # If the user passed custom env, merge it
    if "env" in kwargs:
        user_env = kwargs.pop("env")
        env.update(user_env)

    cmd = [tool_path] + args

    # Run subprocess directly without shell=True to avoid cmd.exe/bash issues
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        **kwargs
    )
