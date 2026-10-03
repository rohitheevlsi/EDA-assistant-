import os
import re
from src.toolchain import setup_toolchain_env
os.environ.update(setup_toolchain_env())

from pyverilog.vparser.parser import parse

def parse_verilog(file_path):
    """Safely parse Verilog file into AST. Returns None on parse failure."""
    try:
        ast, _ = parse([file_path])
        return ast
    except Exception as e:
        print(f"[Warning] Pyverilog parse exception: {e}")
def strip_verilog_comments(code_text):
    """Strip single-line and multi-line comments from Verilog source code."""
    code_no_block = re.sub(r'/\*.*?\*/', '', code_text, flags=re.DOTALL)
    return re.sub(r'//.*', '', code_no_block)

def summarize_ast_regex(code_text):
    """Fallback regex extractor for Verilog / SystemVerilog when Pyverilog AST parsing fails."""
    clean_code = strip_verilog_comments(code_text)
    # Find module name
    mod_match = re.search(r'\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)', clean_code)
    mod_name = mod_match.group(1) if mod_match else "unknown_module"

    ports = []
    port_details = []

    # Port regex matching: (input|output|inout) [wire|reg|logic] [msb:lsb] name
    port_pattern = re.compile(
        r'\b(input|output|inout)\s+(?:wire|reg|logic)?\s*(?:signed)?\s*(\[[^\]]+\])?\s*([A-Za-z_][A-Za-z0-9_]*)',
        re.IGNORECASE
    )
    for m in port_pattern.finditer(clean_code):
        direction, width_str, name = m.group(1).lower(), m.group(2) or "", m.group(3)
        ports.append(name)
        port_details.append({
            'name': name,
            'direction': direction,
            'width_str': width_str.strip()
        })

    # Signals (wire/reg/logic declarations)
    sig_pattern = re.compile(r'\b(reg|wire|logic)\s*(?:\[[^\]]+\])?\s*([A-Za-z_][A-Za-z0-9_]*)', re.IGNORECASE)
    signals = list(set(m.group(2) for m in sig_pattern.finditer(code_text)))

    # Always blocks count
    always_blocks = len(re.findall(r'\balways\b|\balways_comb\b|\balways_ff\b', code_text, re.IGNORECASE))

    return {
        'modules': [{
            'name': mod_name,
            'ports': ports,
            'port_details': port_details,
            'signals': signals,
            'always_blocks': always_blocks
        }]
    }

def summarize_ast(ast, file_path=None):
    """Summarize AST into structured IR. Falls back to regex if AST is None or empty."""
    if ast is None or not hasattr(ast, 'description') or not ast.description:
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, encoding='utf-8', errors='replace') as f:
                    return summarize_ast_regex(f.read())
            except Exception:
                pass
        return {'modules': []}

    summary = {
        'modules': []
    }
    try:
        for desc in ast.description.definitions:
            if type(desc).__name__ == 'ModuleDef':
                mod_info = {
                    'name': desc.name,
                    'ports': [],
                    'port_details': [],
                    'signals': [],
                    'always_blocks': 0
                }
                
                # Extract Ports
                if desc.portlist:
                    for port in desc.portlist.ports:
                        if type(port).__name__ == 'Ioport':
                            mod_info['ports'].append(port.first.name)
                        elif type(port).__name__ == 'Port':
                            mod_info['ports'].append(port.name)
                
                # Find all Inputs, Outputs, Inouts inside the module AST to get direction/width details
                from pyverilog.ast_code_generator.codegen import ASTCodeGenerator
                codegen = ASTCodeGenerator()
                
                def find_port_decls(node):
                    decls = []
                    if type(node).__name__ in ('Input', 'Output', 'Inout'):
                        decls.append(node)
                    if hasattr(node, 'children'):
                        for child in node.children():
                            decls.extend(find_port_decls(child))
                    return decls
                
                port_decls = find_port_decls(desc)
                for decl in port_decls:
                    dir_name = type(decl).__name__.lower()
                    width_str = ""
                    if decl.width:
                        width_str = codegen.visit(decl.width).strip()
                    mod_info['port_details'].append({
                        'name': decl.name,
                        'direction': dir_name,
                        'width_str': width_str
                    })
                
                # Extract Signals (Wire, Reg) and Always blocks
                for item in desc.items:
                    item_type = type(item).__name__
                    if item_type == 'Decl':
                        for decl in item.list:
                            decl_type = type(decl).__name__
                            if decl_type in ('Wire', 'Reg'):
                                mod_info['signals'].append(decl.name)
                    elif item_type == 'Always':
                        mod_info['always_blocks'] += 1
                
                summary['modules'].append(mod_info)
    except Exception as e:
        print(f"[Warning] AST summarization error: {e}")

    if not summary['modules'] and file_path and os.path.exists(file_path):
        try:
            with open(file_path, encoding='utf-8', errors='replace') as f:
                return summarize_ast_regex(f.read())
        except Exception:
            pass

    return summary

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python parser_ir.py <verilog_file>")
        return
    
    file_path = sys.argv[1]
    ast = parse_verilog(file_path)
    summary = summarize_ast(ast, file_path=file_path)
    
    print(f"Summary for {os.path.basename(file_path)}:")
    for mod in summary['modules']:
        print(f"  Module: {mod['name']}")
        print(f"    Ports: {', '.join(mod['ports'])}")
        print(f"    Signals: {', '.join(mod['signals'])}")
        print(f"    Always Blocks: {mod['always_blocks']}")

if __name__ == '__main__':
    main()

