#!/usr/bin/env python3
import sys

if sys.stdout.isatty():
  do_fmt = True
else:
  do_fmt = False

def no_color_printing():
  global do_fmt
  do_fmt = False

def color_printing():
  global do_fmt
  do_fmt = True


def fmt(tag, text):
  if do_fmt:
    return tag+text+'\033[0m'
  else:
    return text


def bold(text):
  return fmt('\033[1m', text)


def color(color_code, text):
  return fmt('\033[0;3{}m'.format(color_code), text)


def red(text):
  return color(1, text)

def green(text):
  return color(2, text)

def yellow(text):
  return color(3, text)

def blue(text):
  return color(4, text)

def magenta(text):
  return color(5, text)

def cyan(text):
  return color(6, text)
