"""Fail-closed metadata-only tree census; never skip vanished rename targets."""
import os
import stat
from pathlib import Path

ATTEMPTS=8

def census(root):
    """One lstat per visited path; ENOENT restarts WHOLE census, max8.

    No partial sum is returned. Other I/O errors propagate. Symlinks and special
    files are refused rather than followed/ignored; these intake directories are
    regular files/directories. No source file is opened. Caller owns deadline.
    """
    root=Path(root)
    for attempt in range(ATTEMPTS):
        total=0;todo=[root]
        try:
            while todo:
                path=todo.pop();s=path.stat(follow_symlinks=False)
                if stat.S_ISREG(s.st_mode):total+=s.st_size
                elif stat.S_ISDIR(s.st_mode):
                    with os.scandir(path) as entries:
                        todo.extend(Path(e.path) for e in entries)
                else:raise ValueError('census_requires_regular_files_directories_no_symlinks')
            return total
        except FileNotFoundError:
            # Includes directory disappearance between stat and scandir. A new
            # complete scan must discover the final renamed file and its bytes.
            if attempt+1==ATTEMPTS:raise ValueError('census_persistent_ENOENT_after8_full_attempts') from None
    raise AssertionError('unreachable_census')
