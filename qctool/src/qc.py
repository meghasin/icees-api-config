import sys
from typing import Tuple, Dict, List, Optional
import Levenshtein
import argparse
from argparse import RawTextHelpFormatter
import difflib
from itertools import chain
import asyncio
import curses
import logging
import os
from functools import reduce, partial
from dataclasses import dataclass, field
import csv
import traceback
from collections import defaultdict
from tx.functional.either import Left, Right
from window import HIGHLIGHT_COLOR, NORMAL_COLOR, Window, Pane, init_colors, SELECTED_NORMAL_COLOR, popup, draw_textfield, WindowExit, WindowPass, WindowContinue, ERROR_COLOR
from file import make_file, MappingFile, YAMLFile
from coloredtext import toColoredText, ColoredText
from table import format_table
from components import pick_file, help, choose_candidate, enter_var_name, command_keys, menu, choose_candidate_ratio, enter_var_name1, key_escape
from mode import DiffMode, FocusedMode, Config, CacheFile, CacheTables

APPLICATION_TITLE = "ICEES FHIR-PIT Configuration Tool"
HELP_TEXT_SHORT = "H help M menu U update tables Q exit "


# from https://stackoverflow.com/a/6386990
logging.basicConfig(filename="qctool.log",
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)

logger = logging.getLogger(__name__)

class Noop:
    def __str__(self):
        return ""

    def update(self, name, key_a, file_a, key_b, file_b):
        pass

    
class UseA:
    def __str__(self):
        return "use a"

    def update(self, name, key_a, file_a, key_b, file_b):
        file_b.update_key(name, key_b, key_a)

        
class UseB:
    def __str__(self):
        return "use b"

    def update(self, name, key_a, file_a, key_b, file_b):
        file_a.update_key(name, key_a, key_b)

    
class Customize:
    def __init__(self, var_name):
        self.var_name = var_name

    def __str__(self):
        return f"customize: {self.var_name}"

    def update(self, name, key_a, file_a, key_b, file_b):
        file_a.update_key(name, key_a, self.var_name)
        file_b.update_key(name, key_b, self.var_name)

    
class CustomizeA:
    def __init__(self, var_name):
        self.var_name = var_name

    def __str__(self):
        return f"customize a: {self.var_name}"

    def update(self, name, key_a, file_a, key_b, file_b):
        file_a.update_key(name, key_a, self.var_name)

    
class CustomizeB:
    def __init__(self, var_name):
        self.var_name = var_name

    def __str__(self):
        return f"customize b: {self.var_name}"

    def update(self, name, key_a, file_a, key_b, file_b):
        file_b.update_key(name, key_b, self.var_name)

    
def difference_ignore_suffix(a, b, ignore_suffix):
    diff = []
    for an in a:
        found = False
        for bn in b:
            if an == bn or any([an == bn + suffix or an + suffix == bn for suffix in ignore_suffix]):
                found = True
                break
        if not found:
            diff.append(an)
    return diff
            
    
def find_candidates(a, bn, similarity_threshold, n, ignore_suffix):
    if bn is None:
        return [(an, None) for an in a]
    else:
        ans = [(an, Levenshtein.ratio(an, bn)) for an in a]
        return sorted(ans, reverse=True, key=lambda t: t[1])


def truncate_set(a, b, a_only, b_only, similarity_threshold, n, ignore_suffix):
    diff_a = [] if b_only else difference_ignore_suffix(a, b, ignore_suffix)
    diff_b = [] if a_only else difference_ignore_suffix(b, a, ignore_suffix)

    def find_match(b, an):
        bns = [(bn, Levenshtein.ratio(an, bn)) for bn in b]
        if len(bns) == 0:
            bn = None
            ratio = 0
        else:
            bn, ratio = max(bns, key=lambda x: x[1])
        return (an, bn, ratio)

    diff_a_match = [find_match(b, an) for an in diff_a]
    diff_b_match = [find_match(a, bn) for bn in diff_b]

    diff_a_match_truncated = [(an, bn, ratio) if ratio >= similarity_threshold else (an, None, None) for an, bn, ratio in diff_a_match]
    diff_b_match_truncated = [(bn, an, ratio) if ratio >= similarity_threshold else (bn, None, None) for bn, an, ratio in diff_b_match]

    diff_b_match_switched = [(an, bn, ratio) for bn, an, ratio in diff_b_match_truncated]

    diff_a_match_dir = {(an, bn, ratio, "x", "x" if bn in diff_b else "") for an, bn, ratio in diff_a_match_truncated}
    diff_b_match_dir = {(an, bn, ratio, "x" if an in diff_a else "", "x") for an, bn, ratio in diff_b_match_switched}

    ls = sorted(list(diff_a_match_dir | diff_b_match_dir), reverse=True, key=lambda t: t[2] or 0)
    
    if n == -1:
        topn = ls
    else:
        topn = ls[:n]

    topnaction = list(map(lambda x: [x[0], x[1], x[2], x[3], x[4], Noop()], ls))
        
    return topnaction, n >= 0 and len(ls) > n


def colorize_diff(a: str, b: str) -> Tuple[ColoredText, ColoredText]:
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    opcodes = sm.get_opcodes()
    a_colorized = ColoredText()
    b_colorized = ColoredText()
    ab = HIGHLIGHT_COLOR
    bb = HIGHLIGHT_COLOR
    for tag, i1, i2, j1, j2 in opcodes:
        a_segment = a[i1:i2]
        b_segment = b[j1:j2]
        if tag == "equal":
            a_colorized += toColoredText(NORMAL_COLOR, a_segment)
            b_colorized += toColoredText(NORMAL_COLOR, b_segment)
        elif tag == "delete":
            a_colorized += toColoredText(ab, a_segment)
        elif tag == "insert":
            b_colorized += toColoredText(bb, b_segment)
        elif tag == "replace":
            a_colorized += toColoredText(ab, a_segment)
            b_colorized += toColoredText(bb, b_segment)
    return (a_colorized, b_colorized)
    
    
def to_prettytable(mode, l):
    if isinstance(mode, DiffMode):
        if l[0] is None:
            if l[1] is None:
                return [toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, l[3]), toColoredText(NORMAL_COLOR, l[4]), toColoredText(NORMAL_COLOR, str(l[5]))]
            else:
                return [toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, l[1]), toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, l[3]), toColoredText(NORMAL_COLOR, l[4]), toColoredText(NORMAL_COLOR, str(l[5]))]
        elif l[1] is None:
            return [toColoredText(NORMAL_COLOR, l[0]), toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, l[3]), toColoredText(NORMAL_COLOR, l[4]), toColoredText(NORMAL_COLOR, str(l[5]))]
        else:
            return list(colorize_diff(l[0], l[1])) + [toColoredText(NORMAL_COLOR, f"{l[2]:.2f}"), toColoredText(NORMAL_COLOR, l[3]), toColoredText(NORMAL_COLOR, l[4]), toColoredText(NORMAL_COLOR, str(l[5]))]
    else:
        if l[0] is None:
            return [toColoredText(NORMAL_COLOR, ""), toColoredText(NORMAL_COLOR, str(l[1]))]
        else:
            return [toColoredText(NORMAL_COLOR, l[0]), toColoredText(NORMAL_COLOR, str(l[1]))]
        

def reload_files(window, config, mode):
    if isinstance(mode, DiffMode):
        a_filename = mode.a_cache_file.update if config.a_updated else mode.a_cache_file.filename
        b_filename = mode.b_cache_file.update if config.b_updated else mode.b_cache_file.filename
        a_type = mode.a_cache_file.typ
        b_type = mode.b_cache_file.typ
        
        window.set_header(toColoredText(NORMAL_COLOR, APPLICATION_TITLE))
        window.set_footer(toColoredText(NORMAL_COLOR, f"loading {a_filename} ..."))
        try:
            a_file = make_file(a_type, a_filename)
        except Exception as e:
            logger.error(f"error loading {a_filename}\n")
            raise

        window.set_footer(toColoredText(NORMAL_COLOR, f"loading {b_filename} ..."))
        try:
            b_file = make_file(b_type, b_filename)
        except Exception as e:
            logger.error(f"error loading {b_filename}\n")
            raise

        window.set_footer(toColoredText(NORMAL_COLOR, f"comparing..."))
        tables = {}
        for table in config.table_names:
            a_var_names = a_file.get_keys(table)

            b_var_names = b_file.get_keys(table)

            tables[table] = truncate_set(a_var_names, b_var_names, config.a_only, config.b_only, config.similarity_threshold, config.max_entries, config.ignore_suffix)

        mode.update_files(config, a_file, b_file, tables)

    else:    
        filename = mode.cache_file.update if (config.a_updated and mode.a_focused) or (config.b_updated and not mode.a_focused) else mode.cache_file.filename
        typ = mode.cache_file.typ

        window.set_header(toColoredText(NORMAL_COLOR, APPLICATION_TITLE))
        window.set_footer(toColoredText(NORMAL_COLOR, f"loading {filename} ..."))
        try:
            fil = make_file(typ, filename)
        except Exception as e:
            logger.error(f"error loading {filename}\n")
            raise

        mode.update_file(config, fil, {name : ([[key, Noop()] for key in fil.get_keys(name)], False) for name in config.table_names})
    
    refresh(window, config, mode)
    

def refresh(window, config, mode):
    refresh_content(window, config, mode)
    top_pane = window.children["top_pane"]
    top_pane._move_abs(0,0)
    window.update()


def refresh_footer(window, config, mode):
    if window.focus == "left_pane" or window.focus == "right_pane" or window.focus == "bottom_pane":
        footer = toColoredText(NORMAL_COLOR, "ESCAPE exit")
    else:
        i = get_current_row_id(window.children["top_pane"]) + 1
        n = get_total_rows(config, mode)
        if i > n: # i might be on the ...
            i = n
        footer = toColoredText(HIGHLIGHT_COLOR, f"{i} / {n}") + toColoredText(NORMAL_COLOR, f" {HELP_TEXT_SHORT}")

    window.set_footer(footer)

    
def refresh_bottom_panes(window, config, mode, force=False):
    name = config.table_names[mode.cache_tables.current_table]
    row = get_current_row(window.children["top_pane"], config, mode)

    if isinstance(mode, DiffMode):
        if row is not None:
            key_a, key_b, _, _, _, _ = row
            if key_a is None:
                dump_get_a = ""
            else:
                dump_get_a = mode.a_cache_file.fil.dump_get(name, key_a)

            if key_b is None:
                dump_get_b = ""
            else:
                dump_get_b = mode.b_cache_file.fil.dump_get(name, key_b)
        else:
            key_a = None
            key_b = None
            dump_get_a = ""
            dump_get_b = ""

        if force or key_a != mode.a_cache_file.old_key:
            mode.a_cache_file.old_key = key_a
            left_pane = window.children["left_pane"]
            left_pane._clear()
            left_pane._append(toColoredText(NORMAL_COLOR, dump_get_a))

        if force or key_b != mode.b_cache_file.old_key:
            mode.b_cache_file.old_key = key_b
            right_pane = window.children["right_pane"]
            right_pane._clear()
            right_pane._append(toColoredText(NORMAL_COLOR, dump_get_b))

    else: # focused mode
        if row is not None:
            key, _ = row
            if key is None:
                dump_get = ""
            else:
                dump_get = mode.cache_file.fil.dump_get(name, key)
        else:
            key = None
            dump_get = ""

        if force or key != mode.cache_file.old_key:
            mode.cache_file.old_key = key
            bottom_pane = window.children["bottom_pane"]
            bottom_pane._clear()
            bottom_pane._append(toColoredText(NORMAL_COLOR, dump_get))

    refresh_footer(window, config, mode)
    window.update()

    
def refresh_content(window, config, mode):
    nav = toColoredText(NORMAL_COLOR, f"{APPLICATION_TITLE} ")
    for i, n in enumerate(config.table_names):
        if i > 0:
            nav += toColoredText(NORMAL_COLOR, " ")
        if i == mode.cache_tables.current_table:
            nav += toColoredText(HIGHLIGHT_COLOR, n)
        else:
            nav += toColoredText(NORMAL_COLOR, n)
    window._set_header(nav)

    name = config.table_names[mode.cache_tables.current_table]
    table, ellipsis = mode.cache_tables.tables[name]
    table_copy = list(table)
    if ellipsis:
        if isinstance(mode, DiffMode):
            table_copy.append(["...", None, None, "", Noop()])
        else:
            table_copy.append(["...", Noop()])
    if isinstance(mode, DiffMode):
        column_names = [toColoredText(NORMAL_COLOR, mode.a_cache_file.filename), toColoredText(NORMAL_COLOR, mode.b_cache_file.filename), toColoredText(NORMAL_COLOR, "ratio"), toColoredText(NORMAL_COLOR, "a"), toColoredText(NORMAL_COLOR, "b"), toColoredText(NORMAL_COLOR, "update")]
    else:
        column_names = [toColoredText(NORMAL_COLOR, mode.cache_file.filename), toColoredText(NORMAL_COLOR, "update")]

    rows = list(map(partial(to_prettytable, mode), table_copy))

    header, content, footer = format_table(NORMAL_COLOR, column_names, rows)

    content += toColoredText(NORMAL_COLOR, "\n")
    content += footer

    top_pane = window.children["top_pane"]
    header_pane = window.children["header_pane"]
    top_pane.bottom_padding = footer.numberOfLines()
    header_pane._replace(header)
    top_pane._replace(content)
    window.update()
    refresh_bottom_panes(window, config, mode)

    
def handle_window_resize(window, config, mode):
    window._teardown()
    setup_window(window, config, mode)

    refresh_content(window, config, mode)

        
def get_current_row_id(window):
    return max(0, window.current_document_y)


def get_total_rows(config, mode):
    name = config.table_names[mode.cache_tables.current_table]
    table, _ = mode.cache_tables.tables[name]
    return len(table)


def get_current_row(window, config, mode):
    name = config.table_names[mode.cache_tables.current_table]
    table, ellipsis = mode.cache_tables.tables[name]
    table_y = get_current_row_id(window)
    row = table[table_y] if table_y < len(table) else None
    return row
        

def focus_a(window, config):
    mode = FocusedMode(True, CacheFile(config.a_filename, config.a_type, update=config.a_update))
    refresh_mode(window, config, mode)
    return mode

    
def focus_b(window, config):
    mode = FocusedMode(False, CacheFile(config.b_filename, config.b_type, update=config.b_update))
    refresh_mode(window, config, mode)
    return mode

    
def diff_mode(window, config):
    mode = DiffMode(CacheFile(config.a_filename, config.a_type, update=config.a_update), CacheFile(config.b_filename, config.b_type, update=config.b_update))
    refresh_mode(window, config, mode)
    return mode

def refresh_mode(window, config, mode):
    window._teardown()
    setup_window(window, config, mode)
    reload_files(window, config, mode)

def extract_mappings(yamlfile, filename):
    if isinstance(yamlfile, MappingFile):
        with open(filename, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            code_index = header.index("Code")
            vocab_index = header.index("Vocab")
            mappings = defaultdict(list)
            for row in reader:
                code = row[code_index]
                vocab = row[vocab_index]
                if vocab == "RxNorm":
                    mappings["MedicationRequest"].append({
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": code
                    })
        return dict(mappings)
    else:
        raise RuntimeError("unsupported file type")

    
def setFocusByName(window, focus):
    if window.focus == "left_pane" or window.focus == "right_pane" or window.focus == "bottom_pane":
        window.children[window.focus].editable = False
    window.focus = focus
    if focus == "left_pane" or focus == "right_pane" or window.focus == "bottom_pane":
        window.children[focus].editable = True


def edit_left(window, config, mode):
    setFocusByName(window, "left_pane")
    refresh_footer(window, config, mode)

    
def edit_right(window, config, mode):
    setFocusByName(window, "right_pane")
    refresh_footer(window, config, mode)

    
def edit_bottom(window, config, mode):
    setFocusByName(window, "bottom_pane")
    refresh_footer(window, config, mode)

    
# def setFocus(focusIndex):
#     logger.info(f"=={focusIndex}")
#     setFocusByName(focusRing[focusIndex])

# def nextFocus(focusIndex):
#     logger.info(focusIndex)
#     focusIndex = (focusIndex + 1) % len(focusRing)
#     logger.info(f"->{focusIndex}")
#     setFocus(focusIndex)
#     return focusIndex

# focusRing = ["top_pane", "left_pane", "right_pane"]
# focusIndex = 0

def new_row(window, config, mode):
    name = config.table_names[mode.cache_tables.current_table]
    table, _ = mode.cache_tables.tables[name]
    i = window.children["top_pane"].current_document_y
    if isinstance(mode, DiffMode):
        table.insert(i, [None, None, None, "", "", Noop()])
    else:
        table.insert(i, ["", Noop()])
    refresh(window, config, mode)
    

def print_matches(window, config, init_mode):

    mode = init_mode    
    setFocusByName(window, "top_pane")
    reload_files(window, config, mode)

    def handle_command(ch):
        nonlocal mode
        ntables = len(config.table_names)
        name = config.table_names[mode.cache_tables.current_table]
        row = get_current_row(window.children["top_pane"], config, mode)
        
        if ch == ord("."):
            mode.cache_tables.current_table += 1
            mode.cache_tables.current_table %= ntables
            refresh(window, config, mode)
        elif ch == ord(","):
            mode.cache_tables.current_table += ntables - 1
            mode.cache_tables.current_table %= ntables
            refresh(window, config, mode)
        elif ch == ord("i"):
            mode = focus_a(window, config)
        elif ch == ord("j"):
            mode = focus_b(window, config)
        elif ch == ord("k"):
            mode = diff_mode(window, config)
            logger.info(f"handle_command: mode = {mode}")
        elif ch == ord("n"):
            new_row(window, config, mode)
        elif ch == ord("h"):
            help(window, mode)
            refresh_content(window, config, mode)
        else:
            if isinstance(mode, DiffMode):
                if row is not None:
                    if ch == ord("f"):
                        key_b = row[1]
                        a = mode.a_cache_file.fil.get_keys(name)            
                        candidates_a = find_candidates(a, key_b, config.similarity_threshold, config.max_entries, config.ignore_suffix)
                        c = choose_candidate_ratio(window, candidates_a)
                        if c is not None:
                            candidate_a, ratio = c
                            row[0] = candidate_a
                            row[2] = ratio
                            row[3] = "o"
                            refresh_content(window, config, mode)
                    elif ch == ord("g"):
                        key_a = row[0]
                        b = mode.b_cache_file.fil.get_keys(name)            
                        candidates_b = find_candidates(b, key_a, config.similarity_threshold, config.max_entries, config.ignore_suffix)
                        c = choose_candidate_ratio(window, candidates_b)
                        if c is not None:
                            candidate_b, ratio = c
                            row[1] = candidate_b
                            row[2] = ratio
                            row[4] = "o"
                            refresh_content(window, config, mode)
                    elif ch == ord("s"):
                        row[5] = Noop()
                        refresh_content(window, config, mode)
                    else:
                        if mode.a_cache_file.update is not None or mode.b_cache_file.update is not None:
                            if ch == ord("c"):
                                key_a, key_b, _, _, _, _ = row

                                c = enter_var_name(window, key_a, key_b)
                                if c is not None:
                                    row[5] = Customize(c)
                                    refresh_content(window, config, mode)
                            elif ch == ord("u"):
                                a_file = mode.a_cache_file.fil
                                b_file = mode.b_cache_file.fil
                                a_update = mode.a_cache_file.update
                                b_update = mode.b_cache_file.update
                                for name, (table, _) in mode.cache_tables.tables.items():
                                    window.set_footer(toColoredText(NORMAL_COLOR, f"updating table {name} ..."))
                                    for row in table:
                                        key_a, key_b, _, _, _, action = row
                                        action.update(name, key_a, a_file, key_b, b_file)
                                        row[5] = Noop()
                                    if a_update is not None:
                                        window.set_footer(toColoredText(NORMAL_COLOR, f"writing to file {a_update} ..."))
                                        a_file.dump(a_update)
                                        config.a_updated = True
                                    if b_update is not None:
                                        window.set_footer(toColoredText(NORMAL_COLOR, f"writing to file {b_update} ..."))
                                        b_file.dump(b_update)
                                        config.b_updated = True
                                reload_files(window, config, mode)
                            else:
                                if mode.b_cache_file.update is not None:                                
                                    if ch == ord("a"):
                                        row[5] = UseA()
                                        refresh_content(window, config, mode)
                                    elif ch == ord("d"):
                                        key_a, key_b, _, _, _, _ = row

                                        c = enter_var_name(window, key_a, key_b)
                                        if c is not None:
                                            row[5] = CustomizeB(c)
                                            refresh_content(window, config, mode)
                                    elif ch == ord("r"):
                                        edit_right(window, config, mode)
                                    elif ch == ord("w"):
                                        filename = pick_file(window, ".")
                                        if filename is not None:
                                            b_file = mode.b_cache_file.fil
                                            a_file = mode.a_cache_file.fil
                                            mappings = extract_mappings(b_file, filename)
                                            _, key_b, _, _, _, _ = row
                                            b_file.update_value(name, key_b, mappings)
                                            refresh_bottom_panes(window, config, mode, force=True)
                                if mode.a_cache_file.update is not None:
                                    if ch == ord("b"):
                                        row[5] = UseB()
                                        refresh_content(window, config, mode)
                                    elif ch == ord("e"):
                                        key_a, key_b, _, _, _, _ = row
                            
                                        c = enter_var_name(window, key_a, key_b)
                                        if c is not None:
                                            row[5] = CustomizeA(c)
                                            refresh_content(window, config, mode)
                                    elif ch == ord("l"):
                                        edit_left(window, config, mode)
                                    elif ch == ord("v"):
                                        filename = pick_file(window, ".")
                                        if filename is not None:
                                            b_file = mode.b_cache_file.fil
                                            a_file = mode.a_cache_file.fil
                                            mappings = extract_mappings(a_file, filename)
                                            key_a, _, _, _, _, _ = row
                                            a_file.update_value(name, key_a, mappings)
                                            refresh_bottom_panes(window, config, mode, force=True)

            else: # focused mode
                if row is not None:
                    if ch == ord("f"):
                        keys = mode.cache_file.fil.get_keys(name)            
                        c = choose_candidate(window, keys)
                        if c is not None:
                            row[0] = c
                            refresh_content(window, config, mode)
                    elif ch == ord("s"):
                        row[1] = Noop()
                        refresh_content(window, config, mode)
                    else:
                        if mode.cache_file.update is not None:
                            if ch == ord("e"):
                                key, _ = row

                                c = enter_var_name1(window, key)
                                if c is not None:
                                    row[1] = CustomizeA(c)
                                    refresh_content(window, config, mode)

                            elif ch == ord("l"):
                                edit_bottom(window, config, mode)

                            elif ch == ord("u"):
                                fil = mode.cache_file.fil
                                update = mode.cache_file.update
                                for name, (table, _) in mode.cache_tables.tables.items():
                                    window.set_footer(toColoredText(NORMAL_COLOR, f"updating table {name} ..."))
                                    for row in table:
                                        key, action = row
                                        action.update(name, key, fil, None, None)
                                        row[1] = Noop()
                                    window.set_footer(toColoredText(NORMAL_COLOR, f"writing to file {update} ..."))
                                    fil.dump(update)
                                    if mode.a_focused:
                                        config.a_updated = True
                                    else:
                                        config.b_updated = True
                                reload_files(window, config, mode)
                            elif ch == ord("v"):
                                filename = pick_file(window, ".")
                                if filename is not None:
                                    mappings = extract_mappings(mode.cache_file.fil, filename)
                                    key, _ = row
                                    mode.cache_file.fil.update_value(name, key, mappings)
                                    refresh_bottom_panes(window, config, mode, force=True)

    while True:
        try:
            ch = window.getch()
            if ch == curses.KEY_RESIZE:
                handle_window_resize(window)
            elif window.focus == "top_pane":
                if ch in command_keys(mode) and ch != ord("q") and ch != ord("m"):
                    handle_command(ch)
                elif ch == ord("m"):
                    ch2 = menu(window, mode)
                    if ch2 == ord("q"):
                        break
                    handle_command(ch2)
                    refresh_footer(window, config, mode)
                elif ch == ord("q"):
                    break
                else:
                    window._onKey(ch)
            else:
                if key_escape(ch):
                    name = config.table_names[mode.cache_tables.current_table]
                    row = get_current_row(window.children["top_pane"], config, mode)
                    if window.focus == "left_pane":
                        if row is not None:
                            key_a, _, _, _, _, _ = row

                            a_file = mode.a_cache_file.fil
                            a_file.update_value(name, key_a, a_file.yaml.load(window.children["left_pane"].lines.toString()))
                    elif window.focus == "right_pane":
                        if row is not None:
                            _, key_b, _, _, _, _ = row

                            b_file = mode.b_cache_file.fil
                            b_file.update_value(name, key_b, b_file.yaml.load(window.children["right_pane"].lines.toString()))
                    elif window.focus == "bottom_pane":
                        if row is not None:
                            key, _ = row

                            fil = mode.cache_file.fil
                            fil.update_value(name, key, fil.yaml.load(window.children["bottom_pane"].lines.toString()))
                    setFocusByName(window, "top_pane")
                    refresh_footer(window, config, mode)
                else:
                    window._onKey(ch)
            window.update()
        except Exception as e:
            logger.error(traceback.format_exc())
            window.set_footer(toColoredText(ERROR_COLOR, str(e)))                                         

    
def create_window(stdscr, config, mode):
    window = Window(stdscr)
    setup_window(window, config, mode)
    return window
    

def setup_window(window, config, mode):
    height, width = window.size()
    splittery = height // 2
    top_height = max(0, splittery - 1)
    bottom_height = max(0, height - splittery - 2)
    header_pane = window.pane("header_pane", 3, width, 1, 0, False)
    top_pane = window.pane("top_pane", top_height - 3, width, 4, 0, True)
    horizontal_splitter = window.fill("horizontal_splitter", 1, width, splittery, 0, "-")

    if isinstance(mode, DiffMode):
        splitterx = width // 2
        left_width = splitterx
        right_width = width - splitterx - 1
        left_pane = window.pane("left_pane", bottom_height, left_width, splittery + 1, 0, False)
        right_pane = window.pane("right_pane", bottom_height, right_width, splittery + 1, splitterx + 1, False)
        vertical_splitter = window.fill("vertical_splitter", bottom_height, 1, splittery + 1, splitterx, "|")
    else:
        bottom_pane = window.pane("bottom_pane", bottom_height, width, splittery + 1, 0, False)

    def handleCursorMove(source, oc, c):
        refresh_bottom_panes(window, config, mode)
        
    top_pane.addCursorMoveHandler(handleCursorMove)
    
    window.update()


def curses_main(stdscr, args):
    a_filename = args.a
    a_type = args.a_type
    a_update = args.update_a
    a_only = args.a_only

    b_filename = args.b
    b_type = args.b_type
    b_update = args.update_b
    b_only = args.b_only

    table_names = args.table
    max_entries = args.number_entries
    ignore_suffix = args.ignore_suffix
    similarity_threshold = args.similarity_threshold

    init_colors()

    config = Config(
        a_filename = a_filename,
        b_filename = b_filename,
        a_type = a_type,
        b_type = b_type,
        a_only = a_only,
        b_only = b_only,
        table_names = table_names,
        similarity_threshold = similarity_threshold,
        max_entries = max_entries,
        ignore_suffix = ignore_suffix,
        a_updated = False,
        b_updated = False,
        a_update = a_update,
        b_update = b_update
    )

    mode = DiffMode(CacheFile(a_filename, a_type, a_update), CacheFile(b_filename, b_type, b_update))

    window = create_window(stdscr, config, mode)

    print_matches(window, config, mode)


def main():
    parser = argparse.ArgumentParser(description="""ICEES FHIR-PIT QC Tool

Compare feature variable names in two files. Use --a and --b to specify filenames, --a_type and --b_type to specify file types, --update_a and --update_b to specify output files. Files types are one of features, mapping, and identifiers. If --update_a or --update_b is not specified then the files cannot be updated.""", formatter_class=RawTextHelpFormatter)
    parser.add_argument('--a', metavar='A', type=str, required=True,
                        help='file a')
    parser.add_argument('--b', metavar='B', type=str, required=True,
                        help='file b')
    parser.add_argument('--a_type', metavar='A_TYPE', choices=["features", "mapping", "identifiers"], required=True,
                        help='type of file a')
    parser.add_argument('--b_type', metavar='B_TYPE', choices=["features", "mapping", "identifiers"], required=True,
                        help='type of file b')
    parser.add_argument('--a_only', default=False, action="store_true",
                        help='only show variable names in a that are not in b')
    parser.add_argument('--b_only', default=False, action="store_true",
                        help='only show variable names in b that are not in a')
    parser.add_argument('--number_entries', metavar='NUMBER_ENTRIES', type=int, default=-1,
                        help='number of entries to display, -1 for unlimited')
    parser.add_argument('--ignore_suffix', metavar='IGNORE_SUFFIX', type=str, default=[], nargs="*",
                        help='the suffix to ignore')
    parser.add_argument("--similarity_threshold", metavar="SIMILARITY_THRESHOLD", type=float, default=0,
                        help="the threshold for similarity suggestions")
    parser.add_argument('--table', metavar='TABLE', type=str, required=True, nargs="+",
                        help='tables')
    parser.add_argument("--update_a", metavar="UPDATE_A", type=str,
                        help="YAML file for the updated a. If this file is not specified then a cannot be updated")
    parser.add_argument("--update_b", metavar="UPDATE_B", type=str,
                        help="YAML file for the updated b. If this file is not specified then b cannot be updated")

    args = parser.parse_args()

    os.environ.setdefault('ESCDELAY', '25')

    curses.wrapper(lambda stdscr: curses_main(stdscr, args))


if __name__ == "__main__":
    main()

