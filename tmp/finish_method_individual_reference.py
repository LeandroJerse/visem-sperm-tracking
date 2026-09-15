"""Complete only the local LaTeX portion after an exact-text anchor mismatch."""
import ast
from pathlib import Path

source=Path('tmp/document_individual_reference_results.py').read_text(encoding='utf-8')
tree=ast.parse(source)
# The earlier script completed every public edit. Execute only its helper and
# final LaTeX statements, avoiding any repeated append to the public records.
scope={'ROOT':Path.cwd(),'Path':Path}
helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='replace')
tail=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Expr)
          and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name)
          and n.value.func.id=='replace' and n.value.args
          and isinstance(n.value.args[0],ast.Constant)
          and n.value.args[0].value=='monografia/cap_metodo/metodo.tex')
code=ast.Module(body=[helper,*tree.body[tail:]],type_ignores=[])
exec(compile(ast.fix_missing_locations(code),'local_method_completion','exec'),scope)
