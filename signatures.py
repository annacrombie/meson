from mesonbuild import interpreter
from mesonbuild.interpreter import kwargs
from mesonbuild.interpreter import interpreterobjects as OBJ
from mesonbuild.interpreter.mesonmain import MesonMain
from mesonbuild.interpreter.interpreter import Interpreter
import mesonbuild
from typing_extensions import TypedDict, Literal, Protocol
import typing

from mesonbuild.interpreterbase.decorators import typed_kwargs_map, typed_pos_args_map, ContainerTypeInfo

import ast
import inspect

untyped_posargs = []
untyped_kwargs = []

def get_type_annotations(func):
    T = typing

    import argparse

    from typing_extensions import Literal

    from mesonbuild.interpreter.kwargs import ExtractRequired, ExtractSearchDirs

    from mesonbuild.compilers.compilers import RunResult

    from mesonbuild.backend.backends import Backend
    from mesonbuild.interpreterbase.baseobjects import InterpreterObject, TYPE_var, TYPE_kwargs, MesonInterpreterObject
    from mesonbuild.interpreterbase import Disabler, TYPE_nvar, TYPE_nkwargs
    from mesonbuild.interpreter import primitives as P_OBJ
    from mesonbuild.interpreter.interpreterobjects import (
        SubprojectHolder,
        Test,
        RunProcess,
        extract_required_kwarg,
        extract_search_dirs,
        NullSubprojectInterpreter,
    )
    from mesonbuild.programs import OverrideProgram, ExternalProgram
    from mesonbuild.mesonlib import File
    from mesonbuild.modules import ExtensionModule, NewExtensionModule, NotFoundExtensionModule
    from mesonbuild import mesonlib, build, mparser, dependencies, coredata, compilers
    from mesonbuild.compilers import Compiler
    from mesonbuild.dependencies import Dependency
    from mesonbuild.build import CustomTarget, CustomTargetIndex, GeneratedList
    from mesonbuild.modules import ModuleState

    mesonbuild.build.GeneratedTypes = T.Union['CustomTarget', 'CustomTargetIndex', 'GeneratedList']

    class EnvironmentSeparatorKW(TypedDict):
        separator: str

    class FuncOverrideDependency(TypedDict):
        native: mesonlib.MachineChoice
        static: T.Optional[bool]

    class AddInstallScriptKW(TypedDict):
        skip_if_destdir: bool
        install_tag: str

    class NativeKW(TypedDict):
        native: mesonlib.MachineChoice

    class AddDevenvKW(TypedDict):
        method: Literal['set', 'prepend', 'append']
        separator: str

    class GetSupportedArgumentKw(TypedDict):
        checked: Literal['warn', 'require', 'off']

    class AlignmentKw(TypedDict):
        from mesonbuild import dependencies
        prefix: str
        args: T.List[str]
        dependencies: T.List[dependencies.Dependency]

    class CompileKW(TypedDict):
        from mesonbuild import dependencies
        name: str
        no_builtin_args: bool
        include_directories: T.List[build.IncludeDirs]
        args: T.List[str]
        dependencies: T.List[dependencies.Dependency]

    class CommonKW(TypedDict):
        from mesonbuild import dependencies
        prefix: str
        no_builtin_args: bool
        include_directories: T.List[build.IncludeDirs]
        args: T.List[str]
        dependencies: T.List[dependencies.Dependency]

    class CompupteIntKW(CommonKW):
        guess: T.Optional[int]
        high: T.Optional[int]
        low: T.Optional[int]

    class HeaderKW(CommonKW, ExtractRequired):
        pass

    class FindLibraryKW(ExtractRequired, ExtractSearchDirs):
        from mesonbuild import dependencies
        disabler: bool
        has_headers: T.List[str]
        static: bool

        # This list must be all of the `HeaderKW` values with `header_`
        # prepended to the key
        header_args: T.List[str]
        header_dependencies: T.List[dependencies.Dependency]
        header_include_directories: T.List[build.IncludeDirs]
        header_no_builtin_args: bool
        header_prefix: str
        header_required: T.Union[bool, coredata.UserFeatureOption]

    return typing.get_type_hints(func, globals(), locals())

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
    mesonbuild.build.CustomTargetIndex: 'custom_idx',
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
    mesonbuild.build.IncludeDirs: 'inc',
    mesonbuild.build.Jar: 'jar',
    mesonbuild.interpreterbase.disabler.Disabler: 'disabler',
    mesonbuild.build.SharedLibrary: 'lib',
    mesonbuild.build.StaticLibrary: 'lib',
    # mesonbuild.build.SharedModule: 'lib',
    mesonbuild.interpreter.primitives.range.RangeHolder: 'range',
    mesonbuild.interpreter.interpreterobjects.RunProcess: 'runresult',
    mesonbuild.build.BothLibraries: 'both_libs',
    mesonbuild.build.Generator: 'generator',
    mesonbuild.build.RunTarget: 'run_tgt',
    mesonbuild.build.AliasTarget: 'alias_tgt',
    mesonbuild.compilers.compilers.RunResult: 'runresult',
    mesonbuild.dependencies.base.ExternalLibrary: 'dep',
    bool: 'bool',
    int: 'int',
    str: 'str',
    list: 'list',
    dict: 'dict',
    object: 'any',
    mesonbuild.interpreterbase.baseobjects.MesonInterpreterObject: 'meson',
    typing.Any: 'any',
    mesonbuild.mesonlib.universal.HoldableObject: 'any',
    type(None): 'void',
    mesonbuild.interpreter.interpreterobjects.SubprojectHolder: 'subproject',
    mesonbuild.build.StructuredSources: 'structed_src',
    mesonbuild.modules.ExtensionModule: 'module',
    mesonbuild.modules.NewExtensionModule: 'module',
    mesonbuild.modules.NotFoundExtensionModule: 'module',
    mesonbuild.programs.OverrideProgram: 'external_program', # technically this could be other things too, like file or exe

    # These objects are the return types for various install_ commands
    mesonbuild.build.Data: 'void',
    mesonbuild.build.Headers: 'void',
    mesonbuild.build.Man: 'void',
    mesonbuild.build.InstallDir: 'void',
    mesonbuild.build.SymlinkData: 'void',
    mesonbuild.interpreter.primitives.string.MesonVersionString: 'str',
}

def _annotated_type_to_doctype(t):
    o = typing.get_origin(t)
    a = typing.get_args(t)

    if o is None:
        o = t

    if o is list:
        a = _annotated_type_to_doctype(a)
        a = [a] if not isinstance(a, list) else a
        return ('list', a)
    if o is dict:
        if not a:
            return ('dict', ['any'])

        assert(len(a) == 2)
        _kt = a[0] # should always be str
        kv = a[1]
        a = _annotated_type_to_doctype(kv)
        a = [a] if not isinstance(a, list) else a
        return ('dict', a)
    elif o is typing.Union:
        # NoneType gets in there for optionals
        union = [_annotated_type_to_doctype(x) for x in a if x is not type(None)]
        return union
    elif type(o) is tuple:
        if len(o):
            return _annotated_type_to_doctype(o[0])
        else:
            return []
    elif o in MESON_OBJECTS_TO_TYPE:
        return MESON_OBJECTS_TO_TYPE[o]
    elif type(o) is typing.ForwardRef:
        return {
                'File': 'file',
        }[o.__forward_arg__]
    elif o is typing.Literal:
        return str(a)
    else:
        return f"unknown: {o}"

def annotated_type_to_doctype(t):
    a = _annotated_type_to_doctype(t)
    return [a] if not isinstance(a, list) else a

def handle_annotated_kwargs(n, f, kwargs):
    if not kwargs:
        return

    if hasattr(kwargs, '__annotations__'):
        annotations = kwargs.__annotations__
    else:
        return None

    types = []
    for k, v in annotations.items():
        types.append((k, annotated_type_to_doctype(v)))

    def key_func(v):
        return v[0]

    types.sort(key=key_func)

    ret = []
    for k, dt in types:
        ret.append((k, dt))
    return ret

def is_optional(t):
    # TODO
    return False

def handle_annotated_posargs(n, f, posargs):
    if not posargs:
        return

    o = typing.get_origin(posargs)
    if o is not tuple:
        a = (posargs,)
    else:
        a = typing.get_args(posargs)

    pos = []
    opt = []
    for v in a:
        if is_optional(v):
            opt.append(annotated_type_to_doctype(v))
        else:
            pos.append(annotated_type_to_doctype(v))

    print(pos)

    return {
        'posargs': pos if pos else None,
        'optargs': opt if opt else None,
    }


def container_type_to_doctype(types_tuple):
    types_tuple = types_tuple if isinstance(types_tuple, tuple) else (types_tuple,)

    def type_name(o):
        if isinstance(o, list) or isinstance(o, tuple):
            return [type_name(x) for x in o]
        elif o in MESON_OBJECTS_TO_TYPE:
            return MESON_OBJECTS_TO_TYPE[o]
        else:
            return f"unknown {o}"

    def container_description(cont):
        container = 'dict' if cont.container is dict else 'list'
        if isinstance(cont.contains, tuple):
            l = [type_name(t) for t in cont.contains]
            contains = l
        else:
            contains = [type_name(cont.contains)]

        return (container, contains)

    candidates = []
    for t in types_tuple:
        if t is type(None):
            continue

        if isinstance(t, ContainerTypeInfo):
            candidates.append(container_description(t))
        else:
            candidates.append(type_name(t))

    return candidates

def handle_typed_posargs(n, f, args):
    ret = {}
    for k, v in args.items():
        if not v:
            ret[k] = None
            continue

        if k == 'posargs':
            # posargs are a splat variable
            assert isinstance(v, tuple)
        else:
            v = [v] if not isinstance(v, list) else v


        ret[k] = [container_type_to_doctype(a) for a in v]
    return ret

def handle_typed_kwargs(n, f, kwargs):
    kwargs_list = []
    for k in kwargs:
        kwargs_list.append((k.name, k))
    kwargs_list.sort(key=lambda x: x[0])

    ret = []
    for (name, k) in kwargs_list:
        t = container_type_to_doctype(k.types)
        ret.append((name, t))

    return ret

def handle_posargs(n, f, annotations, decorators):
    has_posargs = True
    posargs = None
    for d, first_arg in decorators:
        if d == 'noPosargs':
            has_posargs = False
        elif d == 'typed_pos_args':
            posargs = typed_pos_args_map[first_arg]

    if not has_posargs:
        return None

    # if annotations:
    #     annotated_posargs = annotations.get('args')
    #     if annotated_posargs:
    #         return handle_annotated_posargs(n, f, annotated_posargs)

    if posargs:
        return handle_typed_posargs(n, f, posargs)

    untyped_posargs.append(n)
    return None

def handle_kwargs(n, f, annotations, decorators):
    has_kwargs = True
    kwargs = None
    for d, first_arg in decorators:
        if d == 'noKwargs':
            has_kwargs = False
        elif d == 'typed_kwargs':
            kwargs = typed_kwargs_map[first_arg]

    if not has_kwargs:
        return None

    # if annotations:
    #     annotated_kwargs = annotations.get('kwargs') or annotations.get('kwargs_')
    #     if annotated_kwargs :
    #         return handle_annotated_kwargs(n, f, annotated_kwargs)

    if kwargs:
        return handle_typed_kwargs(n, f, kwargs)

    untyped_kwargs.append(n)
    return None

def gather_function_info():
    class Mock(mesonbuild.mesonlib.universal.HoldableObject):
        def __getattr__(self, attr):
            try:
                return super(Mock, self).__getattr__(attr)
            except AttributeError:
                return lambda *x: None

    class Dummy(Interpreter):
        def __init__(self):
            self.funcs = {}
            self.holder_map = {}
            self.bound_holder_map = {}

            self.subproject = None
            self.environment = None

        def __getattr__(self,attr):
            try:
                return super(Dummy, self).__getattr__(attr)
            except AttributeError:
                return None

    dummy_interpreter = Dummy()
    dummy_interpreter.build_func_dict()
    dummy_interpreter.build_holder_map()

    # These functions are defined in the interpreter, but they aren't actually
    # valid, they exist to help nudge users with error messages
    exclude_funcs = [
            'find_library',
            'gettext',
            'option',
    ]

    funcs = [
        (f, dummy_interpreter.funcs[f])
        for f in dummy_interpreter.funcs
        if f not in exclude_funcs
    ]
    funcs.sort(key=lambda x: x[0])

    exclude_objects = [
        # exclude all build_tgt objects
        mesonbuild.build.SharedLibrary,
        mesonbuild.build.StaticLibrary,
        mesonbuild.build.Jar,
        mesonbuild.build.Executable,
        mesonbuild.build.BothLibraries,

        mesonbuild.dependencies.base.ExternalLibrary,
        mesonbuild.interpreter.primitives.string.MesonVersionString,
    ]

    objects = [
        (MESON_OBJECTS_TO_TYPE[t], h)
        for t, h in dummy_interpreter.holder_map.items()
        if t in MESON_OBJECTS_TO_TYPE and t not in exclude_objects
    ]

    objects.append(('meson', MesonMain))
    objects.append(('dep', OBJ.DependencyHolder))
    objects.append(('compiler', mesonbuild.interpreter.compiler.CompilerHolder))
    objects.append(('external_program', OBJ.ExternalProgramHolder))
    objects.append(('build_machine', OBJ.MachineHolder))

    objects = [
        (t, list(holder(Mock(), dummy_interpreter).methods.items()))
        for t, holder in objects
    ]

    build_tgt_methods = OBJ.SharedLibraryHolder(Mock(), dummy_interpreter).methods

    objects.append(('build_tgt', list(build_tgt_methods.items())))
    objects.append(('module', list(mesonbuild.modules.NewExtensionModule().methods.items())))
    objects.append(('subproject', list(OBJ.SubprojectHolder(OBJ.NullSubprojectInterpreter, subdir='asdf').methods.items())))
    objects.append(('both_libs', [
        m
        for m in OBJ.BothLibrariesHolder(Mock(), dummy_interpreter).methods.items()
        if m[0] not in build_tgt_methods
    ]))

    objects.sort(key=lambda x: x[0])

    for t, methods in objects:
        methods.sort(key=lambda x: x[0])

        for n, f in methods:
            n = f"{t}.{n}"
            funcs.append((n, f))

    funcinfo = {}
    for n, f in funcs:
        assert n not in funcinfo

        annotations = get_type_annotations(f)
        decorators = get_decorators(f)

        info = {}
        posargs = handle_posargs(n, f, annotations, decorators)
        if posargs:
            info.update(posargs)

        info['kwargs'] = handle_kwargs(n, f, annotations, decorators)

        ret = annotations.get('return')
        if ret:
            ret = [annotated_type_to_doctype(ret)]
        info['returns'] = ret

        funcinfo[n] = info

    return funcinfo

def clean_up_type(t):
    assert isinstance(t, list)

    def type_sort(v):
        if isinstance(v, tuple):
            return v[0]
        else:
            assert isinstance(v, str)
            return v

    cleaned = []
    for v in t:
        if isinstance(v, tuple):
            v = (v[0], clean_up_type(v[1]))
        elif v in cleaned:
            continue

        cleaned.append(v)
    cleaned.sort(key=type_sort)

    if 'any' in cleaned:
        return ['any']

    return cleaned

def clean_function_info(function_info):
    ret = {}
    for n, info in function_info.items():
        new_info = {}
        for k, v in info.items():
            if not v:
                new_info[k] = []
                continue

            vals = []
            for i in v:
                if isinstance(i, tuple):
                    vals.append((i[0], clean_up_type(i[1])))
                else:
                    vals.append(clean_up_type(i))

            new_info[k] = vals
        ret[n] = new_info

    return ret

def assemble_type(t):
    if type(t) is list:
        return "|".join(assemble_type(x) for x in t)
    elif type(t) is tuple:
        return t[0] + '[' + assemble_type(t[1]) + ']'
    else:
        return t

def main():
    for n, info in clean_function_info(gather_function_info()).items():
        print(n)
        for k, v in info.items():
            if not v:
                continue

            print(f'  {k}:')
            for i in v:
                if isinstance(i, tuple):
                    t = assemble_type(i[1])
                    print(f'    {i[0]}: {t}')
                else:
                    t = assemble_type(i)
                    print(f'    {t}')

    # print('untyped posargs:', untyped_posargs)
    # print('untyped kwargs:', untyped_kwargs)

main()
