from coloredtext import toColoredText, ColoredText
from itertools import chain
import logging

logging.basicConfig(filename="qctool.log",
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)

logger = logging.getLogger(__name__)


def format_table(color, column_names, rows, upper_border=True, lower_border=True, left_border=True, right_border=True):
    columns = list(map(list, zip(*rows))) if len(rows) > 0 else [[] for _ in column_names]
    column_widths = [max(chain([len(column_name)], (len(a) for a in column if a is not None))) + 2 for column_name, column in zip(column_names, columns)]
    table_width = sum(column_widths) + len(column_widths) -1 + (1 if left_border else 0) + (1 if right_border else 0)

    if upper_border:
        header = toColoredText(color, "-" * table_width)
        header += toColoredText(color, "\n")
    else:
        header = ColoredText()
    header += (toColoredText(color, "|") if left_border else ColoredText()) + toColoredText(color, "|").join([column_name.center(color, w) for w, column_name in zip(column_widths, column_names)]) + (toColoredText(color, "|") if right_border else ColoredText())
    header += toColoredText(color, "\n")
    header += toColoredText(color, "-" * table_width)
    
        
    contents = [(toColoredText(color, "|") if left_border else ColoredText()) + toColoredText(color, "|").join([x.center(color, w) for w, x in zip(column_widths, row)]) + (toColoredText(color, "|") if right_border else ColoredText()) for row in rows]
    content = toColoredText(color, "\n").join(contents)
    
    if lower_border:
        footer = toColoredText(color, "-" * table_width)
    else:
        footer = ColoredText()

    return header, content, footer

