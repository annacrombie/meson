from mesonbuild import interpreter
from mesonbuild.interpreter import kwargs
import mesonbuild
from typing_extensions import TypedDict, Literal, Protocol
import typing

from mesonbuild.interpreterbase.decorators import typed_kwargs_map, typed_pos_args_map, ContainerTypeInfo

import ast
import inspect

untyped_posargs = []
untyped_kwargs = []

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

    source = inspect.getsource(target).split('\n')

    indent = 0
    for c in source[0]:
        if c == ' ':
            indent += 1
        else:
            break

    unindented = [line[indent:] for line in source]
    source = '\n'.join(unindented)

    node_iter.visit(ast.parse(source))
    return decorators

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
    kwargs._FoundProto: 'dep', # really, this means anything that responds to .found() I think.
    mesonbuild.dependencies.base.Dependency: 'dep',
    mesonbuild.build.IncludeDirs: 'include_dirs',
    mesonbuild.build.Jar: 'jar',
    mesonbuild.interpreterbase.disabler.Disabler: 'disabler',
    bool: 'bool',
    int: 'int',
    str: 'str',
    list: 'list',
    dict: 'dict',
    object: 'any',
}

def handle_annotated_kwargs(n, t, f, kwargs):
    def type_to_doctype(t, n=0):
        pre = ' '*(n*2)
        o = typing.get_origin(t)
        a = typing.get_args(t)

        if o is None:
            o = t

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

    if hasattr(kwargs, '__annotations__'):
        annotations = kwargs.__annotations__
    else:
        return None

    types = []
    for k, v in annotations.items():
        types.append((k, type_to_doctype(v)))

    def key_func(v):
        return v[0]

    types.sort(key=key_func)

    ret = []
    for k, dt in types:
        ret.append((k, dt))
    return ret

def container_type_to_doctype(types_tuple):
    types_tuple = types_tuple if isinstance(types_tuple, tuple) else (types_tuple,)

    def type_name(o):
        if isinstance(o, list) or isinstance(o, tuple):
            return "|".join([type_name(x) for x in o])
        elif o in MESON_OBJECTS_TO_TYPE:
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

def handle_typed_posargs(n, t, f, args):
    for k, v in args.items():
        if not v:
            continue

        print('  ' + k + ':')
        if k == 'posargs':
            assert isinstance(v, tuple)
            # posargs are a splat variable
        else:
            v = [v] if not isinstance(v, list) else v

        for a in v:
            print('    ' + container_type_to_doctype(a))

def handle_typed_kwargs(n, t, f, kwargs):
    kwargs_list = []
    for k in kwargs:
        kwargs_list.append((k.name, k))
    kwargs_list.sort(key=lambda x: x[0])

    ret = []
    for (name, k) in kwargs_list:
        t = container_type_to_doctype(k.types)
        ret.append((name, t))

    return ret

def handle_posargs(n, t, f, decorators):
    has_posargs = True
    posargs = None
    for d, first_arg in decorators:
        if d == 'noPosargs':
            has_posargs = False
        elif d == 'typed_pos_args':
            posargs = typed_pos_args_map[first_arg]

    if not has_posargs:
        return

    if posargs:
        handle_typed_posargs(n, t, f, posargs)
        return

    untyped_posargs.append(n)

def handle_kwargs(n, t, f, decorators):
    has_kwargs = True
    kwargs = None
    for d, first_arg in decorators:
        if d == 'noKwargs':
            has_kwargs = False
        elif d == 'typed_kwargs':
            kwargs = typed_kwargs_map[first_arg]

    if not has_kwargs:
        return None

    if kwargs:
        return handle_typed_kwargs(n, t, f, kwargs)

    kwargs = t.get('kwargs')
    if kwargs:
        return handle_annotated_kwargs(n, t, f, kwargs)

    untyped_kwargs.append(n)
    return None

def main():
    types = interpreter.interpreter.get_types()
    types.sort(key=lambda x: x[0])
    for n, t, f in types:
        print(n)

        decorators = get_decorators(f)
        handle_posargs(n, t, f, decorators)
        kwargs = handle_kwargs(n, t, f, decorators)
        if kwargs:
            print('  kwargs:')
            for k, t in kwargs:
                print(f'    {k}: {t}')

    # print('untyped posargs:', untyped_posargs)
    # print('untyped kwargs:', untyped_kwargs)

main()
