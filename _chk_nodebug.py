# -*- coding: utf-8 -*-
r"""_chk_nodebug.py —— 提交前核对「_submit\nodebug\」是否与当前源码一致。

为什么需要它：
    本项目有个反复踩的坑 —— **生成物（_submit\）会陈旧定格**（曾定格 5 小时，
    拿旧提交件当新代码提交）。nodebug 版同理：改了 UsrAI.cpp 之后若忘跑
    `mk_submit.py --nodebug-only`，目录里躺着的就是上一版。

它做什么：
    不算 md5 存档，而是**当场重算**「当前源码 → 应有的 nodebug 内容」，再与磁盘上的
    实际文件逐字节比对。相等 ⇒ 新鲜；不等 ⇒ 陈旧（并指出差在哪类结构上）。
    同时核验三件结构事实：① 补丁块位于**所有 #include 之后**；
    ② 剥掉补丁块后与源源码**逐字符相同**；③ 文件是纯 LF、无 BOM。

用法：
    python _chk_nodebug.py            # 核对，退出码 0=新鲜 / 1=陈旧或不一致
    python _chk_nodebug.py --fix      # 陈旧则自动重跑生成
"""
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE or '.')
import mk_submit as M           # noqa: E402  复用 make_nodebug / NODEBUG_PATCH


def md5b(b):
    return hashlib.md5(b).hexdigest()


def to_lf(b):
    return b.replace(b'\r\r\n', b'\r\n').replace(b'\r\n', b'\n')


def inspect(path, name):
    """返回该文件的体检字典；文件不存在返回 None。"""
    if not os.path.exists(path):
        return None
    b = open(path, 'rb').read()
    return {
        'path': path, 'name': name, 'bytes': len(b), 'bom': b[:3] == b'\xef\xbb\xbf',
        'crlf': b.count(b'\r\n'), 'lf': b.count(b'\n') - b.count(b'\r\n'),
        'md5': md5b(b), 'raw': b,
    }


def line_of(b, needle):
    for i, L in enumerate(b.split(b'\n')):
        if needle in L:
            return i + 1
    return None


def main():
    fix = '--fix' in sys.argv
    src_dir = M.DEFAULT_SRC
    nb_dir = os.path.join(src_dir, '_submit', 'nodebug')
    ok = True

    print('=' * 78)
    print('核对 %s  <->  %s' % (src_dir, nb_dir))
    print('=' * 78)

    # ---- UsrAI.cpp ----
    s_cpp = os.path.join(src_dir, 'UsrAI.cpp')
    n_cpp = os.path.join(nb_dir, 'UsrAI.cpp')
    src = to_lf(open(s_cpp, 'rb').read())
    want, at, n = M.make_nodebug(src)
    got = inspect(n_cpp, 'nodebug/UsrAI.cpp')

    if got is None:
        print('[X] 缺文件 %s ⇒ 先跑 python mk_submit.py --nodebug-only' % n_cpp)
        ok = False
    else:
        cur = got['raw']
        print('源的纯 LF 版 : %d B  md5=%s' % (len(src), md5b(src)))
        print('应有 nodebug : %d B  md5=%s  (补丁块第 %d~%d 行)'
              % (len(want), md5b(want), at, at + n - 1))
        print('磁盘 nodebug : %d B  md5=%s' % (got['bytes'], got['md5']))

        if cur == want:
            print('[.] 新鲜：与当前源码一致')
        else:
            ok = False
            print('[X] ★陈旧或不一致★ 磁盘内容不是「当前源码 + 补丁块」的产物')
            print('    ⇒ 跑 python mk_submit.py --nodebug-only 重新生成')

        # 结构事实①：补丁块必须位于所有 #include 之后
        lines = cur.split(b'\n')
        last_inc = max([i for i, L in enumerate(lines) if L.startswith(b'#include')] or [-1])
        macro_ln = line_of(cur, b'#define DebugText')
        if macro_ln is None:
            print('[X] 找不到 #define DebugText（补丁块丢了？）')
            ok = False
        else:
            if macro_ln > last_inc + 1:
                print('[.] 补丁块位置正确：宏在第 %d 行，最后一个 #include 在第 %d 行'
                      % (macro_ln, last_inc + 1))
            else:
                print('[X] ★宏在第 %d 行，早于/等于最后一个 #include（第 %d 行）★'
                      % (macro_ln, last_inc + 1))
                print('    ⇒ 会把 ai.h 里 DebugText 的声明一起替换掉 ⇒ 编译错')
                ok = False

        # 结构事实②：剥掉补丁块后必须与源逐字符相同
        try:
            stripped = b'\n'.join(lines[:at - 2] + lines[at - 2 + n + 1:])
        except Exception as e:                       # noqa: BLE001
            stripped = b''
            print('[X] 剥补丁块失败: %s' % e)
            ok = False
        same = stripped == src
        print('[%s] 剥掉补丁块后与源码逐字符相同' % ('.' if same else 'X'))
        if not same:
            ok = False

        # 结构事实③：行尾 / BOM
        tail_ok = (got['crlf'] == 0 and got['lf'] > 0 and not got['bom'])
        print('[%s] 纯 LF（CRLF=%d 纯LF=%d BOM=%s）'
              % ('.' if tail_ok else 'X', got['crlf'], got['lf'], got['bom']))
        if not tail_ok:
            ok = False

        # 调用点守恒：产物比源恰好多 1 行（宏定义行）
        n_src = sum(1 for L in src.split(b'\n') if b'DebugText(' in L)
        n_nb = sum(1 for L in cur.split(b'\n') if b'DebugText(' in L)
        keep = (n_nb == n_src + 1)
        print('[%s] DebugText( 行数 源 %d → 产物 %d（应 +1 = 宏定义行）'
              % ('.' if keep else 'X', n_src, n_nb))
        if not keep:
            ok = False

    # ---- UsrAI.h （应与源同内容，仅转 LF）----
    s_h = os.path.join(src_dir, 'UsrAI.h')
    n_h = os.path.join(nb_dir, 'UsrAI.h')
    want_h = to_lf(open(s_h, 'rb').read())
    got_h = inspect(n_h, 'nodebug/UsrAI.h')
    if got_h is None:
        print('[X] 缺文件 %s' % n_h)
        ok = False
    else:
        same_h = got_h['raw'] == want_h
        print('[%s] UsrAI.h 一致（%d B, md5=%s）'
              % ('.' if same_h else 'X', got_h['bytes'], got_h['md5']))
        if not same_h:
            ok = False

    print('=' * 78)
    if ok:
        print('==> 新鲜且结构正确，可直接提交 _submit\\nodebug\\ 下的两个文件。')
        print('    提醒：编译校验仍需 PATH 前置 32 位 bin，否则 cc1plus 静默 exit=1：')
        print('      export PATH="/d/360Downloads/Tools/mingw530_32/bin:$PATH"')
        return 0

    print('==> 核对未通过（见上面 [X]）。')
    if fix:
        print('    --fix：正在重新生成 ...')
        r = subprocess.call([sys.executable, os.path.join(src_dir, 'mk_submit.py'),
                             '--nodebug-only', '--src', src_dir])
        print('    重新生成退出码 = %d，请重跑本脚本确认' % r)
    else:
        print('    修复： python mk_submit.py --nodebug-only')
    return 1


if __name__ == '__main__':
    sys.exit(main())
