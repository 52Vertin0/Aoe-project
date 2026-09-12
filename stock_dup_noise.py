# -*- coding: utf-8 -*-
"""历史批次内/批间的"同群重复仓库"噪声标尺（2026-09-20）
用 8 局为一组（与历史 verify.sh 的批次规模一致）统计重复率，看批间波动幅度。
"""
import re, os, glob, math
from collections import defaultdict

RE = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .*?at=\((\d+),(\d+)\)")


def stocks_of(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if "[BUILD-ISSUE" not in line or "type=3 " not in line:
                continue
            m = RE.search(line)
            if m:
                out.append((int(m.group(1)), int(m.group(4)), int(m.group(5))))
    return out


def dup_flag(st, thr=9.0):
    for i in range(len(st)):
        for j in range(i + 1, len(st)):
            if math.hypot(st[i][1] - st[j][1], st[i][2] - st[j][2]) <= thr:
                return True
    return False


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(here, "*.ait")))
    groups = defaultdict(list)
    for fp in files:
        n = os.path.basename(fp)
        if n.startswith("fu"):
            continue
        stem = n[:-4] if n.lower().endswith(".ait") else n
        if "_" in stem:
            g = stem.split("_")[0]
        else:
            g = stem.rstrip("0123456789") or "x"
        groups[g].append(fp)
    print("=" * 88)
    print("【历史批间噪声标尺】按 8 局为一批（与 verify.sh 同规模），重复率 = 出现『同群<=9格』的局数/批内局数")
    print(f"  {'批':<10}{'局数':>5}{'有仓库令':>9}{'同群重复':>9}{'重复率':>9}")
    rates = []
    # 按文件名数字切成 8 局一批
    for g in sorted(groups):
        fs = sorted(groups[g], key=lambda p: (len(p), p))
        for k in range(0, len(fs), 8):
            chunk = fs[k:k + 8]
            if len(chunk) < 8:
                continue
            n_stock = dup = 0
            for fp in chunk:
                st = stocks_of(fp)
                if st:
                    n_stock += 1
                    if dup_flag(st):
                        dup += 1
            if n_stock == 0:
                continue
            r = dup / 8.0
            rates.append(r)
            print(f"  {g+str(k//8+1):<10}{8:>5}{n_stock:>9}{dup:>9}{r*100:>8.1f}%")
    if rates:
        import statistics
        print(f"\n  批数={len(rates)}  均值={statistics.mean(rates)*100:.1f}%  中位={statistics.median(rates)*100:.1f}%  "
              f"最小={min(rates)*100:.1f}%  最大={max(rates)*100:.1f}%  标准差={statistics.pstdev(rates)*100:.1f}pp")


if __name__ == "__main__":
    main()
