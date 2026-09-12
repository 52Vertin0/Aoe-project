# -*- coding: utf-8 -*-
"""
bow_tower_probe.py — 复合弓兵攻塔行为探针（2026-09-18）

回答的问题：为什么复合弓兵不站在最大射程打箭塔，而是走近后被射杀？

数据源：*.ait（引擎动作日志，不受采样影响）
提取链路：
  1. [TOWER-TGT] 事件 = AI 首次把某塔选为目标（attackBuildingOrMarch 下发 HumanAction）
  2. 该 SN 的死亡帧
  3. 箭塔对该 SN 的首次开火帧（塔先手 vs AI 先选）
  4. 选塔之后该 SN 是否还收到过 HumanMove / [KIT-R]（撤退令）——验证"打塔=站桩"
输出：分兵种统计 + 逐样本明细
"""
import glob, os, re, sys, statistics
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
MIN_MTIME = datetime(2026, 9, 16).timestamp()   # TOWER-TGT 逻辑 09-16 才加入

RE_TOWERTGT = re.compile(r'\[TOWER-TGT f=(\d+)\]\s*(\S+)\s*SN=(\d+)\s*攻击最近敌塔\s*(\d+)')
RE_DEATH    = re.compile(r'([\u4e00-\u9fa5]+)\(编号:?(\d+)\)死亡')
RE_MOVE     = re.compile(r'HumanMove:([\u4e00-\u9fa5]+)\s+(\d+)\s+移动至\s+\(([\d.]+),([\d.]+)\)')
RE_MYATK    = re.compile(r'HumanAction:([\u4e00-\u9fa5]+)\s+(\d+)\s+设置攻击目标为\s+([\u4e00-\u9fa5]+)\s+(\d+)')
RE_TOWERFIRE= re.compile(r'HumanAction:箭塔\s+(\d+)\s+设置攻击目标为\s+([\u4e00-\u9fa5]+)\s+(\d+)')
RE_KITR     = re.compile(r'\[KIT-R f=(\d+)\]\s*SN=(\d+)')
RE_KITS     = re.compile(r'\[KIT-S f=(\d+)\]\s*SN=(\d+)')

def parse_line(line):
    """→ (frame, color, message) 或 None"""
    parts = line.split(' | ', 3)
    if len(parts) < 4:
        return None
    try:
        fr = int(parts[1])
    except ValueError:
        return None
    return fr, parts[2], parts[3].rstrip('\n')

def analyze(path):
    """返回该文件的样本列表"""
    turrets = {}        # 首次选塔: sn -> (frame, towerSN, who)
    deaths = {}         # sn -> frame
    moves = {}          # sn -> [frame, ...]
    kitr = {}           # sn -> [frame, ...]
    kits = {}           # sn -> [frame, ...]
    towerfire = {}      # (towerSN, victimSN) -> frame
    myatk = {}          # sn -> [(frame, targetSN)]
    tower_seen = {}     # towerSN -> first frame mentioned anywhere

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                r = parse_line(line)
                if not r:
                    continue
                fr, color, msg = r

                m = RE_TOWERTGT.search(msg)
                if m:
                    sn = int(m.group(3))
                    if sn not in turrets:
                        turrets[sn] = (fr, int(m.group(4)), m.group(2))
                    continue
                m = RE_DEATH.search(msg)
                if m:
                    sn = int(m.group(2))
                    if sn not in deaths:
                        deaths[sn] = fr
                    continue
                m = RE_TOWERFIRE.search(msg)
                if m:
                    key = (int(m.group(1)), int(m.group(3)))
                    if key not in towerfire:
                        towerfire[key] = fr
                    continue
                m = RE_MOVE.search(msg)
                if m:
                    moves.setdefault(int(m.group(2)), []).append(fr)
                    continue
                m = RE_MYATK.search(msg)
                if m:
                    myatk.setdefault(int(m.group(2)), []).append((fr, int(m.group(4)), m.group(3)))
                    continue
                m = RE_KITR.search(msg)
                if m:
                    kitr.setdefault(int(m.group(2)), []).append(fr)
                    continue
                m = RE_KITS.search(msg)
                if m:
                    kits.setdefault(int(m.group(2)), []).append(fr)
                    continue
    except Exception as e:
        print("ERR", path, e, file=sys.stderr)
        return []

    out = []
    for sn, (fr0, towerSN, who) in turrets.items():
        d = deaths.get(sn)
        mv = [x for x in moves.get(sn, []) if x > fr0]
        kr = [x for x in kitr.get(sn, []) if x > fr0]
        ks = [x for x in kits.get(sn, []) if x > fr0]
        # 塔对该单位的首次开火
        tf = towerfire.get((towerSN, sn))
        # 该单位对外的攻击令中，首次切到塔 SN 的帧
        atk_tower = None
        for (af, tsn, tname) in myatk.get(sn, []):
            if tsn == towerSN:
                atk_tower = af
                break
        out.append(dict(f=os.path.basename(path), sn=sn, who=who, tower=towerSN,
                        fr_select=fr0, fr_towerfire=tf, fr_myatk=atk_tower, fr_death=d,
                        n_move_after=len(mv), n_kitr_after=len(kr), n_kits_after=len(ks),
                        first_move_after=(mv[0] if mv else None),
                        last_move_after=(mv[-1] if mv else None)))
    return out


def main():
    files = sorted(glob.glob(os.path.join(ROOT, '*.ait')))
    files = [f for f in files if os.path.getmtime(f) >= MIN_MTIME]
    print("扫描 %d 个 .ait（mtime >= 2026-09-16）" % len(files))
    alls = []
    for f in files:
        alls += analyze(f)

    if not alls:
        print("无样本"); return

    # ---------- 汇总 ----------
    for who in ('复合弓兵/远程', '近战'):
        s = [x for x in alls if x['who'] == who]
        if not s:
            continue
        print("\n" + "=" * 78)
        print("【%s】样本 %d 条，覆盖 %d 局" % (who, len(s), len(set(x['f'] for x in s))))
        died = [x for x in s if x['fr_death']]
        print("  打到死(有死亡记录) %d 条 (%.0f%%)；存活至局末 %d 条"
              % (len(died), 100.0 * len(died) / len(s), len(s) - len(died)))
        if died:
            life = [x['fr_death'] - x['fr_select'] for x in died]
            print("  从「AI选塔」到「死亡」帧数：中位 %.0f (≈%.1f秒)  均值 %.0f  min %d  max %d"
                  % (statistics.median(life), statistics.median(life) / 25.0,
                     statistics.mean(life), min(life), max(life)))
            print("    → 存活 ≤2秒 %d 条 (%.0f%%)；≤5秒 %d 条 (%.0f%%)；≤10秒 %d 条 (%.0f%%)"
                  % (sum(1 for x in life if x <= 50), 100.0 * sum(1 for x in life if x <= 50) / len(life),
                     sum(1 for x in life if x <= 125), 100.0 * sum(1 for x in life if x <= 125) / len(life),
                     sum(1 for x in life if x <= 250), 100.0 * sum(1 for x in life if x <= 250) / len(life)))
        # 塔先手
        both = [x for x in s if x['fr_towerfire'] and x['fr_myatk']]
        if both:
            tower_first = sum(1 for x in both if x['fr_towerfire'] < x['fr_myatk'])
            delta = [x['fr_myatk'] - x['fr_towerfire'] for x in both]
            print("  时序（塔首次开火 vs 我方首次攻击令）可比 %d 条：塔先手 %d 条 (%.0f%%)"
                  % (len(both), tower_first, 100.0 * tower_first / len(both)))
            print("    帧差(我方-塔) 中位 %+.0f 帧 (≈%+.1f 秒)，即 AI 平均落后 %.1f 秒才反应过来"
                  % (statistics.median(delta), statistics.median(delta) / 25.0,
                     abs(statistics.median(delta)) / 25.0))
        # 站桩验证
        nomove = sum(1 for x in s if x['n_move_after'] == 0)
        nokitr = sum(1 for x in s if x['n_kitr_after'] == 0)
        print("  选塔后【零移动令】(纯站桩对射) %d 条 (%.0f%%)" % (nomove, 100.0 * nomove / len(s)))
        print("  选塔后【零撤退令 KIT-R】          %d 条 (%.0f%%)" % (nokitr, 100.0 * nokitr / len(s)))
        mv = [x['n_move_after'] for x in s]
        kr = [x['n_kitr_after'] for x in s]
        print("  选塔后移动令条数 中位 %.0f / 均值 %.1f ；撤退令 KIT-R 中位 %.0f / 均值 %.1f"
              % (statistics.median(mv), statistics.mean(mv), statistics.median(kr), statistics.mean(kr)))

    # ---------- 明细 ----------
    print("\n" + "=" * 78)
    print("【明细】复合弓兵样本（前 30 条，按存活帧升序）")
    print("%-10s %-7s %-6s %10s %10s %10s %8s %6s %6s" %
          ("file", "SN", "塔SN", "选塔帧", "塔开火帧", "死亡帧", "存活帧", "move", "kitR"))
    s = [x for x in alls if x['who'] == '复合弓兵/远程']
    s.sort(key=lambda x: (x['fr_death'] - x['fr_select']) if x['fr_death'] else 1e9)
    for x in s[:30]:
        life = (x['fr_death'] - x['fr_select']) if x['fr_death'] else -1
        print("%-10s %-7d %-6d %10d %10s %10s %8s %6d %6d" %
              (x['f'], x['sn'], x['tower'], x['fr_select'],
               x['fr_towerfire'] if x['fr_towerfire'] else '-',
               x['fr_death'] if x['fr_death'] else '-',
               life if life >= 0 else '存活',
               x['n_move_after'], x['n_kitr_after']))

    # ---------- 塔射程内被选中 vs 射程外 ----------
    print("\n【关键】AI 选塔时我方的距离无法从 ait 直接得到，但可由'塔立即开火'反推：")
    s2 = [x for x in alls if x['who'] == '复合弓兵/远程']
    both = [x for x in s2 if x['fr_towerfire'] and x['fr_myatk']]
    near = sum(1 for x in both if x['fr_towerfire'] - x['fr_myatk'] <= 5)
    print("  塔开火帧 ≤ 我方攻击令帧+5 的样本（=选塔时已在塔射程内）: %d / %d (%.0f%%)"
          % (near, len(both), 100.0 * near / len(both) if both else 0))

if __name__ == '__main__':
    main()
