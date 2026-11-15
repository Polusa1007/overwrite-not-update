#!/usr/bin/env python3
"""Paper C, C7: two workloads that update data existing before the tool runs (prereg/C7.md). Runs in the guest.

    c7_wl.py prep|run dbupd|logapp DIR

dbupd   prep: SQLite database DIR/db.sqlite with 200000 rows (the row generator of the C1 sqlite tool, seed 1).
        run:  400 transactions of 250 updates of random existing rows (seed 2), default rollback journal.
logapp  prep: 2000 text files DIR/mNNNN of 8-32 KiB (seed 1).
        run:  20000 appends of 0.5-8 KiB of text to random existing files, each followed by fsync (seed 2)."""
import os
import random
import sqlite3
import sys

mode, tool, root = sys.argv[1:4]
words = open("/usr/share/dict/words").read().split() if os.path.exists("/usr/share/dict/words") \
    else [str(i) for i in range(50000)]


def text(rng, n):
    return " ".join(rng.choice(words) for _ in range(n))


def lines(rng, nbytes):
    out, size = [], 0
    while size < nbytes:
        s = text(rng, 12) + "\n"
        out.append(s)
        size += len(s)
    return "".join(out)[:nbytes]


if tool == "dbupd":
    p = os.path.join(root, "db.sqlite")
    if mode == "prep":
        os.makedirs(root, exist_ok=True)
        rng = random.Random(1)
        db = sqlite3.connect(p)
        c = db.cursor()
        c.execute("create table t(id integer primary key, k text, v text)")
        for b in range(200):
            c.executemany("insert into t(k, v) values (?, ?)", [(str(rng.random()), text(rng, 60)) for _ in range(1000)])
            db.commit()
        db.close()
    else:
        rng = random.Random(2)
        db = sqlite3.connect(p)
        c = db.cursor()
        for b in range(400):
            for _ in range(250):
                c.execute("update t set v = ? where id = ?", (text(rng, 60), rng.randint(1, 200000)))
            db.commit()
        db.close()
elif tool == "logapp":
    if mode == "prep":
        os.makedirs(root, exist_ok=True)
        rng = random.Random(1)
        for i in range(2000):
            with open(os.path.join(root, f"m{i:04d}"), "w") as f:
                f.write(lines(rng, rng.randint(8192, 32768)))
    else:
        rng = random.Random(2)
        for _ in range(20000):
            i = rng.randrange(2000)
            with open(os.path.join(root, f"m{i:04d}"), "a") as f:
                f.write(lines(rng, rng.randint(512, 8192)))
                f.flush()
                os.fsync(f.fileno())
else:
    sys.exit(f"unknown tool {tool}")
