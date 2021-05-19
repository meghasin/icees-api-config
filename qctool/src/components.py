import os
import os.path
from dataclasses import dataclass
from functools import reduce
import curses
from window import WindowPass, WindowContinue, WindowExit, NORMAL_COLOR
from table import format_table
from coloredtext import toColoredText
from file import YAMLFile
from mode import DiffMode, FocusedMode
from typing import Type, List

@dataclass
class Command:
    key: int
    key_name: str
    text: str
    extended: bool # whether not show in the main window
    menu: bool # whether show in the menu
    modes: List[Type]
    
COMMANDS = [
    Command(ord(","), "COMMA", "previous table", False, True, [DiffMode, FocusedMode]),
    Command(ord("."), "PERIOD", "next table", False, True, [DiffMode, FocusedMode]),
    Command(curses.KEY_UP, "UP", "move up", True, False, [DiffMode, FocusedMode]),
    Command(curses.KEY_DOWN, "DOWN", "move down", True, False, [DiffMode, FocusedMode]),
    Command(curses.KEY_PPAGE, "PAGE UP", "page up", True, False, [DiffMode, FocusedMode]),
    Command(curses.KEY_NPAGE, "PAGE DOWN", "page down", True, False, [DiffMode, FocusedMode]),
    Command(ord("i"), "I", "focus on a", False, True, [DiffMode, FocusedMode]),
    Command(ord("j"), "J", "focus on b", False, True, [DiffMode, FocusedMode]),
    Command(ord("k"), "K", "diff mode", False, True, [DiffMode, FocusedMode]),
    Command(ord("a"), "A", "use a", False, True, [DiffMode]),
    Command(ord("b"), "B", "use b", False, True, [DiffMode]),
    Command(ord("d"), "D", "customize b", False, True, [DiffMode]),
    Command(ord("e"), "E", "customize a", False, True, [DiffMode, FocusedMode]),
    Command(ord("c"), "C", "customize", False, True, [DiffMode]),
    Command(ord("s"), "S", "skip", False, True, [DiffMode, FocusedMode]),
    Command(ord("f"), "F", "pick candidate from a", False, True, [DiffMode, FocusedMode]),
    Command(ord("g"), "G", "pick candidate from b", False, True, [DiffMode]),
    Command(ord("l"), "L", "update a value", False, True, [DiffMode, FocusedMode]),
    Command(ord("r"), "R", "update b value", False, True, [DiffMode]),
    Command(ord("u"), "U", "update tables", False, True, [DiffMode, FocusedMode]),
    Command(ord("v"), "V", "update a by loading codes from a table", False, True, [DiffMode, FocusedMode]),
    Command(ord("w"), "W", "update b by loading codes from a table", False, True, [DiffMode]),
    Command(ord("n"), "N", "append new row", False, True, [DiffMode, FocusedMode]),
    Command(ord("h"), "H", "help", False, True, [DiffMode, FocusedMode]),
    Command(ord("m"), "M", "menu", False, False, [DiffMode, FocusedMode]),
    Command(ord("q"), "Q", "quit", False, True, [DiffMode, FocusedMode])
]

def instanceofs(mode, modes):
    return any(isinstance(mode, t) for t in modes)
        

def command_keys(mode):
    return [c.key for c in COMMANDS if not c.extended and instanceofs(mode, c.modes)]


def menu_keys(mode):
    return [c.key for c in COMMANDS if c.menu and instanceofs(mode, c.modes)]

def HELP_TEXT_LONG(mode):
    help_texts = [c.key_name.ljust(10) + c.text for c in COMMANDS if not c.extended and instanceofs(mode, c.modes)]
    help_texts_width = max(map(len, help_texts))
    return "\n".join(l.ljust(help_texts_width) + " " + r.ljust(help_texts_width) for l, r in zip(help_texts[::2], help_texts[1::2])) + """

In the a and b columns
          variable exists in other file
x         variable doesn't exist in other file
o         variable is a candidate
"""

def MENU_TEXT(mode):
    return "\n".join(c.key_name.ljust(10) + c.text for c in COMMANDS if c.menu and instanceofs(mode, c.modes))

def key_enter(ch):
    return ch == curses.KEY_ENTER or ch == ord("\n") or ch == ord("\r")


def key_escape(ch):
    return ch == 27


def pick_file(window, starting_path):

    path = os.path.abspath(starting_path)

    help_text_short = "UP DOWN PAGE UP PAGE DOWN navigate ENTER confirm ESCAPE exit"

    def _refresh_content(popwindow):
        files = os.listdir(path)
        header_pane = popwindow.children["header_pane"]
        poph, popw = popwindow.size()
        popcontent_pane = popwindow.children["content_pane"]
        header_pane.text = toColoredText(NORMAL_COLOR, f"{path}\n{'-' * (popw - 2)}")
        popcontent_pane._replace(toColoredText(NORMAL_COLOR, "\n".join([".."] + files)))

    def create_window(popwindow):
        popwindow.window.keypad(1)
        poph, popw = popwindow.size()
        header_pane = popwindow.text("header_pane", 2, popw - 2, 1, 1, toColoredText(NORMAL_COLOR, ""))
        popcontent_pane = popwindow.pane("content_pane", poph - 4, popw - 2, 3, 1, True)
        _refresh_content(popwindow)

    def key_handler(popwindow, ch):
        nonlocal path
        popcontent_pane = popwindow.children["content_pane"]
        if key_enter(ch):
            filename = popcontent_pane.lines.lines()[popcontent_pane.current_document_y].toString()
            if filename == "..":
                path = os.path.dirname(path)
                _refresh_content(popwindow)
                return WindowContinue()
            else:
                path = os.path.join(path, filename)
                if os.path.isfile(path):
                    return WindowExit(path)
                elif os.path.isdir(path):
                    _refresh_content(popwindow)
                    return WindowContinue()
        elif key_escape(ch):
            return WindowExit(None)
        else:
            return WindowPass()

    return window.popup(toColoredText(NORMAL_COLOR, help_text_short), create_window, key_handler, None)


def popup_text(window, text_content):
    def create_window(popwindow):
        poph, popw = popwindow.size()
        text = popwindow.text("text_pane", poph - 1, popw - 1, 1, 1, toColoredText(NORMAL_COLOR, text_content))

    def key_handler(win, ch):
        return WindowExit(None) if key_escape(ch) else WindowPass()

    window.popup(toColoredText(NORMAL_COLOR, "ESCAPE exit"), create_window, key_handler, None)


def help(window, mode):
    popup_text(window, HELP_TEXT_LONG(mode))


def enter_var_name(window, key_a, key_b):

    def create_window(popwindow):
        _, popw = popwindow.size()
        a_text = popwindow.text("a_text", 1, popw - 2, 1, 1, toColoredText(NORMAL_COLOR, f"a: {key_a}"))
        b_text = popwindow.text("b_text", 1, popw - 2, 2, 1, toColoredText(NORMAL_COLOR, f"b: {key_b}"))
        c_textfield = popwindow.textfield("c_textfield", popw - 2, 3, 1, "c:", "")
        popwindow.focus = "c_textfield"

    def key_handler(window, ch):
        if key_enter(ch):
            c_textfield = window.children["c_textfield"]
            return WindowExit(c_textfield.text)
        elif key_escape(ch):
            return WindowExit(None)
        else:
            return WindowPass()

    c = window.popup(toColoredText(NORMAL_COLOR, "ENTER confirm ESCAPE exit"), create_window, key_handler, h = 5)

    return c


def enter_var_name1(window, key_a):

    def create_window(popwindow):
        _, popw = popwindow.size()
        a_text = popwindow.text("a_text", 1, popw - 2, 1, 1, toColoredText(NORMAL_COLOR, f"a: {key_a}"))
        c_textfield = popwindow.textfield("c_textfield", popw - 2, 2, 1, "c:", "")
        popwindow.focus = "c_textfield"

    def key_handler(window, ch):
        if key_enter(ch):
            c_textfield = window.children["c_textfield"]
            return WindowExit(c_textfield.text)
        elif key_escape(ch):
            return WindowExit(None)
        else:
            return WindowPass()

    c = window.popup(toColoredText(NORMAL_COLOR, "ENTER confirm ESCAPE exit"), create_window, key_handler, h = 4)

    return c


def format_row(row):
    return [toColoredText(NORMAL_COLOR, header) for header in row]
        
def choose_candidate_ratio(window, candidates):
    help_text_short = "UP DOWN PAGE UP PAGE DOWN navigate ENTER confirm ESCAPE exit"

    candidates_w = max(len("candidate"), max(len(candidate) for candidate, _ in candidates)) + 2
    ratios_w = len("ratio") + 2
    column_ws = [candidates_w, ratios_w]
    table_w = reduce(lambda x, y: x + y + 1, column_ws, 0)
    headers = ["candidate", "ratio"]

    def f(candidates):
        return format_table(NORMAL_COLOR, format_row(headers), list(map(format_row, map(lambda r : [r[0], "" if r[1] is None else f"{r[1]:.2f}"], candidates))), upper_border = False, left_border=False, right_border=False)
    
    header, content, footer = f(candidates)

    content += toColoredText(NORMAL_COLOR, "\n")
    content += footer

    _, w = window.size()
    popw = min(len(header.lines()[0]) + 2, w * 4 // 5)

    popwindow = None
    candidates_filtered = None

    def match(c, candidate):
        return c.lower() in candidate.lower()
        
    def update_content(source, oc, c):
        nonlocal candidates_filtered
        popcontent_pane = popwindow.children["content_pane"]
        candidates_filtered = [[candidate, ratio] for candidate, ratio in candidates if match(c, candidate)]
        header, content, footer = f(candidates_filtered)

        content += toColoredText(NORMAL_COLOR, "\n")
        content += footer

        popcontent_pane._replace(content)

    def create_window(window):
        nonlocal popwindow
        popwindow = window
        popwindow.window.keypad(1)
        poph, popw = popwindow.size()
        popheader_pane = popwindow.pane("header_pane", 3, popw - 2, 1, 1, False)
        popcontent_pane = popwindow.pane("content_pane", poph - 5, popw - 2, 3, 1, True)
        popcontent_pane.bottom_padding = 1
        popsearch_textfield = popwindow.textfield("search_textfield", popw - 2, poph - 2, 1, "search:", "")
        popsearch_textfield.addChangeHandler(update_content)
        popwindow.focus = "search_textfield"

        popheader_pane._replace(header)
        popcontent_pane._replace(content)
        update_content(None, None, "")

    def candidates_get_current_row_id(popcontent_pane):
        return max(0, popcontent_pane.current_document_y)

    def key_handler(popwindow, ch):
        popcontent_pane = popwindow.children["content_pane"]
        search_textfield = popwindow.children["search_textfield"]

        if key_enter(ch):
            i = candidates_get_current_row_id(popcontent_pane)
            c = candidates_filtered[i]
            return WindowExit(c)
        elif key_escape(ch):
            return WindowExit(None)

    c = window.popup(toColoredText(NORMAL_COLOR, help_text_short), create_window, key_handler, w=popw)

    return c


def choose_candidate(window, candidates):
    help_text_short = "UP DOWN PAGE UP PAGE DOWN navigate ENTER confirm ESCAPE exit"

    candidates_w = max(len("candidate"), max(len(candidate) for candidate in candidates)) + 2
    column_ws = [candidates_w]
    table_w = reduce(lambda x, y: x + y + 1, column_ws, 0)
    headers = ["candidate"]

    def f(candidates):
        return format_table(NORMAL_COLOR, format_row(headers), list(map(format_row, map(lambda r : [r], candidates))), upper_border = False, left_border=False, right_border=False)
    
    header, content, footer = f(candidates)

    content += toColoredText(NORMAL_COLOR, "\n")
    content += footer

    _, w = window.size()
    popw = min(len(header.lines()[0]) + 2, w * 4 // 5)

    popwindow = None
    candidates_filtered = None

    def match(c, candidate):
        return c.lower() in candidate.lower()
        
    def update_content(source, oc, c):
        nonlocal candidates_filtered
        popcontent_pane = popwindow.children["content_pane"]
        candidates_filtered = [candidate for candidate in candidates if match(c, candidate)]
        header, content, footer = f(candidates_filtered)

        content += toColoredText(NORMAL_COLOR, "\n")
        content += footer

        popcontent_pane._replace(content)

    def create_window(window):
        nonlocal popwindow
        popwindow = window
        popwindow.window.keypad(1)
        poph, popw = popwindow.size()
        popheader_pane = popwindow.pane("header_pane", 3, popw - 2, 1, 1, False)
        popcontent_pane = popwindow.pane("content_pane", poph - 5, popw - 2, 3, 1, True)
        popcontent_pane.bottom_padding = 1
        popsearch_textfield = popwindow.textfield("search_textfield", popw - 2, poph - 2, 1, "search:", "")
        popsearch_textfield.addChangeHandler(update_content)
        popwindow.focus = "search_textfield"

        popheader_pane._replace(header)
        popcontent_pane._replace(content)
        update_content(None, None, "")

    def candidates_get_current_row_id(popcontent_pane):
        return max(0, popcontent_pane.current_document_y)

    def key_handler(popwindow, ch):
        popcontent_pane = popwindow.children["content_pane"]
        search_textfield = popwindow.children["search_textfield"]

        if key_enter(ch):
            i = candidates_get_current_row_id(popcontent_pane)
            c = candidates_filtered[i]
            return WindowExit(c)
        elif key_escape(ch):
            return WindowExit(None)

    c = window.popup(toColoredText(NORMAL_COLOR, help_text_short), create_window, key_handler, w=popw)

    return c


def menu(window, mode):
    def create_window(popwindow):
        poph, popw = popwindow.size()
        menu_pane = popwindow.pane("menu_pane", poph - 1, popw - 1, 1, 1, selectable=True)
        menu_pane.lines = toColoredText(NORMAL_COLOR, MENU_TEXT(mode))
        popwindow.window.keypad(1)

    def key_handler(popwin, ch):
        if ch in menu_keys(mode):
            return WindowExit(ch)
        elif key_escape(ch):
            return WindowExit(None)
        elif key_enter(ch):
            menu_pane = popwin.children["menu_pane"]
            key_name = menu_pane.lines.toString().split("\n")[menu_pane.current_document_y].split(" ")[0]
            key = next(c.key for c in COMMANDS if c.key_name == key_name)
            return WindowExit(key)
        else:
            return WindowPass()

    c = window.popup(toColoredText(NORMAL_COLOR, "ENTER confirm ESCAPE exit"), create_window, key_handler, w=max(map(len, MENU_TEXT(mode).split("\n"))) + 2)
    return c
