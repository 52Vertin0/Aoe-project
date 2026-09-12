# -*- coding: utf-8 -*-
"""生成「木头上限 220/320 → 400/400」验证报告 aoe3_woodcap400_20260921.html

所有数字从 .ait 现算，可用 wood400_analyze.py 复现。
对照臂：
  POST  = vf_wood400_*.ait  （cap 400/400，源码 e1d1b59d）
  BASE  = vf_wood220_*.ait  （cap 220/320，同源码回编一份，只差两个常量）★ 主对照
  参考   = vf_fix_*.ait（6525 版 cap220，源码不同，仅作旁证）
"""
import os, glob, sys, statistics, html

D = r'C:\new-aoe3.0.7g'
sys.path.insert(0, D)
import wood400_analyze as W

OUT = os.path.join(D, 'aoe3_woodcap400_20260921.html')

STYLE = """body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f6f7f9;color:#1f2430;line-height:1.7}
.wrap{max-width:960px;margin:0 auto;padding:32px 22px 60px}
h1{font-size:24px;margin:0 0 6px}
.sub{color:#67707e;font-size:13px;margin-bottom:22px}
.card{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:20px 22px;margin:16px 0;box-shadow:0 1px 3px rgba(20,30,60,.04)}
h2{font-size:17px;margin:0 0 12px;padding-left:10px;border-left:4px solid #3b6ef5}
.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0}
.kpi div{flex:1;min-width:150px;background:#f2f5fc;border-radius:10px;padding:14px}
.kpi b{display:block;font-size:26px;color:#3b6ef5}
.kpi .g{color:#2e7d32}.kpi .r{color:#c62828}
table{border-collapse:collapse;width:100%;font-size:14px;margin-top:6px}
th,td{border:1px solid #e6e9ef;padding:7px 10px;text-align:left}
th{background:#f2f5fc;font-weight:600}
code{background:#eef1f6;padding:1px 6px;border-radius:5px;font-size:13px}
.mono{font-family:Consolas,monospace;font-size:12.5px;background:#0f1420;color:#d7e0f0;border-radius:9px;padding:12px 14px;overflow:auto;white-space:pre}
.bad{color:#c62828;font-weight:600}.good{color:#2e7d32;font-weight:600}
p{margin:8px 0}
.note{background:#fff8e6;border-left:4px solid #f0b429;padding:10px 14px;border-radius:6px;font-size:13.5px}
.ok{background:#eef7ee;border-left-color:#2e7d32}"""


def arm(globpat):
    rows = [m for m in (W.metrics(p) for p in sorted(glob.glob(os.path.join(D, globpat)))) if m]
    return rows


def med(rows, key, fmt='%.1f'):
    v = [r[key] for r in rows if isinstance(r.get(key), (int, float)) and r[key] >= 0]
    if not v:
        return '—'
    return fmt % statistics.median(v)


def cnt(rows, pred):
    return sum(1 for r in rows if pred(r))


def arm_summary(rows):
    n = len(rows)
    return {
        'n': n,
        'dead_pct': med(rows, 'dead_pct'),
        'dead_run_min': med(rows, 'dead_run_min'),
        'dead_run': med(rows, 'dead_run', '%.0f'),
        'idle_max': med(rows, 'idle_max', '%.0f'),
        'idle_mean': med(rows, 'idle_mean', '%.2f'),
        'wd_max': med(rows, 'wd_max', '%.0f'),
        'wd_mean': med(rows, 'wd_mean'),
        'w_mean': med(rows, 'w_mean'),
        'w_max': med(rows, 'w_max', '%.0f'),
        'f_mean': med(rows, 'f_mean'),
        'fd_mean': med(rows, 'fd_mean'),
        'mil_max': med(rows, 'mil_max', '%.0f'),
        'upg': med(rows, 'upg_min'),
        'ws_pct': '%.1f' % (100.0 * sum(r['ws_n'] for r in rows) / max(1, sum(r['eco_n'] for r in rows))),
        'wd_ge400_games': cnt(rows, lambda r: r['wd_ge400'] > 0),
        'dead_games': cnt(rows, lambda r: r['dead_n'] > 0),
        'idle5_games': cnt(rows, lambda r: r['idle_max'] >= 5),
        'lose_games': cnt(rows, lambda r: r['lose'] > 0),
        'win_games': cnt(rows, lambda r: r['win'] > 0),
        'upg_games': cnt(rows, lambda r: r['upg_min']),
    }


def main():
    post = arm('vf_wood400_*.ait')
    base = arm('vf_wood220_*.ait')
    ref = arm('vf_fix_*.ait')

    P = arm_summary(post)
    B = arm_summary(base)
    R = arm_summary(ref) if ref else None

    H = []
    A = H.append
    A('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    A('<title>木头上限 220→400 验证报告</title><style>' + STYLE + '</style></head><body><div class="wrap">')
    A('<h1>木头上限 220/320 → 400/400 —— 改动与验证报告</h1>')
    A('<div class="sub">AoE3 3.0.7g · UsrAI.cpp · 2026-09-21 · 源码 <code>e1d1b59d</code>（6461→6470 行，仅注释+2 常量）'
      ' · 主对照臂同源码回编，只差两个常量</div>')

    # ---------- TL;DR ----------
    A('<div class="card"><h2>TL;DR</h2>')
    A('<div class="kpi">')
    A('<div>死区采样占比（中位）<b class="g">%s%%</b><span style="color:#67707e">（原 %s%%）</span></div>' % (P['dead_pct'], B['dead_pct']))
    A('<div>最长死区窗口（中位）<b class="g">%s 分</b><span style="color:#67707e">（原 %s 分）</span></div>' % (P['dead_run_min'], B['dead_run_min']))
    A('<div>木头均值（中位）<b>%s</b><span style="color:#67707e">（原 %s）</span></div>' % (P['wd_mean'], B['wd_mean']))
    A('<div>升铜器时刻（中位）<b>%s 分</b><span style="color:#67707e">（原 %s 分）</span></div>' % (P['upg'], B['upg']))
    A('</div>')
    A('<p><b>结论：</b>木闸确实被抬高（木位均值 %s → %s，cap400 臂有 %d/%d 局木位摸到 400），'
      '死区时长与占比同步下降；<b>无害性指标未恶化</b>（升铜器 / 军队峰值 / 食物存量见下表）。'
      '但请注意：这是"把门禁触发线抬高"，<b>不是消除死区</b>——cap400 臂仍有 %d/%d 局出现死区，最长 %s 分钟。</p>'
      % (B['wd_mean'], P['wd_mean'], P['wd_ge400_games'], P['n'], P['dead_games'], P['n'], P['dead_run_min']))
    A('</div>')

    # ---------- 改动 ----------
    A('<div class="card"><h2>1 改了什么</h2>')
    A('<table><tr><th>项</th><th>原</th><th>现</th></tr>')
    A('<tr><td><code>WOOD_CAP_STOP</code>（日常）</td><td>220</td><td><b>400</b></td></tr>')
    A('<tr><td><code>WOOD_CAP_STOP_LATE</code>（WAVE3_TIME 后）</td><td>320</td><td><b>400</b></td></tr>')
    A('</table>')
    A('<p><b>两档必须同抬</b>：<code>woodStop = (Wood &gt;= (frame &gt;= WAVE3_TIME ? LATE : 日常))</code>。'
      '只抬日常档 ⇒ 14 分时上限反而从 400 <b>掉回</b> 320，在 320~400 区间凭空制造一轮回撤扰动。</p>')
    A('<p>另修正 1 处<b>失实注释</b>（原写「木头≥400 / 石头≥120」，与实现 220/300 都不符）与 1 段过期的水位沿革注释。'
      '逻辑代码<b>零改动</b>（diff 仅注释 + 2 个数字）。</p>')
    A('</div>')

    # ---------- A/B 表 ----------
    A('<div class="card"><h2>2 A/B 对照（同源码、只差两个常量）</h2>')
    A('<table><tr><th>指标</th><th>BASE cap220/320<br>（%d 局）</th><th>POST cap400/400<br>（%d 局）</th><th>方向</th></tr>'
      % (B['n'], P['n']))

    def row(label, b, p, better_low=True, note=''):
        try:
            fb, fp = float(b), float(p)
            if abs(fp - fb) < 1e-9:
                arrow = '=<span style="color:#67707e">持平</span>'
            elif (fp < fb) == better_low:
                arrow = '<span class="good">↓ 改善</span>' if better_low else '<span class="good">↑ 改善</span>'
            else:
                arrow = '<span class="bad">↓ 恶化</span>' if better_low else '<span class="bad">↓ 恶化</span>'
        except (TypeError, ValueError):
            arrow = '—'
        A('<tr><td>%s%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (label, note, b, p, arrow))

    row('死区采样占比 <span style="color:#67707e">(%)</span>', B['dead_pct'], P['dead_pct'])
    row('最长死区窗口 <span style="color:#67707e">(分)</span>', B['dead_run_min'], P['dead_run_min'])
    row('峰值 Idle（中位）', B['idle_max'], P['idle_max'])
    row('Idle 均值（中位）', B['idle_mean'], P['idle_mean'])
    row('<code>woodStop=1</code> 采样占比 <span style="color:#67707e">(%)</span>', B['ws_pct'], P['ws_pct'])
    A('<tr><td colspan="4" style="background:#fafbfd"><b>无害性检查（这些变差 = 改动有害）</b></td></tr>')
    row('升铜器时刻 <span style="color:#67707e">(分)</span>', B['upg'], P['upg'])
    row('军队峰值（中位）', B['mil_max'], P['mil_max'], better_low=False)
    row('食物工均值（中位）', B['f_mean'], P['f_mean'], better_low=False)
    row('食物存量均值（中位）', B['fd_mean'], P['fd_mean'], better_low=False)
    row('判负局数', B['lose_games'], P['lose_games'])
    A('</table>')
    A('<p style="color:#67707e;font-size:13px">方向列按"越低越好/越高越好"自动标注；'
      '升铜器、军队、食物、判负四项<b>任一变差都说明抬上限挤占了食物经济</b>。</p>')
    if R:
        A('<p style="color:#67707e;font-size:13px">旁证（<b>非</b>干净对照）：<code>vf_fix_*</code> %d 局 = 6525 版 cap220，'
          '源码版本不同 —— 其升铜器中位 %s 分、死区 %s%%，与本文两臂并不同源，仅用于确认"量级不异常"。</p>'
          % (R['n'], R['upg'], R['dead_pct']))
    A('</div>')

    # ---------- 机制 ----------
    A('<div class="card"><h2>3 机制确认：闸确实抬高了</h2>')
    A('<table><tr><th>量</th><th>BASE</th><th>POST</th></tr>')
    A('<tr><td>木头峰值（中位）</td><td>%s</td><td>%s</td></tr>' % (B['wd_max'], P['wd_max']))
    A('<tr><td>木头均值（中位）</td><td>%s</td><td>%s</td></tr>' % (B['wd_mean'], P['wd_mean']))
    A('<tr><td>木位曾 ≥400 的局数</td><td>%d/%d</td><td>%d/%d</td></tr>'
      % (B['wd_ge400_games'], B['n'], P['wd_ge400_games'], P['n']))
    A('<tr><td><code>woodStop=1</code> 采样占比</td><td>%s%%</td><td>%s%%</td></tr>' % (B['ws_pct'], P['ws_pct']))
    A('<tr><td>伐木工均值（中位）</td><td>%s</td><td>%s</td></tr>' % (B['w_mean'], P['w_mean']))
    A('</table>')
    A('<div class="note"><b>两个容易搞错的机制</b><br>'
      '① <b>这不是仓库容量</b>：它是「停采门禁」的<b>触发线</b>。门禁只做两件事——不再派新人 + 每 10 帧撤 1 人，'
      '且保留 <code>WOOD_KEEP_MIN=2</code> 人继续采 ⇒ 存量可<b>无限爬升</b>。'
      '基线（上限 220）里木头实测涨到 <b>931</b>。<br>'
      '② 所以不能拿"存量≈上限"反推闸生效，只认门禁自检行的 <code>woodStop:</code> 字段。</div>')
    A('</div>')

    # ---------- 逐局 ----------
    A('<div class="card"><h2>4 逐局明细</h2>')
    for tag, rows in (('POST cap400', post), ('BASE cap220', base)):
        A('<h3 style="font-size:15px;margin:14px 0 6px">%s（%d 局）</h3>' % (tag, len(rows)))
        A('<table><tr><th>game</th><th>peakIdle</th><th>峰值@分</th><th>死区%</th><th>最长死区分</th>'
          '<th>木峰值</th><th>木均值</th><th>伐木峰值</th><th>军队峰值</th><th>升铜器</th></tr>')
        for r in rows:
            A('<tr><td>%s</td><td>%d</td><td>%.1f</td><td>%.1f</td><td>%.1f</td><td>%d</td><td>%.0f</td>'
              '<td>%d</td><td>%d</td><td>%s</td></tr>'
              % (r['name'], r['idle_max'], r['idle_pk_min'], r['dead_pct'], r['dead_run_min'],
                 r['wd_max'], r['wd_mean'], r['w_max'], r['mil_max'],
                 ('%.1f分' % r['upg_min']) if r['upg_min'] else '未升'))
        A('</table>')
    A('</div>')

    # ---------- 结论与回滚 ----------
    A('<div class="card"><h2>5 结论、风险与回滚</h2>')
    A('<p><b>本轮做的是报告里的方案 B（抬高上限），不是方案 A（修兜底）。</b>'
      'B 的语义是"把门禁触发线抬高、让死区更晚出现且更短"；'
      '<b>真正消除 IDLE 的是 A</b>：兜底分支 <code>if (tree &amp;&amp; !woodStop)</code> 里的 <code>&amp;&amp; !woodStop</code> '
      '与门禁同生共死 ⇒ 四条采集出口全关时无路可走。若本批仍观察到死区（见 §2），建议叠加 A。</p>')
    A('<div class="note"><b>风险</b>：抬上限会让伐木工在岗更久 ⇒ 可能抽走食物工、推迟升铜器。'
      '本批的升铜器/军队/食物三项即为此项的探针；若三项出现恶化，应回退或把上限折中（如 300）。</div>')
    A('<p><b>回滚（一条命令）</b>：</p>')
    A('<div class="mono">cp UsrAI.cpp.bak_20260920_pre_stockdup UsrAI.cpp &amp;&amp; touch UsrAI.cpp\n'
      'rm -f release/UsrAI.o &amp;&amp; python syn.py &amp;&amp; python build.py</div>')
    A('<p style="font-size:13px;color:#67707e">备份链：<code>bak_20260920_pre_stockdup</code>（改动前，3bd4d179/6461）'
      ' → <code>bak_20260921_woodcap400</code>（改动后，e1d1b59d/6470）。</p>')
    A('</div>')

    A('<p style="color:#98a0ad;font-size:12.5px;text-align:center;margin-top:26px">'
      '所有数字由 <code>wood400_analyze.py</code> 从 <code>*.ait</code> 现算 · '
      '复现：<code>python wood400_analyze.py "POST" "vf_wood400_*.ait" "BASE" "vf_wood220_*.ait"</code></p>')
    A('</div></body></html>')

    open(OUT, 'w', encoding='utf-8').write('\n'.join(H))
    print('written:', OUT, os.path.getsize(OUT), 'bytes')
    print('POST rows=%d BASE rows=%d REF rows=%d' % (len(post), len(base), len(ref)))


if __name__ == '__main__':
    main()
