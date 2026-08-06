from src.toolchain import setup_toolchain_env
import os
os.environ.update(setup_toolchain_env())

from pyverilog.vparser.parser import parse

def parse_verilog(file_path):
    # parse takes a list of files
    ast, directives = parse([file_path])
    return ast

def summarize_ast(ast):
    summary = {
        'modules': []
    }
    # AST root is usually Source -> Description -> ModuleDef
    if ast.description:
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
                    dir_name = type(decl).__name__.lower() # input, output, or inout
                    # width is a Width node, or None
                    width_str = ""
                    if decl.width:
                        # Visit the width node to get '[msb:lsb]' string
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
    return summary

def main():
    if len(sys.argv) < 2:
        print("Usage: python parser_ir.py <verilog_file>")
        return
    
    file_path = sys.argv[1]
    ast = parse_verilog(file_path)
    summary = summarize_ast(ast)
    
    print(f"Summary for {os.path.basename(file_path)}:")
    for mod in summary['modules']:
        print(f"  Module: {mod['name']}")
        print(f"    Ports: {', '.join(mod['ports'])}")
        print(f"    Signals: {', '.join(mod['signals'])}")
        print(f"    Always Blocks: {mod['always_blocks']}")

if __name__ == '__main__':
    main()
