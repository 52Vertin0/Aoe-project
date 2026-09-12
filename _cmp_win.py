# -*- coding: utf-8 -*-
"""当前版(f425fcb1) vs 之前版本 胜率对比 + 分地图 + 确定性提示。"""
import io, os, re, json
from math import comb

def jsonl_win(tag):
    fn = tag + '.jsonl'
    if not os.path.exists(fn):
        return False
    for line in io.open(fn, encoding='utf-8', errors='ignore'):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get('win'):
            return True
    return False

def ait_defeated(tag):
    fn = tag + '.ait'
    if not os.path.exists(fn):
        return False
    for line in io.open(fn, encoding='utf-8', errors='ignore'):
        p = line.split(' | ', 3)
        if len(p) < 4:
            continue
        if re.search(r'DEFEAT: [A-Za-z ]+', p[3]):
            return True
    return False

def judge(tag):
    w = jsonl_win(tag)
    d = ait_defeated(tag)
    if w:
        return 'W'
    if d:
        return 'L'
    return 'U'

def count(tags):
    W = L = U = 0
    detail = []
    for t in tags:
        if not os.path.exists(t + '.ait'):
            continue
        r = judge(t)
        detail.append((t, r))
        if r == 'W': W += 1
        elif r == 'L': L += 1
        else: U += 1
    return W, L, U, detail

def fisher(w1, n1, w2, n2):
    # two-sided exact via hypergeometric tail (approx by summing <= observed prob ratio)
    try:
        from math import comb
    except Exception:
        return None
    N = n1 + n2
    K = w1 + w2
    if K > N: return None
    def p(k):
        return comb(n1, k) * comb(n2, K - k) / comb(N, K) if 0 <= k <= n1 and 0 <= K - k <= n2 else 0.0
    obs = p(w1)
    if obs == 0: return None
    s = 0.0
    for k in range(0, min(n1, K) + 1):
        pk = p(k)
        if pk <= obs + 1e-15:
            s += pk
    return min(1.0, s)

# ===== 批次定义（地图来自 fw1_verify.sh / fw2_ab.sh / cy1_verify.sh）=====
batches = {
  'fw1  (f425fcb1 当前 地图*4×2)': (
      ['fw101','fw102','fw103','fw104'], ['fw105','fw106','fw107','fw108']),
  'gd1  (f425fcb1 当前 地图*4×2)': (
      ['gd101','gd102','gd103','gd104'], ['gd105','gd106','gd107','gd108']),
  'bl1  (blanket a2b5f9ed 确定性复测)': (
      ['bl101'], ['bl105']),
  'cy1  (金丝雀 f67fd89e 前农民波)': (
      ['cy101','cy102'], ['cy103','cy104']),
  'h2xx (现行 58143847 疑=map2)': (
      ['h2%02d' % i for i in range(1, 25)], []),
  'h3xx (现行 58143847 疑=map3)': (
      [], ['h3%02d' % i for i in range(1, 25)]),
}
# h2xx/h3xx 用 %02d 占位，需展开
expanded = {}
for name,(m2,m3) in batches.items():
    e2=[t%i if '%' in t else t for t in m2 for i in ([0] if '%' not in t else range(1,25))]
    e3=[t%i if '%' in t else t for t in m3 for i in ([0] if '%' not in t else range(1,25))]
    expanded[name]=(e2,e3)

print("="*70)
print("当前版 f425fcb1 (fw1+gd1 合并) vs 之前版本 —— 分地图胜率")
print("="*70)
all_m2_cur=[]; all_m3_cur=[]
for name,(m2,m3) in expanded.items():
    W2,L2,U2,_ = count(m2); W3,L3,U3,_ = count(m3)
    n2,m2n=W2+L2+U2,len(m2); n3,m3n=W3+L3+U3,len(m3)
    def pct(w,n): return ("%.1f%%"%(100.0*w/n)) if n else "n=0"
    print("%-34s map2: %2d/%2d=%s  | map3: %2d/%2d=%s" % (
        name, W2,n2,pct(W2,n2), W3,n3,pct(W3,n3)))
    if name.startswith('fw1') or name.startswith('gd1'):
        all_m2_cur+=m2; all_m3_cur+=m3

# 当前合并
W2,L2,U2,_=count(all_m2_cur); W3,L3,U3,_=count(all_m3_cur)
n2=W2+L2+U2; n3=W3+L3+U3
print("-"*70)
print(">>> 当前 f425fcb1 合并: map2 %d/%d=%.1f%%   map3 %d/%d=%.1f%%   (总 %d/%d=%.1f%%)" % (
    W2,n2,100.0*W2/n2 if n2 else 0, W3,n3,100.0*W3/n3 if n3 else 0,
    W2+W3, n2+n3, 100.0*(W2+W3)/(n2+n3) if (n2+n3) else 0))

# 之前版本记录（§AN.5，已 Fisher 验证，n=24/map）
print("-"*70)
print("之前版本(记录值, n=24/map):")
print("  现行 58143847 : map2 18/24=75.0%%  map3 16/24=66.7%%  总 34/48=70.8%%")
print("  基线 774348fe : map2 25/36=69.4%%  map3 12/24=50.0%%")
print("  方案2 4b33881a: map2 17/24=70.8%%  map3  9/24=37.5%%")

# Fisher: 当前合并 vs 现行  (n 小，仅参考)
print("-"*70)
p2 = fisher(W2, n2, 18, 24)
p3 = fisher(W3, n3, 16, 24)
print("Fisher(当前 map2 %d/%d vs 现行 18/24): p=%s  (n=8<<24，仅供参考)" % (W2,n2, ("%.3f"%p2) if p2 is not None else "NA"))
print("Fisher(当前 map3 %d/%d vs 现行 16/24): p=%s  (n=8<<24，仅供参考)" % (W3,n3, ("%.3f"%p3) if p3 is not None else "NA"))
print("\n⚠ 铁律81: 单批<24 局/臂不得下胜负结论；且已证同配置同 exe 复跑会 W↔L 翻转。")
