# -*- coding: utf-8 -*-
"""
[SIEGE-WAIT] 闸链探针 + 感化武器厂起手/胜负统计。

用法:
    python siewgate_probe.py show <ait...>     # 逐局明细
    python siewgate_probe.py scan <glob>       # 跨批汇总

关注量:
    [SIEGE-WAIT] = 祭司已进 PRIEST_CONVERT_SIEGE_RANGE(12) 格内、但塔闸不通过 ⇒ 本帧 return（不发感化令）
      字段: f=帧 hp=祭司血量比 towers=视野内敌箭塔数 seen=视野内敌建筑数 alive=敌活兵数 dS=距武器厂格 lim=当前放行上限

判据（2026-09-21 放宽阈值 0 → 2 的验收）:
    ① 闸真在拦   : dS<=12 的 SIEGE-WAIT 条数 > 0
    ② 闸未被禁死 : SIEGE-WAIT 里 towers > lim 的条数 > 0（>2 座塔时仍拦）
    ③ 起手真发生 : `设置转换目标为 攻城武器厂` 令条数 > 0（这是产物量，不是日志量）
    ④ 门槛生效   : towers<=2 的时刻【不再出现】在 SIEGE-WAIT 里
"""
import sys, re, glob, os

RE_WAIT = re.compile(r'\[SIEGE-WAIT f=(\d+)\] hp=([\d.]+) towers=(\d+) seen=(\d+) alive=(\d+) dS=([\d.]+)'
                     r'(?: lim=(\d+))?')
RE_CONV = re.compile(r'HumanAction:祭司\s+(\d+)\s+设置转换目标为\s+(\S+)\s+(\d+)')
SIEGE_NAME = '攻城武器厂'
RE_WIN = re.compile(r'!!\s*VICTORY!')
RE_LOSE = re.compile(r'!!\s*DEFEAT:')

SORT = {5: '弓兵', 8: '投石车', 10: '方阵兵', 11: '战车', 12: '战车弓兵',
        14: '复合弓兵', 13: '阔剑兵', 6: '骑兵', 15: '刀斧兵'}


def parse(path):
    waits, convs, win, lose = [], [], False, False
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.split(' | ', 3)
        if len(p) < 4:
            continue
        msg = p[3]
        m = RE_WAIT.search(msg)
        if m:
            waits.append(dict(fr=int(m.group(1)), hp=float(m.group(2)), towers=int(m.group(3)),
                              seen=int(m.group(4)), alive=int(m.group(5)), ds=float(m.group(6)),
                              lim=(int(m.group(7)) if m.group(7) else None)))
        c = RE_CONV.search(msg)
        if c:
            convs.append(dict(fr=None, priest=int(c.group(1)), tgt=c.group(2), tsn=int(c.group(3)),
                              raw=int(p[1]) if p[1].isdigit() else None))
        if RE_WIN.search(msg):
            win = True
        if RE_LOSE.search(msg):
            lose = True
    return dict(waits=waits, convs=convs, win=win, lose=lose)


def hist(vals):
    h = {}
    for v in vals:
        k = v if v <= 4 else 5
        h[k] = h.get(k, 0) + 1
    return h


def fmt_hist(h):
    return "  ".join(("%d%s=%d" % (k, "+" if k == 5 else "", h[k])) for k in sorted(h)) or "(空)"


def show(paths):
    print("=" * 78)
    print(" [SIEGE-WAIT] = 祭司已进 12 格内、但塔闸不通过 => 本帧 return（不发感化令）")
    print("=" * 78)
    tot_w, n_conv_game, n_conv, n_win, n_lose = [], 0, 0, 0, 0
    for path in paths:
        r = parse(path)
        base = os.path.basename(path).replace('.ait', '')
        sw = r['waits']
        ws = [c for c in r['convs'] if c['tgt'] == SIEGE_NAME]
        res = 'WIN' if r['win'] else ('LOSE' if r['lose'] else '-')
        if r['win']:
            n_win += 1
        if r['lose']:
            n_lose += 1
        if ws:
            n_conv_game += 1
        n_conv += len(ws)
        tot_w += sw
        line = "%-20s %-4s 感化厂令=%-3d" % (base, res, len(ws))
        if sw:
            line += " SIEGE-WAIT n=%-4d 帧[%d..%d] towers{%s}" % (
                len(sw), sw[0]['fr'], sw[-1]['fr'], fmt_hist(hist([x['towers'] for x in sw])))
            lims = sorted(set(x['lim'] for x in sw if x['lim'] is not None))
            if lims:
                line += " lim=%s" % lims
        else:
            line += " SIEGE-WAIT 0"
        if ws:
            line += " | 起手帧=%s" % [x['raw'] for x in ws]
        print(line)
    print("-" * 78)
    print("【汇总】局数=%d  胜=%d 负=%d  有起手局=%d  感化厂令总数=%d  SIEGE-WAIT 总条数=%d"
          % (len(paths), n_win, n_lose, n_conv_game, n_conv, len(tot_w)))
    if not tot_w:
        print("★ SIEGE-WAIT 一条都没有 ⇒ 须确认是『祭司已能起手（闸放开）』还是『祭司根本没走到 12 格』；")
        print("  用起手帧交叉验证：有起手帧 ⇒ 闸放开；无起手帧 ⇒ 瓶颈在上游门外（见 SKILL §2.12）。")
        return
    reach = [x for x in tot_w if x['ds'] <= 12.0]
    print("-" * 78)
    print("★ 判据① 闸真在拦（dS<=12 却被拒）: %d 条" % len(reach))
    if not reach:
        print("★ 判据② 无 dS<=12 样本 ⇒ SIEGE-WAIT 全发生在 12 格外，瓶颈不在本闸。")
        return
    print("★ 判据② 可达样本 towers 分布 : %s" % fmt_hist(hist([x['towers'] for x in reach])))
    lims = sorted(set(x['lim'] for x in reach if x['lim'] is not None))
    if not lims:
        print("     日志未打印 lim ⇒ 旧版二进制，按 0 解释")
    cur = min(lims) if lims else 0
    print("     本批自报放行上限 lim = %s（判据③ 以此为准）" % (lims if lims else [0]))
    for lim in (0, 1, 2, 3):
        c = sum(1 for x in reach if x['towers'] <= lim)
        print("     放宽到 towers<=%d => 可放行 %d 条 (%.0f%%)%s"
              % (lim, c, 100.0 * c / len(reach), "   <== 本批阈值" if lim == cur else ""))
    above = sum(1 for x in reach if x['towers'] > cur)
    le = sum(1 for x in reach if x['towers'] <= cur)
    print("-" * 78)
    if cur == 0 and le == 0:
        print("★ 判据④ lim=0 且可达样本里 towers==0 出现 0 次 => 旧闸【结构性死锁】（塔会重建，归零不可达）")
    if cur == 0:
        print("★ 判据⑤ 达标（未放宽）: towers>0 被拦 %d/%d" % (above, len(reach)))
    else:
        print("★ 判据⑤ 闸未被禁死 : towers>lim(%d) 仍被拦 %d 条" % (cur, above))
        if le:
            print("  ⚠ 违规：lim=%d 却有 %d 条 towers<=%d 仍被拦 => 阈值未生效或另有闸在拦" % (cur, le, cur))
        else:
            print("  ✅ 合规：towers<=%d 一条都没出现在 SIEGE-WAIT 里 => 阈值已生效" % cur)
    al = sum(1 for x in reach if x['alive'] == 0)
    print("★ 判据⑥ 可达样本中 alive==0（敌军全灭）: %d/%d => 用户口径『箭塔拆完=军队已全灭』的成立度"
          % (al, len(reach)))


def summary(pattern):
    paths = sorted(glob.glob(pattern))
    if paths:
        show(paths)
    else:
        print("no files: %s" % pattern)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    mode = sys.argv[1]
    if mode == 'show':
        show([a for a in sys.argv[2:] if a.endswith('.ait')])
    elif mode == 'scan':
        summary(sys.argv[2])
    else:
        print(__doc__)
