# -*- coding: utf-8 -*-
from . import blocks
from . import emitter
from . import I8CError
from . import lexer
from . import loggers
from . import names
from . import optimizer
from . import parser
from . import serializer
from . import stack
from . import types
import copy
import os
import pkg_resources
import cStringIO as stringio
import subprocess
import sys

def version():
    try:
        return pkg_resources.get_distribution("i8c").version
    except: # pragma: no cover
        # This block is excluded from coverage because while
        # we could test it (by hiding the egg-info somehow?)
        # it seems like a lot of effort for very little gain.
        return "UNKNOWN"

VERSIONMSG = u"""\
GNU i8c %s
Copyright (C) 2015 Free Software Foundation, Inc.
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.""" % version()

HELPMSG = u"""\
Usage: i8c [OPTION]... [FILE]...

GNU Infinity note compiler.

Options:
  --help     Display this information
  --version  Display version information
  -E         Preprocess only; do not compile, assemble or link
  -S         Compile only; do not assemble or link
  -c         Compile and assemble, but do not link
  -fpreprocessed
             Do not preprocess.
  -o FILE    Place the output into FILE

Note that i8c uses GCC both to preprocess its input (unless invoked
with ‘-fpreprocessed’) and to assemble its output (unless invoked with
‘-E’ or ‘-S’).  If GCC is used, all options not explicitly listed
above will be passed to GCC unmodified.

In general i8c operates like GCC, so if you are used to GCC then i8c
should make sense.  Try it!

In most cases the command you want is ‘i8c -c file.i8’, which reads
and compiles ‘file.i8’ and writes the result to ‘file.o’.

Report bugs to gbenson@redhat.com.
i8c home page: <https://github.com/gbenson/i8c/>"""

class CommandLine(object):
    def __init__(self, args):
        self.showinfo = None
        self.with_cpp = True
        self.with_i8c = True
        self.with_asm = True
        self.infiles = []
        self.outfile = None
        self.cpp_args = []
        self.asm_args = []
        self.__process_args(args)

    def __process_args(self, args):
        args = copy.copy(list(args))
        while args:
            arg = args.pop(0)

            # --help     Display usage information
            # --version  Display version information
            #
            # Both these options cause us to print information and
            # exit immediately, without continuing to process the
            # command line or compiling anything.
            if arg == "--help":
                self.showinfo = HELPMSG
                return

            elif arg == "--version":
                self.showinfo = VERSIONMSG
                return

            # -E  Preprocess only; do not compile, assemble or link
            # -S  Compile only; do not assemble or link
            # -c  Compile and assemble, but do not link
            # -fpreprocessed
            #     Indicate to the preprocessor that the input file
            #     has already been preprocessed.
            #
            # These options control what processes we run.  GCC
            # doesn't seem to care if you specify more than one of
            # these so we don't either.
            elif arg == "-E":
                self.with_i8c = False
                self.with_asm = False

            elif arg == "-S":
                self.with_asm = False

            elif arg == "-c":
                self.asm_args.append(arg)

            elif arg == "-fpreprocessed":
                self.with_cpp = False

            # -o <file>  Place the output into <file>
            #
            # GCC doesn't complain about multiple "-o" options,
            # it just uses the last one it saw, so we do too.
            elif arg == "-o":
                if not args:
                    raise I8CError(u"missing filename after ‘-o’")

                self.asm_args.append(arg)
                self.outfile = args.pop(0)
                self.asm_args.append(self.outfile)

            elif arg.startswith("-o"):
                self.asm_args.append(arg)
                self.outfile = arg[2:]

            # Input filenames.  Not so easy to distinguish.
            elif (arg.endswith(".i8")
                  or arg.endswith(".i8p")) and not arg.startswith("-"):
                if self.asm_args and self.asm_args[-1] == "-include":
                    self.asm_args.pop()

                self.infiles.append(arg)
                self.cpp_args.append(arg)

            # -x <language>  Specify the language of input files
            #
            # Don't allow users to specify this, we need to use
            # it ourselves.
            elif arg.startswith("-x"):
                raise I8CError(u"unrecognized option ‘%s’" % arg)

            # --debug[=faculty1[,faculty2]...]
            #
            # Turn on debugging for some or all of i8c.
            elif arg.startswith("--debug"):
                if arg == "--debug":
                    for logger in loggers.values():
                        logger.enable()
                else:
                    for faculty in arg[8:].split(","):
                        logger = loggers.get(faculty, None)
                        if logger is not None:
                            logger.enable()

            # All other options get passed through to both the
            # preprocessor and the assembler, if they are used.
            else:
                self.cpp_args.append(arg)
                self.asm_args.append(arg)

def setup_input(args):
    process = infile = None
    if args.with_cpp:
        command = ["gcc", "-E", "-x", "c"] + args.cpp_args
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        infile = process.stdout
    elif args.infiles in ([], ["-"]):
        infile = sys.stdin
    else:
        infile = stringio.StringIO()
        for filename in args.infiles:
            infile.write(open(filename).read())
        infile.seek(0)
    return process, infile

def guess_outfile(args):
    assert args.outfile is None
    assert "-c" in args.asm_args
    if len(args.infiles) != 1:
        raise I8CError("unable to determine output filename")
    root, ext = os.path.splitext(args.infiles[0])
    return root + ".o"

def setup_output(args):
    process = outfile = None
    if args.with_asm:
        command = ["gcc", "-x", "assembler-with-cpp"] + args.asm_args + ["-"]
        if args.outfile is None and "-c" in args.asm_args:
            command.extend(("-o", guess_outfile(args)))
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        outfile = process.stdin
    elif args.outfile in (None, "-"):
        outfile = sys.stdout
    else:
        outfile = open(args.outfile, "w")
    return process, outfile

def compile(readline, write):
    tree = parser.build_tree(lexer.generate_tokens(readline))
    tree.accept(types.TypeAnnotator())
    tree.accept(names.NameAnnotator())
    tree.accept(blocks.BlockCreator())
    tree.accept(stack.StackWalker())
    tree.accept(optimizer.BlockOptimizer())
    tree.accept(serializer.Serializer())
    tree.accept(optimizer.StreamOptimizer())
    tree.accept(emitter.Emitter(write))
    return tree

def main(args):
    args = CommandLine(args)
    if args.showinfo is not None:
        print args.showinfo.encode("utf-8")
        return

    if not (args.with_cpp or args.with_i8c or args.with_asm):
        raise I8CError("nothing to do!")

    outfile = stringio.StringIO()
    process, infile = setup_input(args)
    try:
        if args.with_i8c:
            compile(infile.readline, outfile.write)
        else:
            outfile.write(infile.read())

    finally:
        if process is not None:
            infile.close()
            process.wait()
            if process.returncode != 0:
                return process.returncode
    outfile.seek(0)
    infile = outfile

    process, outfile = setup_output(args)
    try:
        outfile.write(infile.read())
    finally:
        if process is not None:
            outfile.close()
            process.wait()
            if process.returncode != 0:
                return process.returncode