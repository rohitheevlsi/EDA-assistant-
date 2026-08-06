import sys
import os
from src.toolchain import run_tool, setup_toolchain_env

# Apply toolchain environment
os.environ.update(setup_toolchain_env())

def check_command(tool_name, args, name):
    try:
        result = run_tool(tool_name, args)
        if result.returncode == 0 or result.stderr or result.stdout:
            print(f"[PASS] {name} found.")
            return True
        else:
            print(f"[FAIL] {name} check failed.")
            return False
    except FileNotFoundError:
        print(f"[FAIL] {name} not found in PATH.")
        return False
    except Exception as e:
        print(f"[WARN] {name} found but returned an error: {e}")
        return False

def check_python_module(module_name):
    try:
        __import__(module_name)
        print(f"[PASS] Python module '{module_name}' found.")
        return True
    except ImportError:
        print(f"[FAIL] Python module '{module_name}' not found.")
        return False

def main():
    print("Checking EDA Assistant Dependencies...")
    print("-" * 40)
    
    deps_ok = True
    deps_ok &= check_command('verilator_bin', ['--version'], 'Verilator')
    deps_ok &= check_command('yosys', ['-V'], 'Yosys')
    deps_ok &= check_command('iverilog', ['-V'], 'Icarus Verilog')
    deps_ok &= check_command('vvp', ['-V'], 'VVP Simulator')
    deps_ok &= check_python_module('pyverilog')
    
    print("-" * 40)
    if deps_ok:
        print("All dependencies are satisfied!")
    else:
        print("Some dependencies are missing. Please install them.")
        sys.exit(1)

if __name__ == '__main__':
    main()
