# -*- coding: utf-8 -*-
"""UsrAI.cpp 结构度量：函数长度 / 内部功能段 / 嵌套深度 / 重复代码块 / 注释占比。

用途：为"下一轮优化"提供事实基线（哪些段最大、哪些段重复、哪些段是死代码温床）。
用法：python code_metrics.py [--seg] [--dup] [--nest]
"""
import re, sys, os, collections

SRC = 'UsrAI.cpp'
L = open(SRC, encoding='utf-8').read().split('\n')
N = len(L)

FUNC_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_:<>,&\*\s]*\s+UsrAI::(\w+)\s*\(')

# ---------- 1. 函数边界 ----------
defs = []
for i, ln in enumerate(L):
    m = FUNC_RE.match(ln)
    if m:
        defs.append((i, m.group(1)))

funcs = []
for k, (i, name) in enumerate(defs):
    end = defs[k + 1][0] - 1 if k + 1 < len(defs) else N - 1
    # 去掉尾部空行，让函数真实终点更接近最后一个非空行
    last = end
    while last > i and not L[last].strip():
        last -= 1
    funcs.append(dict(name=name, start=i + 1, end=last + 1, span=end - i + 1, body=last - i + 1))

# ---------- 工具 ----------
def classify(lines):
    blank = code = cmt = 0
    for s in lines:
        t = s.strip()
        if not t:
            blank += 1
        elif t.startswith('//'):
            cmt += 1
        else:
            code += 1
    return blank, code, cmt

def max_nest(lines):
    """按首列花括号 + 缩进估算嵌套深度（4 空格 = 1 层）"""
    mx = 0
    for s in lines:
        if not s.strip() or s.strip().startswith('//'):
            continue
        ind = len(s) - len(s.lstrip(' '))
        mx = max(mx, ind // 4)
    return mx

SEG_PATS = [
    re.compile(r'^\s{0,12}//\s*[=─━\-]{4,}'),                 # 分隔线
    re.compile(r'^\s{0,12}//\s*★'),
    re.compile(r'^\s{0,12}//\s*【'),
    re.compile(r'^\s{0,12}//\s*(?:第\s*[0-9一二三四五六七八九十]+\s*段|Step\s*\d)'),
    re.compile(r'^\s{0,12}//\s*[A-Z]{1,4}[-0-9]+\s*段'),      # D-1 段 / 1.5 段 之类
    re.compile(r'^\s{0,12}//\s*优先级'),
]
def is_seg_title(s):
    return any(p.match(s) for p in SEG_PATS)

# ---------- 2. 输出：函数排行 ----------
def head():
    print('=' * 100)
    print('UsrAI.cpp 结构度量  |  总行=%d  |  函数=%d  |  非函数头部(含 include/#define)=%d 行'
          % (N, len(funcs), defs[0][0] if defs else 0))
    print('=' * 100)

    rows = []
    for f in funcs:
        lines = L[f['start'] - 1:f['end']]
        b, c, m = classify(lines)
        rows.append((f['body'], f['name'], f['start'], f['end'], b, c, m, max_nest(lines)))
    rows.sort(reverse=True)

    tot_body = sum(r[0] for r in rows)
    print('\n%-34s %6s %7s %6s %6s %6s %5s %6s' %
          ('函数', '行数', '起始', '空行', '代码', '注释', '注释%', '嵌套'))
    print('-' * 100)
    for body, name, st, en, b, c, m, nest in rows:
        if body < 5:
            continue
        print('%-34s %6d %7d %6d %6d %6d %5.0f%% %6d' %
              (name, body, st, b, c, m, 100.0 * m / max(1, body), nest))
    print('-' * 100)
    print('%-34s %6d' % ('(以上函数合计)', tot_body))
    small = [r for r in rows if r[0] < 5]
    print('小函数(<5行): %d 个  %s' % (len(small), ' '.join(r[1] for r in small)))

    # 帕累托
    print('\n【帕累托】按行数降序累计占比：')
    acc = 0
    for i, r in enumerate(rows):
        acc += r[0]
        if i < 8:
            print('  #%-2d %-30s %5d 行  累计 %5.1f%%' % (i + 1, r[1], r[0], 100.0 * acc / tot_body))

# ---------- 3. 输出：函数内分段 ----------
def segs():
    print('\n' + '=' * 100)
    print('函数内【功能段】明细（>200 行的函数）')
    print('=' * 100)
    for f in funcs:
        if f['body'] <= 200:
            continue
        lines = L[f['start'] - 1:f['end']]
        marks = []
        for j, s in enumerate(lines):
            if is_seg_title(s):
                marks.append((j, s.strip()[:96]))
        if not marks:
            continue
        print('\n### %s  (L%d~%d, %d 行, 嵌套 %d) —— 识别到 %d 个段标题'
              % (f['name'], f['start'], f['end'], f['body'], max_nest(lines), len(marks)))
        for k, (j, txt) in enumerate(marks):
            nxt = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
            seg_lines = lines[j:nxt]
            b, c, m = classify(seg_lines)
            print('   L%-5d %5d行 (码%4d 注%4d 空%3d)  %s'
                  % (f['start'] + j, nxt - j, c, m, b, txt))

# ---------- 4. 输出：嵌套深度分布 ----------
def nest():
    print('\n' + '=' * 100)
    print('缩进/嵌套深度（4 空格 = 1 层）—— 深度越大越难改')
    print('=' * 100)
    hist = collections.Counter()
    deep = collections.defaultdict(list)
    for f in funcs:
        lines = L[f['start'] - 1:f['end']]
        for j, s in enumerate(lines):
            t = s.strip()
            if not t or t.startswith('//'):
                continue
            d = (len(s) - len(s.lstrip(' '))) // 4
            hist[d] += 1
            if d >= 6:
                deep[d].append((f['name'], f['start'] + j, t[:80]))
    tot = sum(hist.values())
    for d in sorted(hist):
        bar = '#' * int(60.0 * hist[d] / tot)
        print('  深度 %-2d  %6d 行  %5.1f%%  %s' % (d, hist[d], 100.0 * hist[d] / tot, bar))
    print('\n深度 >=6 的行共 %d 行，分布：' % sum(len(v) for v in deep.values()))
    for d in sorted(deep):
        cnt = collections.Counter(x[0] for x in deep[d])
        print('  深度 %d: %d 行  %s' % (d, len(deep[d]), dict(cnt.most_common(6))))

# ---------- 5. 输出：重复代码块（聚簇 + 最长匹配） ----------
def _owner(ln):
    for f in funcs:
        if f['start'] <= ln + 1 <= f['end']:
            return f['name']
    return '<top>'

def dup(cap=70):
    print('\n' + '=' * 100)
    print('重复代码块检测（去注释/数字→N/去空白 后 **>=8 行连续相同**，按最长匹配聚簇）')
    print('=' * 100)
    def norm(s):
        s = re.sub(r'//.*', '', s)
        s = re.sub(r'\b\d+(\.\d+)?\b', 'N', s)
        s = re.sub(r'\s+', '', s)
        return s
    body = [norm(x) for x in L]
    ok = [bool(b) and len(b) >= 8 for b in body]      # 只以"有实义且够长"的行做种子

    SEED = 4
    seeds = collections.defaultdict(list)
    for i in range(N - SEED):
        if all(ok[i + k] for k in range(SEED)):
            seeds[tuple(body[i:i + SEED])].append(i)

    def mlen(i, j):
        k = 0
        while k < cap and i + k < N and j + k < N and body[i + k] == body[j + k] and ok[i + k]:
            k += 1
        return k

    found = {}   # (i, j) -> 长度
    for locs in seeds.values():
        if len(locs) < 2 or len(locs) > 40:          # 出现过多 = 常见惯用法，非复制粘贴
            continue
        for x in range(len(locs)):
            for y in range(x + 1, len(locs)):
                i, j = locs[x], locs[y]
                if i > 0 and j > 0 and body[i - 1] == body[j - 1]:
                    continue                             # 非左端最大，跳过
                found[(i, j)] = mlen(i, j)

    # 聚簇：把「起点相邻且长度重合」的多条合并为一条最长记录
    items = [(ml, i, j) for (i, j), ml in found.items() if ml >= int(os.environ.get('DUPMIN', '8'))]
    items.sort(key=lambda t: (-t[0], t[1]))
    used = []
    out = []
    for ml, i, j in items:
        if any(abs(i - u) < cap and abs(j - v) < cap for u, v in used):
            continue
        used.append((i, j))
        out.append((ml, i, j))
        if len(out) >= 20:
            break

    if not out:
        print('  未发现 >=8 行的重复块。')
    for ml, i, j in out:
        allpos = sorted({i, j} | {p for p in range(N - SEED)
                                  if p != i and p != j and body[p:p + ml] == body[i:i + ml]
                                  and all(ok[p + k] for k in range(min(ml, SEED)))})
        allpos = [p for p in allpos if p + ml <= N]
        loc = ' , '.join('%s:L%d' % (_owner(p), p + 1) for p in allpos)
        print('\n  [%d 行 x %d 处] %s' % (ml, len(allpos), loc))
        print('     ' + ' ⏎ '.join(x.strip() for x in L[i:i + min(4, ml)])[:220])

    print('\n  ※ 归一化：去注释、数字→N、去全部空白 ⇒ 常量不同的同构代码也会命中（多为此前"复制粘贴 + 改常量"的产物）。')

# ---------- 5b. 宏使用情况 ----------
def macro():
    print('\n' + '=' * 100)
    print('#define 使用情况（UNUSED = 定义后再无引用；ONLY-COMMENT = 只出现在注释里）')
    print('=' * 100)
    mac = []
    for i, s in enumerate(L):
        m = re.match(r'^#define\s+(\w+)\b(.*)$', s)
        if m:
            mac.append((i, m.group(1), m.group(2)[:60]))
    unused, onlyc = [], []
    for i, name, rest in mac:
        cnt = 0; ccomment = 0
        for j, s in enumerate(L):
            if j == i:
                continue
            t = s.split('//')[0] if not s.strip().startswith('//') else ''
            if re.search(r'\b' + re.escape(name) + r'\b', t):
                cnt += 1
            elif re.search(r'\b' + re.escape(name) + r'\b', s):
                ccomment += 1
        if cnt == 0:
            (onlyc if ccomment else unused).append((i, name, rest, ccomment))
    print('宏总数 %d  |  完全未使用 %d  |  仅注释提及 %d\n' % (len(mac), len(unused), len(onlyc)))
    for lab, arr in (('【完全未使用】', unused), ('【仅注释提及，代码里不生效】', onlyc)):
        if not arr:
            continue
        print(lab)
        for i, name, rest, cc in arr:
            print('   L%-5d %-38s  %s' % (i + 1, name, rest))
        print()

    # 宏注释占用行数（头部第 1~380 行）
    head_end = defs[0][0] if defs else 0
    hb, hc, hm = classify(L[:head_end])
    print('常量/宏头部(前 %d 行): 代码 %d / 注释 %d / 空行 %d ⇒ 注释占 %.0f%%'
          % (head_end, hc, hm, hb, 100.0 * hm / max(1, hc + hm)))

# ---------- 6. 输出：注释/宏/死代码线索 ----------
def misc():
    print('\n' + '=' * 100)
    print('其它体量指标')
    print('=' * 100)
    blank, code, cmt = classify(L)
    print('全文件: 代码 %d 行 / 注释 %d 行 / 空行 %d 行  ⇒ 注释占非空 %.0f%%'
          % (code, cmt, blank, 100.0 * cmt / max(1, code + cmt)))
    print('#define 总数: %d' % sum(1 for s in L if s.startswith('#define')))

    # 中文注释行（UTF-8 下 CJK 范围）
    cjk = sum(1 for s in L if s.strip().startswith('//') and re.search(r'[\u4e00-\u9fff]', s))
    print('中文注释行: %d (占注释 %.0f%%)' % (cjk, 100.0 * cjk / max(1, cmt)))

    # 疑似死代码：局部变量声明后从未再出现
    print('\n【疑似死代码：局部变量声明后未再被引用】')
    for f in funcs:
        lines = L[f['start'] - 1:f['end']]
        for j, s in enumerate(lines):
            mm = re.match(r'^\s+(?:int|double|bool|float|long|std::string|QString)\s+(\w+)\s*(?:=[^;]*)?;\s*(//.*)?$', s)
            if not mm:
                continue
            v = mm.group(1)
            rest = '\n'.join(lines[j + 1:])
            n_read = len(re.findall(r'\b' + re.escape(v) + r'\b', rest))
            if n_read == 0:
                print('   [未再出现] %s:L%d  %s' % (f['name'], f['start'] + j, s.strip()[:90]))
            elif n_read == 1 and re.search(r'\b' + re.escape(v) + r'\s*=', rest):
                print('   [仅被再赋值一次] %s:L%d  %s' % (f['name'], f['start'] + j, s.strip()[:90]))

if __name__ == '__main__':
    args = set(sys.argv[1:])
    if not args or '--all' in args:
        head(); segs(); nest(); dup(); misc()
    else:
        if '--fn' in args: head()
        if '--seg' in args: segs()
        if '--nest' in args: nest()
        if '--dup' in args: dup()
        if '--misc' in args: misc()
        if '--macro' in args: macro()
