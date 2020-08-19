#!/usr/bin/env python3

# A program to display the contents of a directory as rectangles
# with sizes according to the files sizes. It is supposed to work
# like Konqueror's "File Size View", but it uses curses.

import curses
import math
import optparse
import os
import subprocess
import sys


DU_COMMAND = "du -a -B1"
BLOCKSIZE = 1

if sys.platform == "darwin":
    # Default `du` on MacOS doesn't have the -B option.
    try:
        # See if GNU du (gdu) is installed.
        subprocess.call(["gdu", "--version"], stdout=subprocess.PIPE)
    except OSError:
        # gdu is not installed. Use built-in du with its 512 byte blocks.
        DU_COMMAND = "du -a"
        BLOCKSIZE = 512
    else:
        # gdu is installed. Let's use it.
        DU_COMMAND = "g" + DU_COMMAND


def increase_n_highest(numbers, n):
    indices = [-1] * (n)
    for i, num in enumerate(numbers):
        num = num % 1
        for j, ind in enumerate(indices):
            if ind == -1 or num > numbers[ind]:
                indices.insert(j, i)
                indices = indices[:-1]
                break
    for i in indices:
        numbers[i] = math.ceil(numbers[i])
    for i, num in enumerate(numbers):
        numbers[i] = int(math.floor(num))
    return numbers


class fsvError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

    def __str__(self):
        return "Error: " + Exception.__str__(self)


class fsvFile:
    def __init__(self, name, size):
        self._name = name
        self._size = size
        self._window = None

    def name(self):
        return self._name

    def size(self):
        return self._size

    def set_window(self, window):
        self._window = window

    def setup(self):
        pass

    def calculate_content(self, color, draw_frame=None):
        maxy, maxx = self._window.getmaxyx()
        if len(self._name) > maxx * maxy:
            return color
        self._window.addnstr(0, 0, self._name, maxx * maxy - 1)
        if len(self._name) == maxx * maxy:
            self._window.insstr(maxy - 1, maxx - 1, self._name[-1])
        size_str = self.get_size_string()
        if len(size_str) + len(self._name) < maxx * maxy and len(size_str) <= maxx:
            i, j = (len(size_str)).__divmod__(maxx)
            self._window.insstr(maxy - 1, maxx - len(size_str), size_str)
        return color

    def contains_point(self, y, x):
        if self._window:
            begyx = self._window.getbegyx()
            maxyx = self._window.getmaxyx()
            if (
                begyx[0] <= y < begyx[0] + maxyx[0]
                and begyx[1] <= x < begyx[1] + maxyx[1]
            ):
                return True
        return False

    def get_size_string(self):
        s = float(self._size)
        units = "BKMGT"
        c = 0
        while s > 1024:
            s /= 1024
            c += 1
        if s < 10:
            return "%.1f" % s + units[c]
        return "%.0f" % s + units[c]

    def get_path(self, y, x):
        if not self.contains_point(y, x):
            return None
        return [self]


class fsvDirectory(fsvFile):
    frame_size = (1, 1)

    def __init__(self, name, size=0):
        fsvFile.__init__(self, name, size)
        self._files = []

    def name(self):
        return self._name + os.path.sep

    def add_file(self, f):
        self._files.append(f)
        self._size += f.size()

    def set_files(self, files):
        self._files = files
        self._size = sum(f.size() for f in files)

    def setup(self):
        self._files.sort(key=lambda f: f.size(), reverse=True)

    def calculate_content(self, color, draw_frame=True):
        if draw_frame:
            self.write_name()
        if self._size == 0:
            return color
        exact_heights = []
        indices = []
        w_width = self._window.getmaxyx()[1] - self.frame_size[1] * draw_frame
        w_height = self._window.getmaxyx()[0] - self.frame_size[0] * draw_frame
        if (not w_width) or (not w_height):
            return color
        size_fac = float(w_width * w_height) / self._size
        current_indices = [0, 1]
        difference = 1000
        size_sum = 0.0
        for i, f in enumerate(self._files):
            new_size_sum = size_sum + size_fac * f.size()
            new_difference = abs(
                new_size_sum / w_width - w_width / (i + 1 - current_indices[0])
            )
            if new_difference > difference:
                exact_heights.append(size_sum / w_width)
                indices.append(current_indices)
                current_indices = [i, i + 1]
                size_sum = size_fac * f.size()
                difference = abs(size_sum / w_width - w_width)
            else:
                size_sum = new_size_sum
                difference = new_difference
                current_indices[1] = i + 1
        indices.append(current_indices)
        exact_heights.append(size_sum / w_width)
        num = w_height - sum([int(math.floor(x)) for x in exact_heights])
        # raise str(heights)
        heights = [x for x in exact_heights]  # an ugly deep copy...
        heights = increase_n_highest(heights, num)
        sum_height = self.frame_size[0] * draw_frame
        for i, (start, end) in enumerate(indices):
            if not heights[i]:
                continue
            widths = []
            sum_width = 0
            for j in range(start, end):
                w = self._files[j].size() * size_fac / exact_heights[i]
                widths.append(w)
                sum_width += int(math.floor(w))
            widths = increase_n_highest(widths, w_width - sum_width)
            sum_width = self.frame_size[1] * draw_frame
            for j in range(start, end):
                if not widths[j - start]:
                    continue
                color += 1
                if color > 7:
                    color = 1
                win = self._window.derwin(
                    heights[i], widths[j - start], sum_height, sum_width
                )
                win.bkgdset(" ", curses.color_pair(color))
                win.clear()
                self._files[j].set_window(win)
                color = self._files[j].calculate_content(color, draw_frame)
                # win.refresh()
                sum_width += widths[j - start]
            sum_height += heights[i]
        return color

    def write_name(self):
        name_str = self.name()
        len_name = len(name_str)
        size_str = self.get_size_string()
        len_size = len(size_str)
        maxy, maxx = self._window.getmaxyx()
        if len_name <= maxx:
            self._window.insstr(0, 0, name_str)
            if maxx > len_name + len_size:
                self._window.insstr(0, maxx - len_size, size_str)
            elif maxy - 1 > len_size:
                for i in range(1, len_size + 1):
                    self._window.insch(maxy - i, 0, ord(size_str[len_size - i]))
        elif len_name <= maxy:
            s = name_str
            if maxx - 1 > len_size:
                self._window.insstr(0, maxx - len_size - 1, size_str)
            elif maxy > len_name + len_size:
                s += " " * (maxy - len_name - len_size) + size_str
            for i in range(len(s)):
                self._window.insch(i, 0, ord(s[i]))
        elif maxx >= maxy:
            self._window.insstr(0, 0, name_str)
        else:
            for i in range(maxy):
                self._window.insch(i, 0, ord(name_str[i]))

    def get_path(self, y, x):
        if not self.contains_point(y, x):
            return None
        for f in self._files:
            p = f.get_path(y, x)
            if p:
                return [self] + p
        return [self]


class fsvParentDirectory(fsvDirectory):
    frame_size = (1, 0)

    def __init__(self, name, size=0):
        fsvDirectory.__init__(self, name, size)

    def name(self):
        return os.path.realpath(self._name) + os.path.sep

    def window(self):
        return self._window

    def write_name(self):
        name_str = self.name()
        len_name = len(name_str)
        size_str = self.get_size_string()
        len_size = len(size_str)
        maxy, maxx = self._window.getmaxyx()
        if maxx > len_name + len_size:
            self._window.insstr(
                0, 0, name_str + " " * (maxx - len_name - len_size) + size_str
            )
        else:
            self._window.insstr(0, 0, name_str)


class fsvViewer:
    def __init__(self, mainwin, _dir, draw_frame):
        self._mainwin = mainwin
        self._dir = os.path.realpath(_dir)
        if not curses.has_colors():
            raise fsvError(
                "This program needs colors but curses cannot initialize "
                + "them. Fix this problem and try again."
            )
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_BLACK)
        self._draw_frame = draw_frame
        self._msgwin = self._mainwin.derwin(
            1, self._mainwin.getmaxyx()[1], self._mainwin.getmaxyx()[0] - 1, 0
        )
        # self._msgwin.leaveok(True)
        r = curses.mousemask(
            curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED | curses.BUTTON1_PRESSED
        )

        self.load_dir(self._dir)
        while not self._parent_dir:
            ch = self._mainwin.getch()
            if ch < 256:
                ch = chr(ch)
                if ch in "qQ":
                    return
                elif ch in "rR":
                    self.load_dir(self._dir)
        self.write_path()
        self.set_cursor(0, 0)
        while True:
            ch = self._mainwin.getch()
            if ch == ord("q"):
                break
            elif ch == ord("f"):
                self._mainwin.clear()
                self._draw_frame = not self._draw_frame
                self._parent_dir.calculate_content(0, self._draw_frame)
                self.set_cursor(0, 0)
                self._mainwin.refresh()
            elif ch == ord("r"):
                self.load_dir(self._dir)
                while not self._parent_dir:
                    ch = self._mainwin.getch()
                    if ch < 256:
                        ch = chr(ch)
                        if ch in "qQ":
                            return
                        elif ch in "rR":
                            self.load_dir(self._dir)
                self._selected_path = [self._parent_dir]
                self._path_index = 0
                self.set_cursor(0, 0)
                self.write_path()
            elif ch == ord("d"):
                if self._path_index > 0:
                    self._path_index -= 1
                    self.write_path()
            elif ch == ord("e"):
                if self._path_index < len(self._selected_path) - 1:
                    self._path_index += 1
                    self.write_path()
            elif ch == curses.KEY_UP or ch == ord("k"):
                y, x = self._mainwin.getyx()
                if y > 0:
                    self.set_cursor(y - 1, x)
            elif ch == curses.KEY_DOWN or ch == ord("j"):
                y, x = self._mainwin.getyx()
                if y + 1 < self._mainwin.getmaxyx()[0] - 1:
                    self.set_cursor(y + 1, x)
            elif ch == curses.KEY_LEFT or ch == ord("h"):
                y, x = self._mainwin.getyx()
                if x > 0:
                    self.set_cursor(y, x - 1)
            elif ch == curses.KEY_RIGHT or ch == ord("l"):
                y, x = self._mainwin.getyx()
                if x + 1 < self._mainwin.getmaxyx()[1]:
                    self.set_cursor(y, x + 1)
            elif ch == curses.KEY_MOUSE:
                id, x, y, z, state = curses.getmouse()
                if y < self._mainwin.getmaxyx()[0] - 1:
                    self.set_cursor(y, x)

    def load_dir(self, d):
        self._parent_dir = None
        self._msgwin.clear()
        self._mainwin.clear()
        if not os.path.isdir(d):
            self._msgwin.insstr(0, 0, "The directory %s does not exist." % d)
            self._msgwin.refresh()
            return
        os.chdir(d)
        self._msgwin.addstr(0, 0, "please wait while the sizes are calculated...")
        self._msgwin.refresh()
        with subprocess.Popen(
            DU_COMMAND.split(), stdout=subprocess.PIPE, close_fds=True, text=True
        ) as du:
            self._parent_dir = self.create_tree(du.stdout, d)
        maxyx = self._mainwin.getmaxyx()
        win = self._mainwin.derwin(maxyx[0] - 1, maxyx[1], 0, 0)
        win.bkgdset(" ", curses.color_pair(0))
        self._parent_dir.set_window(win)
        self._parent_dir.calculate_content(0, self._draw_frame)
        self._msgwin.clear()
        self._msgwin.refresh()
        self._mainwin.refresh()
        self._selected_path = [self._parent_dir]
        self._path_index = 0

    def set_cursor(self, y, x):
        new_selected_path = self._parent_dir.get_path(y, x)
        if self._selected_path == new_selected_path:
            self._mainwin.move(y, x)
            return
        self._selected_path = new_selected_path
        if not self._selected_path:
            return
        self._path_index = len(self._selected_path) - 1
        self.write_path()
        self._mainwin.move(y, x)

    def write_path(self):
        if not self._selected_path:
            return
        self._msgwin.clear()
        self._msgwin.move(0, 0)
        size_str = self._selected_path[self._path_index].get_size_string()
        width = self._msgwin.getmaxyx()[1] - 2 - len(size_str)
        self._msgwin.attrset(curses.color_pair(0))
        for i in range(self._path_index, -1, -1):
            s = self._selected_path[i].name()
            if width - len(s) > 3 or (i == 0 and width - len(s) > -1):
                self._msgwin.insstr(s)
                width -= len(s)
            elif i == self._path_index:
                self._msgwin.insstr("..." + s[-width + 3 :])
                width = 0
                break
            else:
                self._msgwin.insstr(".../")
                break
        self._msgwin.attrset(curses.color_pair(8) | curses.A_BOLD)
        self._msgwin.move(0, self._msgwin.getmaxyx()[1] - 2 - len(size_str) - width)
        for i in range(self._path_index + 1, len(self._selected_path)):
            s = self._selected_path[i].name()
            if width >= len(s):
                self._msgwin.addstr(self._selected_path[i].name())
                width -= len(s)
            else:
                break
        self._msgwin.attrset(curses.color_pair(0))
        self._msgwin.addstr(0, self._msgwin.getmaxyx()[1] - len(size_str) - 1, size_str)
        self._msgwin.refresh()

    def create_tree(self, sizefile, directory):
        current_dirs = [fsvParentDirectory(directory, 0)]
        last_path = ["."]
        for line in sizefile:
            p = line.find("\t")
            size = int(line[:p]) * BLOCKSIZE
            path = line[p:].strip()
            path = path.split(os.path.sep)
            len_path = len(path)
            for i in range(max(len_path, len(last_path))):
                if i >= len_path:
                    for j in range(len(current_dirs) - 2, i - 2, -1):
                        current_dirs[j].add_file(current_dirs[j + 1])
                        current_dirs[j + 1].setup()
                    current_dirs = current_dirs[:i]
                    break
                if i >= len(last_path) or last_path[i] != path[i]:
                    for j in range(len(current_dirs) - 2, i - 2, -1):
                        current_dirs[j].add_file(current_dirs[j + 1])
                        current_dirs[j + 1].setup()
                    current_dirs = current_dirs[:i]
                    for j in range(i, len_path - 1):
                        current_dirs.append(fsvDirectory(path[j], 0))
                    current_dirs[-1].add_file(fsvFile(path[len_path - 1], size))
                    break
            last_path = path
        current_dirs[0].setup()
        return current_dirs[0]


parser = optparse.OptionParser(
    usage="usage: %prog [options] <directory>", version="%proc 0.9"
)
parser.add_option(
    "-f",
    "--draw-frame",
    action="store_true",
    dest="draw_frames",
    default=True,
    help="draw frames to indicate directories",
)
parser.add_option(
    "-n",
    "--draw-no-frames",
    action="store_false",
    dest="draw_frames",
    help="draw no frames to around directories",
)


def main():
    options, args = parser.parse_args()

    if len(args) > 1:
        parser.print_usage()
        sys.exit(1)

    directory = args[0] if args else os.getcwd()

    if not os.path.isdir(directory):
        print("invalid directory:", directory)
        sys.exit(1)

    try:
        curses.wrapper(fsvViewer, directory, options.draw_frames)
    except KeyboardInterrupt:
        return
    except fsvError as e:
        print(e)
        sys.exit(2)


if __name__ == "__main__":
    main()
