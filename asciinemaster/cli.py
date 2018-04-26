# -*- coding: utf-8 -*-

"""Console script for asciinemaster."""

import sys
import textwrap
import argparse
from os.path import basename, splitext

from asciinemaster import __version__, asciinemaster
from asciinemaster.asciinemaster import Caster


def run_exec_command(args):
    caster = Caster()
    caster.record_screencast(
        args.input,
        args.output or splitext(args.input)[0] + '.cast',
        with_ansi=args.with_ansi,
        typing_mode=args.typing,
    )


def run_test_command(args):
    raise NotImplementedError


def run_selftest_command(args):
    self_test()


def main():
    """Console script for asciinemaster."""
    desc = 'Execute a bash-like script and record it as an Asciinema.org screencast.'
    parser = argparse.ArgumentParser(
        description=desc,
        epilog=textwrap.dedent("""\
            example usage:
              Execute script and save to local cast:
                \x1b[1masciinemaster exec demo.sh\x1b[0m
              Execute script and save to local cast with explicit name:
                \x1b[1masciinemaster exec --output demo1.cast demo.sh\x1b[0m
              Test script by re-executing and comparing new with old cast:
                \x1b[1masciinemaster test --previous-output demo_prev.cast demo.sh\x1b[0m
              Run a simple self-test:
                \x1b[1masciinemaster selftest\x1b[0m

            For help on a specific command run:
              \x1b[1masciinemaster <command> -h\x1b[0m"""),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-v', '--version',
        action='version',
        version='asciinemaster {}'.format(__version__))

    subparsers = parser.add_subparsers(dest='subparser_name')

    # create the parser for the "exec" command
    parser_exec = subparsers.add_parser('exec',
        help='Execute a shell-like script and record its execution as an Asciinema screencast.')
    parser_exec.add_argument('--with-ansi',
        action='store_true',
        help='Keep ANSI escape sequences (experimental, expect issues with pipes and redirections).')
    parser_exec.add_argument('--typing',
        choices=['instant', 'human'],
        default='human',
        help='Mode for typing input commands (default: "human").')
    parser_exec.add_argument('--output',
        metavar='PATH',
        help='Path of output file (default: input file basename plus extension ".cast").')
    parser_exec.add_argument('input',
        metavar='PATH',
        help='Path of input shell script.')
    parser_exec.set_defaults(func=run_exec_command)

    # create the parser for the "test" command
    parser_test = subparsers.add_parser('test',
        help='Test a previously recorded Asciinema screencast (not yet implemented).')
    parser_test.set_defaults(func=run_test_command)

    # create the parser for the "selftest" command
    parser_selftest = subparsers.add_parser('selftest',
        help='Run self-test and nothing else.')
    parser_selftest.set_defaults(func=run_selftest_command)

    # parse the args and call whatever function was selected
    args = parser.parse_args()
    if hasattr(args, 'func'):
        code = args.func(args)
        sys.exit(code)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
