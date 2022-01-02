import re
from pathlib import Path

from .generatorbase import GeneratorBase
from .model import (
    ReferenceManual,
    Function,
    Object,
    Type,
    PosArg,
    VarArgs,
    Kwarg,
)

import typing as T


class ManTable:
    def __init__(self, cols: T.List[str]):
        self.cols = cols
        self.text = ""
        self.rows = 0

    def row(self, cols: T.List[str]):
        self.rows += 1

        joined = "\nT}\tT{\n".join(cols)

        self.text += f"T{{\n{joined}\nT}}\n"

    def render(self) -> str:
        colspec = " ".join(self.cols)
        tablespec = "\n".join([colspec for _ in range(self.rows)])

        return f".TS\nallbox;{tablespec}.\n{self.text}.TE\n.sp 1\n"


class ManPage:
    def __init__(self, path: Path):
        self.path = path
        self.text = ""

    def reset_font(self):
        self.text += ".P\n"

    def title(self, name: str, section: int):
        import datetime

        date = datetime.date.today()
        self.reset_font()
        self.text += f'.TH "{name}" "{section}" "{date}"\n'

    def section(self, name: str):
        self.reset_font()
        self.text += f".SH {name}\n"

    def subsection(self, name: str):
        self.reset_font()
        self.text += f".SS {name}\n"

    def par(self, text: str):
        self.reset_font()
        self.text += f"{text}\n"

    def indent(self):
        self.text += ".RS 4\n"

    def unindent(self):
        self.text += ".RE\n"

    def br(self):
        self.text += ".br\n"

    def nl(self):
        self.text += "\n"

    def line(self, text: str):
        if text and text[0] in [".", "'"]:
            self.text += "\\"
        self.text += f"{text}\n"

    def inline(self, text: str):
        self.text += f"{text}"

    def table(self, table: ManTable):
        self.reset_font()
        self.text += table.render()

    def write(self):
        self.path.write_text(self.text)

    @staticmethod
    def bold(text: str):
        return f"\\fB{text}\\fR"

    @staticmethod
    def italic(text: str):
        return f"\\fI{text}\\fR"


class GeneratorMan(GeneratorBase):
    def __init__(
        self, manual: ReferenceManual, out: Path, enable_modules: bool
    ) -> None:
        super().__init__(manual)
        self.out = out
        self.enable_modules = enable_modules
        self.links: T.List[str] = []

    def _extract_meson_version(self) -> str:
        # Hack around python relative imports to get to the Meson version
        import sys

        sys.path.append(Path(__file__).resolve().parents[2].as_posix())
        from mesonbuild.coredata import version

        return version

    def generate_description(self, page: ManPage, desc: str):
        def italicise(match: T.Match[str]):
            return ManPage.italic(match.group(1))

        desc = re.sub(re.compile(r"\[\[(.*?)\]\]"), italicise, desc)

        def linkify(match: T.Match[str]):
            replacement = ManPage.italic(match.group(1))

            if match.group(2)[0] != "#":
                if match.group(2) in self.links:
                    num = self.links.index(match.group(2))
                else:
                    self.links.append(match.group(2))
                    num = len(self.links)

                replacement += f"[{len(self.links)}]"

            return replacement

        desc = re.sub(re.compile(r"\[(.*?)\]\((.*?)\)"), linkify, desc)

        def bold(match: T.Match[str]):
            return ManPage.bold(match.group(1))

        desc = re.sub(re.compile(r"\*(.*?)\*"), bold, desc)

        isCode = False
        for chunk in desc.split("```"):
            if isCode:
                page.indent()
                lines = chunk.strip().split("\n")
                if lines[0] == "meson":
                    lines = lines[1:]

                for line in lines:
                    page.line(line)
                    page.br()
                page.unindent()
            else:
                inList = False
                for line in chunk.split("\n"):
                    if len(line) == 0:
                        page.nl()
                    elif line[0:2] in ["- ", "* "]:
                        if inList:
                            page.nl()
                            page.br()
                        else:
                            inList = True

                        page.inline(line.strip() + " ")
                    elif inList and line[0] == " ":
                        page.inline(line.strip())
                    else:
                        inList = False
                        page.line(line)

                if inList:
                    page.nl()

            isCode = not isCode

    def generate_varargs_signature(self, args):
        ret = []
        for arg in args:
            if isinstance(arg, VarArgs):
                ret += [arg.name + "..."]
            else:
                ret += [arg.name]
        return ret

    def generate_function_signature(self, f: Function, o: Object = None) -> str:
        sig = ""
        sep = ""
        if f.posargs:
            sig += ", ".join(self.generate_varargs_signature(f.posargs))
            sep = ", "

        if f.varargs:
            sig += sep
            sig += f.varargs.name + "..."
            sep = ", "

        opt = ""
        if f.optargs:
            opt = "[" + sep
            opt += ", ".join(self.generate_varargs_signature(f.optargs))
            opt += "]"
            sep = ", "

        kwargs = self.sorted_and_filtered(list(f.kwargs.values()))
        kw = ""
        if kwargs:
            kw += sep
            kw += ", ".join([f"{arg.name}:" for arg in kwargs])

        ret = "" if f.returns.raw == "void" else f" -> {f.returns.raw}"

        name = ""
        if o is not None:
            name += f"{o.name}."

        name += f.name

        return f"{name}({sig}{opt}{kw}){ret}"

    def base_info(self, x):
        info = []
        if x.deprecated:
            info += [ManPage.bold("deprecated")]
        if x.since:
            info += [f"since {x.since}"]

        return info

    def generate_function_arg(
        self,
        page: ManPage,
        arg: T.Union[PosArg, VarArgs, Kwarg],
        isOptarg: bool = False,
    ):
        required = (
            arg.required
            if isinstance(arg, Kwarg)
            else not isOptarg and not isinstance(arg, VarArgs)
        )

        page.br()
        page.line(ManPage.bold(arg.name))

        info = [ManPage.italic(arg.type.raw)]

        if required:
            info += [ManPage.bold("required")]
        if isinstance(arg, (PosArg, Kwarg)) and arg.default:
            info += [f"default: {arg.default}"]
        if isinstance(arg, VarArgs):
            mn = 0 if arg.min_varargs < 0 else arg.min_varargs
            mx = "infinity" if arg.max_varargs < 0 else arg.max_varargs
            info += [f"{mn}...{mx} times"]

        info += self.base_info(arg)

        page.line(", ".join(info))

        page.br()
        self.generate_description(page, arg.description.strip())
        page.nl()

    def generate_function_argument_section(
        self, page: ManPage, name: str, args, isOptarg: bool = False
    ):
        if not args:
            return

        page.line(ManPage.bold(name))
        page.indent()
        for arg in args:
            self.generate_function_arg(page, arg, isOptarg)
        page.unindent()

    def generate_function_section(self, page: ManPage, name: str, text: T.List[str]):
        page.line(ManPage.bold(name))
        page.indent()
        for line in text:
            self.generate_description(page, line)
        page.unindent()
        page.nl()

    def generate_function(self, page: ManPage, f: Function, obj: Object = None) -> None:
        page.subsection(self.generate_function_signature(f, obj))

        info = self.base_info(f)
        if info:
            page.line(", ".join(info))
            page.nl()

        self.generate_description(page, f.description.strip())
        page.nl()

        self.generate_function_argument_section(page, "POSARGS", f.posargs)
        if f.varargs:
            self.generate_function_argument_section(page, "VARARGS", [f.varargs])
        self.generate_function_argument_section(page, "OPTARGS", f.optargs, True)
        self.generate_function_argument_section(
            page, "KWARGS", self.sorted_and_filtered(list(f.kwargs.values()))
        )

        if f.notes:
            self.generate_function_section(page, "NOTES", f.notes)
        if f.warnings:
            self.generate_function_section(page, "WARNINGS", f.warnings)
        if f.example:
            self.generate_function_section(page, "EXAMPLE", [f.example])

    def generate_object(self, page: ManPage, obj: Object) -> None:
        info = [obj.name]

        info += self.base_info(obj)

        page.subsection(", ".join(info))

        if obj.extends:
            page.line(ManPage.bold("extends: ") + obj.extends)
            page.br()

        ret = [x.name for x in self.sorted_and_filtered(obj.returned_by)]
        if ret:
            page.line(ManPage.bold("returned_by: ") + ", ".join(ret))
            page.br()

        ext = [x.name for x in self.sorted_and_filtered(obj.extended_by)]
        if ext:
            page.line(ManPage.bold("extended_by: ") + ", ".join(ext))
            page.br()

        page.nl()

        self.generate_description(page, obj.description.strip())

        if obj.notes:
            page.nl()
            self.generate_function_section(page, "NOTES", obj.notes)
        if obj.warnings:
            page.nl()
            self.generate_function_section(page, "WARNINGS", obj.warnings)
        if obj.example:
            page.nl()
            self.generate_function_section(page, "EXAMPLE", [obj.example])

    def generate(self) -> None:
        page = ManPage(self.out / "meson-reference.3")

        page.title("meson-reference", 3)

        page.section("NAME")
        page.par(
            f"meson-reference v{self._extract_meson_version()}"
            + " - a reference for meson functions and objects"
        )

        page.section("DESCRIPTION")
        self.generate_description(
            page,
            """This manual is divided into two sections, *FUNCTIONS* and *OBJECTS*.  *FUNCTIONS* contains a reference for all meson functions and methods.  Methods are denoted by [[object_name]].[[method_name]]().  *OBJECTS* contains additional information about each object.""",
        )

        page.section("FUNCTIONS")
        for f in self.sorted_and_filtered(self.functions):
            self.generate_function(page, f)

        for obj in self.sorted_and_filtered(self.objects):
            for f in self.sorted_and_filtered(obj.methods):
                self.generate_function(page, f, obj)

        page.section("OBJECTS")
        for obj in self.sorted_and_filtered(self.objects):
            self.generate_object(page, obj)

        page.section("SEE ALSO")
        for i in range(len(self.links)):
            link = self.links[i]
            page.line(f"[{i + 1}] {link}")
            page.br()

        page.write()
