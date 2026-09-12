# -*- coding: utf-8 -*-
"""统计某批：祭司死亡前最后一条感化令的目标类型 + 距死亡帧数。

用法:  python _priest_death.py pp        # 前缀 pp → pp1.ait .. pp24.ait
       python _priest_death.py cur

口径（2026-09-24 修正）:
  1) 判胜: 【任一】jsonl 行 win==true（胜帧后引擎还会再写一帧 win=false，
           只读最后一行会漏判；pp10/13/21 就是这么被漏掉的）。
           AIText 的 "VICTORY! Siege Workshop converted" 仅作交叉验证。
  2) 失败: AIText 含 "DEFEAT:"。
  3) 其余: 打满 45000 帧 = 未决。
"""
import glob, re, io, os, json, sys

TARGET_KINDS = ['攻城武器厂', '战车弓兵', '复合弓兵', '方阵兵', '投石车', '斧头兵',
                '棍棒兵', '弓兵', '投石兵', '骑兵', '战车', '阔剑兵', '刀斧兵',
                'Prof.Lu', '村民']


def kind_of(txt):
    for k in TARGET_KINDS:
        if k in txt:
            return k
    return txt.strip()


def jsonl_win_frame(tag):
    jf = tag + '.jsonl'
    if not os.path.exists(jf):
        return None
    try:
        for ln in io.open(jf, encoding='utf-8', errors='ignore'):
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            if o.get('win') is True:
                return o.get('frame')
    except Exception:
        return None
    return None


def main():
    pre = sys.argv[1] if len(sys.argv) > 1 else 'cur'
    files = sorted(glob.glob(pre + '[0-9]*.ait'),
                   key=lambda s: int(re.search(r'(\d+)', os.path.basename(s)).group(1)))
    if not files:
        print('无匹配文件: %s[0-9]*.ait' % pre)
        return
    print('%-8s %-12s %-9s %-9s %-8s %-9s %s' % ('局', '最后感化目标', '起手帧', '死亡帧', '间隔帧', '死亡阶段', '结局'))
    print('-' * 82)
    W = L = U = 0
    for f in files:
        tag = f[:-4]
        s = io.open(f, encoding='utf-8', errors='ignore').read()
        lines = s.split('\n')
        last_conv, last_conv_fr = None, None
        for ln in lines:
            if '设置转换目标为' in ln:
                m = re.search(r'\|\s*(\d+)\s*\|', ln)
                last_conv, last_conv_fr = ln.split('设置转换目标为', 1)[1].strip(), \
                    (int(m.group(1)) if m else None)
        death_fr = None
        for ln in lines:
            if re.search(r'祭司\(编号[:：]?\s*91166\)死亡', ln) or '祭司(编号91166)死亡' in ln:
                m = re.search(r'\|\s*(\d+)\s*\|', ln)
                death_fr = int(m.group(1)) if m else None
                break
        wf = jsonl_win_frame(tag)
        vic = 'VICTORY' in s
        defeat = 'DEFEAT:' in s
        if wf is not None or vic:
            res = '胜'; W += 1
        elif defeat:
            res = '负'; L += 1
        else:
            res = '未决'; U += 1
        gap = (death_fr - last_conv_fr) if (death_fr and last_conv_fr) else None
        seg = '-'
        if death_fr is not None:
            seg = '防御期' if death_fr < 33001 else '反攻期'
        print('%-8s %-12s %-9s %-9s %-8s %-9s %s' % (
            tag, kind_of(last_conv) if last_conv else '(无)',
            last_conv_fr or '-', death_fr or '-', gap if gap is not None else '-', seg, res))
    print('-' * 82)
    print('n=%d 胜=%d 负=%d 未决=%d 胜率=%.1f%%' % (len(files), W, L, U, 100.0 * W / len(files)))


if __name__ == '__main__':
    main()
