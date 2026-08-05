import subprocess
import sys
import os

# Add OSS CAD Suite to PATH if it exists locally
oss_cad_root = r'E:\oss-cad-suite'
if os.path.isdir(oss_cad_root):
    os.environ['PATH'] = os.path.join(oss_cad_root, 'bin') + os.pathsep + os.path.join(oss_cad_root, 'lib') + os.pathsep + os.environ['PATH']

def check_command(cmd, name):
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"[PASS] {name} found.")
        return True
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
    deps_ok &= check_command(['verilator_bin', '--version'], 'Verilator')
    deps_ok &= check_command(['yosys', '-V'], 'Yosys')
    deps_ok &= check_python_module('pyverilog')
    
    print("-" * 40)
    if deps_ok:
        print("All dependencies are satisfied!")
    else:
        print("Some dependencies are missing. Please install them.")
        sys.exit(1)

if __name__ == '__main__':
    main()
