import re
from pathlib import Path

from .generatorbase import GeneratorBase
from .model import (
    ReferenceManual,
    Function,
    Object,
    PosArg,
    VarArgs,
    Kwarg,
    ObjectType,
)

import typing as T

class GeneratorTypes(GeneratorBase):
    def __init__(
        self, manual: ReferenceManual, out: Path, enable_modules: bool
    ) -> None:
        super().__init__(manual)
        self.out = out
        self.enable_modules = enable_modules

    def _parse_type(self, t, in_container=False):
        parsed = []
        name = ""
        i = 0
        while i < len(t):
            c = t[i]
            if c == '[':
                (n, sub) = self._parse_type(t[i+1:], in_container=True)
                parsed.append((name, sub,))
                name = ""
                i += n
                continue
            elif c == ']':
                if name:
                    parsed.append(name)
                return (i+1, parsed)
            elif c == ' ':
                i += 1
                continue
            elif c == '|':
                parsed.append(name)
                name = ""
            else:
                name += c

            i += 1

        if name:
            parsed.append(name)
        return (i, parsed)

    def parse_type(self, t):
        (_, parsed) = self._parse_type(t)
        return parsed

    def assemble_type(self, t):
        if type(t) is list:
            def sort_func(v):
                assert type(v) is not list

                if type(v) is tuple:
                    return v[0]
                else:
                    return v

            t.sort(key=sort_func)
            return "|".join(self.assemble_type(x) for x in t)
        elif type(t) is tuple:
            return t[0] + '[' + self.assemble_type(t[1]) + ']'
        else:
            return t

    def print_types(self, args):
        args = [args] if not isinstance(args, list) else args

        for arg in args:
            t = self.assemble_type(self.parse_type(arg.type.raw))
            print(f"    {t}")


    def function_name(self, f: Function, o: Object = None) -> str:
        name = ""
        if o is not None:
            name += f"{o.name}."

        name += f.name
        return name

    def generate_function(self, f: Function, obj: Object = None):
        print(self.function_name(f, obj))

        if f.posargs:
            print('  posargs:')
            self.print_types(f.posargs)

        if f.varargs:
            print('  varargs:')
            self.print_types(f.varargs)

        if f.optargs:
            print('  optargs:')
            self.print_types(f.optargs)

        kwargs = self.sorted_and_filtered(list(f.kwargs.values()))
        if kwargs:
            print('  kwargs:')
        for kwarg in kwargs:
            k = kwarg.name
            t = self.assemble_type(self.parse_type(kwarg.type.raw))
            print(f"    {k}: {t}")

        print('  returns:')
        print('    ' + self.assemble_type(self.parse_type(f.returns.raw)))

    def generate(self):
        for f in self.sorted_and_filtered(self.functions):
            self.generate_function(f, None)

        for obj in self.sorted_and_filtered(self.objects):
            for f in self.sorted_and_filtered(obj.methods):
                if not self.enable_modules and (obj.obj_type == ObjectType.MODULE or obj.defined_by_module is not None):
                    continue

                self.generate_function(f, obj)
