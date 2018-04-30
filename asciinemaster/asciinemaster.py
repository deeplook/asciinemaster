# -*- coding: utf-8 -*-

"""
Main module.

Execute/test a shell-like script and record as an Asciinema.org screencast.

Current limitations:

- multi-line commands will not show changes in the prompt (e.g. '> ')
- commands in input scripts must be separated by one or more empty lines
- each command is executed in its own shell, so
- setting/reusing state (as shell variables) is not possible
- ANSI escape codes are not properly supported, yet

Done:

- use int(datetime.datetime.timestamp(datetime.datetime.now())) for timestamp value in header
  (reverse: datetime.datetime.fromtimestamp(1521147263.254088))
- subtract timestamp value given in header from all output lines
- read and use terminal's current width/height inside header of generated casts

Todo:

- reduce precision for output times to six digits after the comma, like Asciinema does
- write unittests
- test CaptureOutput with subprocess.getoutput() vs subprocess.check_output()
- simulate tab completion when typing file paths
- simulate occasional typos and their fixes
- write code to strip-off human typing effect in recorded Asciinema casts
- refactor as a plugin for asciinema (asciinema.commands.exec/test)
"""

import re
import os
import sys
import time
import json
import random
import datetime
import argparse
import subprocess
import textwrap
import shutil
from os.path import expanduser, expandvars

# https://capturer.readthedocs.io/en/latest/
from capturer import CaptureOutput


def self_test():
    # single words remain untouched
    content = 'foobar'
    assert split_into_lines(content) == [content]

    print('SUCCESS')
    sys.exit(0)

    # continuation lines get split and indented
    content = open('tests/test_continuation.sh').read()
    print(content)
    print(split_into_lines(content))
    assert split_into_lines(content) == ['ls ', '    -l']


def block_iter(text):
    """
    Generate blocks of non-empty lines found in input test.

        list(block_iter('foo\nbar'))
        -> [['foo', 'bar']]

        list(block_iter('foo\n\nbar'))
        -> [['foo'], ['bar']]
    """

    lines = text.splitlines()
    block = []
    while lines:
        if lines[0]:
            block.append(lines[0])
        else:
            yield block
            block = []
        del lines[0]
    if block:
        yield block


class Typist(object):
    """
    A class to output text character by charater.
    """
    def __init__(self, **kwargs):
        for (k, v) in kwargs.items():
            setattr(self, k, v)
        # self.ts

    def type(self, line):
        """
        Generate all charaters of a string one by one.
        """
        for c in line:
            yield c

    def timed_type(self, line, delay_func=0, accumulate=False, sleep=False):
        """
        Generate (delay, char) pairs of all characters of a string.
        """
        if accumulate:
            assert hasattr(self, 'ts')
        if delay_func == 0:
            yield self.ts if accumulate else delay_func, line
        else:
            for c in self.type(line):
                df = delay_func
                delay = df if type(df) in (float, int) else df()
                if sleep:
                    time.sleep(delay)
                if accumulate:
                    self.ts += delay
                    yield self.ts, c
                else:
                    yield delay, c


class AsciinemaTypist(Typist):
    """
    A typist simulating a Human being typing text into a keyboard.
    """
    def timed_type(self, line, delay_func=0, accumulate=True, sleep=False, first_line=True):
        """
        Asciinema 'print function' writing a JSON string for one output.
        """
        # print shell prompt as prefix before printing the line itself
        if line[0] != '#':
            if first_line:
                ac_line = [self.ts, 'o', '$ ']
                output = '{}\n'.format(json.dumps(ac_line))
                yield self.ts, output

        for d, c in super().timed_type(line, delay_func=delay_func,
                                       accumulate=accumulate, sleep=sleep):
            ac_line = [d, 'o', '{}'.format(c)]
            # ac_line = [float_to_limited_str(d), 'o', '{}'.format(c)]
            output = '{}\n'.format(json.dumps(ac_line))
            yield d, output


# https://stackoverflow.com/questions/32145824/python-forcing-precision-on-a-floating-point-number-in-json
def float_to_limited_str(x, prec=6):
    """
    Convert number to float string with limited precision.
    """
    fmt_str = '{:.%df}' % prec
    return fmt_str.format(round(float(x), prec))

    obj = [float_to_limited_str(3.14), 'foo']
    json.dumps(obj)


class Caster(object):
    """
    Execute a bash-like input script and record it with its output as an Asciinema screencast.
    """
    def __init__(self, **kwargs):
        self.typist = AsciinemaTypist(ts=0)


    def set_header(self, header={}):
        dt = datetime.datetime
        width, height = shutil.get_terminal_size()
        self.ac_header = dict(
            version=2,
            width=width,
            height=height,
            timestamp=int(dt.timestamp(dt.now())),
            idle_time_limit=4.0,
            env=dict(
                SHELL=os.environ.get('SHELL', '/bin/bash'),
                TERM=os.environ.get('TERM', 'xterm-256color')
            )
        )
        self.ac_header.update(header)


    def type_input(self, f, block, typing_mode='human'):
        """
        Add input command "block" to the screencast as it would be typed by a human.
        """
        for i, line in enumerate(block):
            if not line.strip():
                ac_line = [self.typist.ts, 'o', '\r\n']
                # ac_line = [float_to_limited_str(self.typist.ts), 'o', '\r\n']
                f.write('{}\n'.format(json.dumps(ac_line)))
                self.typist.ts += 0.01
                continue

            # print input line
            line1 = re.sub('\n', '\r\n', line)
            delay_func = lambda: random.random() / 10.0 if typing_mode=='human' else 0
            for d, output in self.typist.timed_type(line1 + '\r\n',
                                               first_line=i==0,
                                               delay_func=delay_func):
                f.write(output)

            # don't process any further lines starting with '#'
            if re.match('^\s*#', line[0]):
                continue

            # hack for getting printing continuation lines as they are
            line = re.sub('\\\\\r?\n', '', line)


    def type_output(self, f, block, with_ansi=False):
        """
        Execute input command "block", capture and add results to the screencast.
        """
        # execute and time input command
        line = '\n'.join(block)
        line = expanduser(expandvars(line))
        t0 = time.time()
        if not with_ansi:
            s = subprocess.getoutput(line)
            self.typist.ts += (time.time() - t0)
            if s:
                for out_line in s.split('\n'):
                    ac_line = [self.typist.ts, 'o', '{}\r\n'.format(out_line)]
                    # ac_line = [float_to_limited_str(self.typist.ts), 'o', '{}\r\n'.format(out_line)]
                    f.write('{}\n'.format(json.dumps(ac_line)))
                    self.typist.ts += 0.01
        # print output, without ANSI escape sequences
        else:
            with CaptureOutput() as capturer:
                subprocess.call(line.split()) # trouble ahead with splitting
                self.typist.ts += (time.time() - t0)
                for out_line in capturer.get_lines(): #  + s.errors(raw=True):
                    ac_line = [self.typist.ts, 'o', '{}\r\n'.format(out_line)]
                    # ac_line = [float_to_limited_str(self.typist.ts), 'o', '{}\r\n'.format(out_line)]
                    f.write('{}\n'.format(json.dumps(ac_line)))
                    self.typist.ts += 0.01


    def record_screencast(self, input_path, output_path, with_ansi=False, typing_mode='human', header={}):
        """
        Execute an input script and record it as an Asciinema screencast.
        """
        self.set_header(header=header)
        with open(output_path, 'w') as f:
            f.write('{}\n'.format(json.dumps(self.ac_header)))
            with open(input_path) as g:
                content = g.read()
                for block in block_iter(content):
                    self.type_input(f, block, typing_mode=typing_mode)
                    self.type_output(f, block, with_ansi=with_ansi)

