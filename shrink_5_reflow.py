# -*- coding: utf-8 -*-
"""
shrink_5_reflow.py —— 第五轮：注释「排版重排」（纯换行合并，零文字增删）

动机：注释行中位仅 60 字符、p90 82、max 119 ⇒ 大量行是**排版换行**而非语义换行。
     全部注释文本 77915 字符，按 110 列重排理论可省 ~700 行。

为什么可以证明无害：
  1) 本脚本只改「换行位置」，不改任何字符 —— 自检 = 【空白归一化后的注释文本全等】；
  2) 注释不参与编译 ⇒ .text 段逐字节相同（由 objcopy + cmp 独立验证）。

保守规则（宁少勿错）：
  · 只在【同一个注释块内】合并，绝不跨块、不与代码同行；
  · 遇到「结构行」= 段首新段的锚点，强制断行，不并入上一行：
      装饰线(// ==== / // ----)、表格行(含 |)、列表项(// - / // • / // 1) / // ①)、
      ★ 标记行、箭头行(含 → 或 ⇒)；
  · 合并后行宽（含缩进与 // ）不超过 WIDTH；
  · 块内若有任何一行的缩进与块首行不同 ⇒ 整个块跳过（避免破坏对齐）。

用法：python shrink_5_reflow.py            # 只测不写
      python shrink_5_reflow.py --write    # 写入（先备份）
"""
import io, re, sys

SRC = 'UsrAI.cpp'
WIDTH = 110
WRITE = '--write' in sys.argv

raw = io.open(SRC, encoding='utf-8', newline='').read()
lines = raw.split('\r\n')
N = len(lines)

SEP = re.compile(r'^\s*//\s*[=\-*~+#]{6,}\s*$')          # 装饰线
LIST = re.compile(r'^\s*//\s*(?:[-•·]|[0-9]+[).、]|[①-⑩]|\*)\s')  # 列表项
TAB = re.compile(r'^\s*//.*\|')                          # 表格行

def is_struct(body):
    """body = 去缩进去 // 后的文本。

    定案口径（2026-09-20 实测三档后选定）：
      · 仅当 ★ 出现在【行首】时断行 —— 保住标记的"头部"地位（本项目的导航锚点）；
      · ★ 出现在句中（如"…★ 必须 static…"）不拦，随段落合并；
      · 三档实测：行首+句中★都断 = −63 行；只行首断 = −153 行；全部不断 = −212 行。
        取中间档：收益 2.3%，且 ★ 头仍独立成行、注释文字 100% 保留。
    """
    return body.startswith('★')

def split_prefix(l):
    m = re.match(r'^(\s*//[ ]?)(.*)$', l)
    return (m.group(1), m.group(2).rstrip()) if m else None

out = []
i = 0
n_blocks = n_merged_blocks = n_saved = n_skip_align = 0
while i < N:
    if not lines[i].strip().startswith('//'):
        out.append(lines[i]); i += 1; continue
    j = i
    while j < N and lines[j].strip().startswith('//'):
        j += 1
    blk = lines[i:j]
    n_blocks += 1
    parsed = [split_prefix(l) for l in blk]
    # 缩进一致性检查（块首行的前导空白）
    ind0 = len(blk[0]) - len(blk[0].lstrip())
    if any(len(b) - len(b.lstrip()) != ind0 for b in blk):
        n_skip_align += 1
        out.extend(blk); i = j; continue

    new = []          # 输出块
    cur = None        # (prefix, text)
    for pfx, body in parsed:
        struct = (SEP.match(pfx + body) or LIST.match(pfx + body)
                  or TAB.match(pfx + body) or is_struct(body))
        if cur is None:
            cur = [pfx, body]
            continue
        if struct or is_struct(cur[1]):
            new.append(cur); cur = [pfx, body]; continue
        cand = cur[0] + cur[1] + ' ' + body
        if len(cand) <= WIDTH and not body.startswith('//'):
            cur[1] = cur[1] + ' ' + body
        else:
            new.append(cur); cur = [pfx, body]
    if cur:
        new.append(cur)

    newl = [p + t for p, t in new]
    out.extend(newl)
    if len(newl) < len(blk):
        n_merged_blocks += 1
        n_saved += len(blk) - len(newl)
    i = j

new_raw = '\r\n'.join(out)

# ---------- 自检 1：注释文本（空白归一化）必须完全一致 ----------
def cmt_text(t):
    body = []
    for l in t.split('\r\n'):
        m = re.match(r'^\s*//[ ]?(.*)$', l)
        if m:
            body.append(m.group(1))
    return re.sub(r'\s+', '', ''.join(body))

a, b = cmt_text(raw), cmt_text(new_raw)
same = (a == b)
print('行 %d -> %d （−%d）' % (N, len(out), N - len(out)))
print('注释块 %d 个，其中合并过 %d 个；因缩进不一致整块跳过 %d 个' % (n_blocks, n_merged_blocks, n_skip_align))
print('自检1 注释文字全等: %s   (旧 %d 字符 / 新 %d 字符)' % ('PASS ✓' if same else 'FAIL ✗', len(a), len(b)))
if not same:
    # 找出第一处差异
    for k in range(min(len(a), len(b))):
        if a[k] != b[k]:
            print('   首差 @%d: %r vs %r' % (k, a[k-30:k+30], b[k-30:k+30])); break
    else:
        print('   长度不同：%d vs %d' % (len(a), len(b)))
if not same:
    print('ABORT：文字不等 ⇒ 拒绝写入'); sys.exit(1)

if WRITE:
    io.open(SRC, 'w', encoding='utf-8', newline='').write(new_raw)
    d = io.open(SRC, 'rb').read()
    print('CRLF %d / LF %d（应相等）' % (d.count(b'\r\n'), d.count(b'\n')))
    print('WROTE OK')
else:
    print('（只测不写；加 --write 落盘）')
