from dataclasses import dataclass, field
from typing import List, Union, Iterable, Optional, Tuple, cast
from functools import reduce
import logging

logging.basicConfig(filename="qctool.log",
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)

logger = logging.getLogger(__name__)

@dataclass
class ColoredString:
    color: int
    string: str

    def __add__(self, string: str) -> "ColoredString":
        return ColoredString(self.color, self.string + string)
        
    def __len__(self) -> int:
        return len(self.string)

    def __getitem__(self, x: Union[int, slice]) -> "ColoredString":
        return ColoredString(self.color, self.string.__getitem__(x))

    def toString(self) -> str:
        return self.string
        

@dataclass
class ColoredLine:
    line: List[ColoredString] = field(default_factory=list)

    def __add__(self, s: Union["ColoredLine", ColoredString]) -> "ColoredLine":
        if isinstance(s, ColoredLine):
            return ColoredLine(self.line + s.line)
        elif isinstance(s, ColoredString):
            return ColoredLine(self.line + [s])

    def __len__(self):
        return sum(len(string) for string in self.line)

    def __getitem__(self, x: Union[int, slice]) -> "ColoredLine":
        if isinstance(x, int):
            i, xrem = self.findIndex(x)
            if i is None:
                raise IndexError(str(x))
            else:
                return ColoredLine([self.line[i][xrem]])
        elif isinstance(x, slice):
            if x.step != None:
                raise RuntimeError("step is not supported")
            else:
                i1, xrem1 = self.findIndex(0 if x.start is None else x.start)
                i2, xrem2 = self.findIndex(len(self) if x.stop is None else x.stop)
                if i1 is None:
                    return ColoredLine()
                elif i2 is None:
                    head = self.line[i1][xrem1:]
                    return ColoredLine([head] + self.line[i1+1:])
                elif i1 == i2:
                    return ColoredLine([self.line[i1][xrem1:xrem2]])
                elif xrem2 == 0:
                    head = self.line[i1][xrem1:]
                    return ColoredLine([head] + self.line[i1+1:i2])
                else:
                    head = self.line[i1][xrem1:]
                    tail = self.line[i2][:xrem2]
                    return ColoredLine([head] + self.line[i1+1:i2] + [tail])
            
    def coloredStrings(self):
        return self.line

    def center(self, color: int, w: int) -> "ColoredLine":
        diff = w - len(self)
        if diff > 0:
            l = diff // 2
            r = diff - l
            return toColoredLine(color, " " * l) + self + ColoredString(color, " " * r)
        else:
            return self

    def findIndex(self, x: int) -> Tuple[Optional[int], int]:
        xrem = x
        for i, cs in enumerate(self.line):
            lencs = len(cs)
            if xrem < lencs:
                return i, xrem
            xrem -= lencs
        return None, xrem

    def getColorAt(self, x: int) -> Optional[int]:
        i, _ = self.findIndex(x)
        if i is None:
            return None
        else:
            return self.line[i].color

    def toString(self) -> str:
        return "".join(cs.toString() for cs in self.line)

                          
def toColoredLine(color: int, string: str) -> ColoredLine:
    return ColoredLine([ColoredString(color, string)])


@dataclass
class ColoredText:
    text: List[ColoredLine] = field(default_factory=list)

    def __add__(self, s : Union["ColoredText", ColoredLine, ColoredString]) -> "ColoredText":
        if isinstance(s, ColoredText):
            if len(s.text) == 0:
                return self
            if len(self.text) == 0:
                return s
            else:
                return ColoredText(self.text[:-1] + [self.text[-1] + s.text[0]] + s.text[1:])
        elif isinstance(s, ColoredLine):
            return self + ColoredText([s])
        elif isinstance(s, ColoredString):
            return self + ColoredLine([s])

    def __len__(self) -> int:
        return sum(len(line) for line in self.text)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return ColoredText(self.text.__getitem__(key))
        else:
            return self.text.__getitem__(key)

    def clear(self):
        self.text = []

    def center(self, color: int, w: int) -> "ColoredText":
        return ColoredText([line.center(color, w) for line in self.text])

    def join(self, texts: Iterable["ColoredText"]) -> "ColoredText":
        try:
            iterator = iter(texts)
            head = next(iterator)
            return reduce(lambda x, y: x + self + y, iterator, head)
        except StopIteration:
            return ColoredText()

    def numberOfLines(self) -> int:
        return len(self.text)

    def lines(self) -> List[ColoredLine]:
        return self.text

    def delete(self, y: int, x: int) -> "ColoredText":
        if x == len(self.text[y]):
            if y < self.numberOfLines() - 1:
                return ColoredText(self.text[:y] + [self.text[y] + self.text[y+1]] + self.text[y+2:])
            else:
                return self
        else:
            return ColoredText(self.text[:y] + [self.text[y][:x] + self.text[y][x+1:]] + self.text[y+1:])
        
    def insert(self, y: int, x: int, ch: "ColoredText") -> "ColoredText":
        left = ColoredText(self.text[:y] + [self.text[y][:x]])
        right = ColoredText([self.text[y][x:]] + self.text[y+1:])
        
        return left + ch + right

    def getColorAt(self, y: int, x: int) -> Optional[int]:
        return self.text[y].getColorAt(x)

    def toString(self) -> str:
        return "\n".join(line.toString() for line in self.text)


def toColoredLines(color: int, string: str) -> List[ColoredLine]:
    return [toColoredLine(color, line) for line in string.split("\n")]


def toColoredText(color: int, string: str) -> ColoredText:
    return ColoredText(toColoredLines(color, string))
