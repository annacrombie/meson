from mesonbuild import interpreter
import mesonbuild
from typing_extensions import TypedDict, Literal, Protocol
import typing

from mesonbuild.interpreterbase.decorators import typed_kwargs_map, ContainerTypeInfo

import ast
import inspect

# def get_decorators(tgt):
#     decorators = []

#     for line in inspect.getsource(tgt).split('\n'):
#         line = line.strip()
#         if line[0] == '@':
#             decorators.append(line)
#         elif line.startswith('def'):
#             break

#     return decorators

def get_decorators(target):
    decorators = []
    def visit_FunctionDef(node):
        first_arg = "unknown"
        for n in node.decorator_list:
            name = ''
            if isinstance(n, ast.Call):
                first_arg = n.args[0]
                if isinstance(first_arg, ast.Constant):
                    first_arg = first_arg.value

                name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
            else:
                name = n.attr if isinstance(n, ast.Attribute) else n.id

            decorators.append((name, first_arg))

    node_iter = ast.NodeVisitor()
    node_iter.visit_FunctionDef = visit_FunctionDef
    source = inspect.getsource(target)

    unindented = []
    indent = 999999999999999
    for line in source.split('\n'):
        if not line:
            continue

        i = 0
        for c in line:
            if c != ' ':
                break
            i += 1

        if i < indent:
            indent = i

        if line.startswith((' ' * indent) + 'def'):
            break

    for line in source.split('\n'):
        unindented.append(line[indent:])

    source = '\n'.join(unindented)

    node_iter.visit(ast.parse(source))
    return decorators

types = interpreter.interpreter.get_types()

MESON_OBJECTS_TO_TYPE = {
    mesonbuild.mesonlib.universal.File: 'file',
    mesonbuild.build.BuildTarget: 'build_tgt',
    mesonbuild.build.Target: 'tgt',
    mesonbuild.build.Executable: 'exe',
    mesonbuild.build.CustomTarget: 'custom_tgt',
    mesonbuild.build.CustomTargetIndex: 'custom_tgt_idx',
    mesonbuild.programs.ExternalProgram: 'external_program',
    mesonbuild.build.ExtractedObjects: 'extracted_obj',
    mesonbuild.build.GeneratedList: 'generated_list',
    mesonbuild.build.EnvironmentVariables: 'env',
    mesonbuild.build.MachineChoice: 'bool',
    mesonbuild.coredata.UserFeatureOption: 'feature',
    mesonbuild.mesonlib.universal.FileMode: 'list[int|str]',
    mesonbuild.build.ConfigurationData: 'cfg_data',
    mesonbuild.compilers.compilers.Compiler: 'compiler',
    mesonbuild.interpreter.kwargs._FoundProto: 'dep', # really, this means anything that responds to .found() I think.
    mesonbuild.build.IncludeDirs: 'include_dirs',
    bool: 'bool',
    int: 'int',
    str: 'str',
    list: 'list',
    dict: 'dict',
}



no_kwargs = []
q_kwargs = []
untyped_kwargs = []

def handle_annotated_kwargs(n, t, f, kwargs):
    def type_to_doctype(t, n=0):
        pre = ' '*(n*2)
        o = typing.get_origin(t)
        a = typing.get_args(t)

        if o is None:
            o = t

        # print(pre+'t='+str(t))
        # print(pre+'o='+str(o))

        s = ""
        if o is list:
            assert a is not None
            return f"list[{type_to_doctype(a, n+1)}]"
        if o is dict:
            assert(len(a) == 2)
            _kt = a[0] # should always be str
            kv = a[1]
            return f"dict[{type_to_doctype(kv)}]"
        elif o is typing.Union:
            assert a is not None
            # NoneType gets in there for optionals
            union = [type_to_doctype(x, n+1) for x in a if x is not type(None)]
            union.sort()
            return "|".join(union)
        elif type(o) is tuple:
            return type_to_doctype(o[0], n+1)
        elif o in MESON_OBJECTS_TO_TYPE:
            return MESON_OBJECTS_TO_TYPE[o]
        elif type(o) is typing.ForwardRef:
            return {
                    'File': 'file',
            }[o.__forward_arg__]
        elif o is typing.Literal:
            return str(a)
        else:
            return "unknown: <" + str(o) + ">"

    if not kwargs:
        return

    annotations = kwargs
    if hasattr(kwargs, '__annotations__'):
        annotations = kwargs.__annotations__

    types = []
    for k, v in annotations.items():
        types.append((k, type_to_doctype(v)))

    def key_func(v):
        return v[0]

    types.sort(key=key_func)

    for k, dt in types:
        print(f"  {k}: {dt}")

def handle_typed_kwargs(n, t, f, kwargs):
    def type_to_doctype(t):
        def type_name(o):
            if o in MESON_OBJECTS_TO_TYPE:
                return MESON_OBJECTS_TO_TYPE[o]
            else:
                return f"unknown <{o}>"

        def container_description(cont):
            """Human readable description of this container type.

            :return: string to be printed
            """
            container = 'dict' if cont.container is dict else 'list'
            if isinstance(cont.contains, tuple):
                l = [type_name(t) for t in cont.contains]
                l.sort()
                contains = '|'.join(l)
            else:
                contains = type_name(cont.contains)

            s = f'{container}[{contains}]'
            # if cont.pairs:
            #     s += ' that has even size'
            # if not cont.allow_empty:
            #     s += ' that cannot be empty'
            return s

        candidates = []
        for t in types_tuple:
            if t is type(None):
                continue

            if isinstance(t, ContainerTypeInfo):
                candidates.append(container_description(t))
            else:
                candidates.append(type_name(t))
        candidates.sort()
        return "|".join(candidates)

    kwargs_list = []
    for k in kwargs:
        kwargs_list.append((k.name, k))
    kwargs_list.sort(key=lambda x: x[0])

    for (name, k) in kwargs_list:
        t = k.types
        types_tuple = t if isinstance(t, tuple) else (t,)
        t = type_to_doctype(types_tuple)
        print(f"  {name}: {t}")

types.sort(key=lambda x: x[0])

for n, t, f in types:
    # if f != 'vcs_tag':
    #     continue

    decorators = get_decorators(f)

    print(n)

    has_kwargs = True
    kwargs = None
    for d, first_arg in decorators:
        if d == 'noKwargs':
            has_kwargs = False
        elif d == 'typed_kwargs':
            kwargs = typed_kwargs_map[first_arg]

    if not has_kwargs:
        no_kwargs.append(n)
        continue

    if kwargs:
        handle_typed_kwargs(n, t, f, kwargs)
    else:
        handle_annotated_kwargs(n, t, f, t.get('kwargs'))

    if not kwargs:
        q_kwargs.append(n)
        continue

print('no kwargs:', no_kwargs)
print('q kwargs:', q_kwargs)
print('untyped kwargs:', untyped_kwargs)
