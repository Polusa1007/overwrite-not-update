#!/usr/bin/env python3
"""Paper C, C2: age a mounted file system by repeated random creation and deletion of files.

    churn_age.py MNT SRC SEED [HIGH LOW ROUNDS]

Files are copied from SRC into MNT/aged<round>/ in random order until HIGH of the capacity is used, then randomly
chosen aged files are deleted until LOW is used; ROUNDS times. The last deletion leaves the file system at LOW.
No TRIM is issued here. Standard library only, since it runs in the guest."""
import os
import random
import shutil
import sys


def used(mnt):
    st = os.statvfs(mnt)
    return 1.0 - st.f_bavail / st.f_blocks


def regular_files(src):
    out = []
    for d, _, names in os.walk(src):
        for name in names:
            p = os.path.join(d, name)
            if os.path.isfile(p) and not os.path.islink(p):
                out.append(p)
    return sorted(out)


def main():
    mnt, src, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    high, low, rounds = (float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (0.70, 0.45, 5)
    rng = random.Random(seed)
    files = regular_files(src)
    made = []
    serial = 0
    for r in range(rounds):
        folder = os.path.join(mnt, f"aged{r}")
        os.makedirs(folder, exist_ok=True)
        while used(mnt) < high:
            if serial % 200 == 0:
                os.sync()
            p = rng.choice(files)
            sub = os.path.join(folder, f"{serial // 500:04d}")
            os.makedirs(sub, exist_ok=True)
            dst = os.path.join(sub, f"f{serial:07d}")
            try:
                shutil.copyfile(p, dst)
            except OSError:
                break
            made.append(dst)
            serial += 1
        os.sync()
        rng.shuffle(made)
        while made and used(mnt) > low:
            for _ in range(min(200, len(made))):
                os.unlink(made.pop())
            os.sync()
        print(f"round {r}: used {used(mnt):.3f}, live aged files {len(made)}", flush=True)
    os.sync()


if __name__ == "__main__":
    main()
