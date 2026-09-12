#!/bin/sh
# ============================================================================
# chk_src.sh —— 源码字节级体检（POSIX sh，零依赖）
#
# 用途：任何"读→写 / 跨机传输"之后、编译报怪错之前，先跑一遍。
#       专抓会让 GCC 报怪错、却肉眼看不见的字节损伤：
#         · \r\r\n（双 CR）—— GCC 把孤立 \r 也当换行 ⇒ 行号 = 真实行号×2-1；
#                              `#define X \` 的续行符被切断 ⇒ 宏体掉到文件作用域
#                              ⇒ error: expected ')' before '?' token
#         · 孤立 LF / 孤立 CR —— 行尾混用，同类风险
#         · ??X 三元字         —— 中文被有损转码成 '?' 的残留（成批 -Wtrigraphs）
#         · 非 UTF-8 / UTF-8 BOM
#         · 行数快照
#
# 用法：
#   sh chk_src.sh UsrAI.cpp UsrAI.h          # 体检若干文件
#   sh chk_src.sh UsrAI.cpp 6342             # 只对第 1 个文件附带期望行数
#   sh chk_src.sh --scan .                   # 递归找 UsrAI*.cpp / UsrAI*.h
#
# 退出码：0 = 全部干净；1 = 至少一个文件有损伤
# ============================================================================

CR=$(printf '\r')
BADN=0

# ---- 单个文件体检。$1=路径  $2=期望行数(可空)  $3=quiet(1/0) ----
check_one() {
    _f="$1"; _exp="$2"; _quiet="$3"
    if [ ! -f "$_f" ]; then
        echo "缺文件: $_f"
        BADN=$((BADN + 1))
        return 0
    fi

    _bytes=$(wc -c < "$_f" | tr -d ' ')
    _nl=$(wc -l < "$_f" | tr -d ' ')

    # ★ 行尾统计必须走 od 的十六进制字节流：MSYS/Git Bash 下 sed/awk/tr 都以「文本模式」
    #   读文件，会把 \r\n 吞成 \n（实测 CRLF 数出 0，全是假阴性），只有 od 是逐字节的。
    #   先转成「每行一个字节」的纯 ASCII token 流，再在上面数序列 —— Linux/MSYS 都可靠。
    _stat=$(od -An -v -tx1 "$_f" 2>/dev/null | tr -s ' \n' '\n' | awk '
        $0=="0a" { if (p1=="0d") { crlf++; if (p2=="0d") rr++ } }
        $0=="0d" { totcr++ }
        { p2=p1; p1=$0 }
        END { printf "%d %d %d\n", crlf+0, rr+0, totcr+0 }')
    _crlf=$(printf '%s' "$_stat" | cut -d' ' -f1)
    _rr=$(printf '%s' "$_stat" | cut -d' ' -f2)
    _totcr=$(printf '%s' "$_stat" | cut -d' ' -f3)
    _tri=$(grep -o '??[=()<>/!-]' "$_f" 2>/dev/null | wc -l | tr -d ' ')
    _crlf=${_crlf:-0}; _rr=${_rr:-0}; _totcr=${_totcr:-0}; _tri=${_tri:-0}
    _lonelf=$(( _nl - _crlf ))                  # 不带 CR 收尾的行 = 孤立 LF
    _lonecr=$(( _totcr - _crlf - _rr ))         # 剩下的 CR = 孤立 CR（后面不跟 LF）

    _bom=""
    if [ "$(head -c 3 "$_f" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then
        _bom="yes"
    fi

    _u8="skip"
    if command -v iconv >/dev/null 2>&1; then
        if iconv -f UTF-8 -t UTF-8 "$_f" >/dev/null 2>&1; then _u8="yes"; else _u8="no"; fi
    fi

    _bad=""
    [ "$_rr" -gt 0 ]     && _bad="$_bad CRCR"
    [ "$_lonelf" -gt 0 ] && _bad="$_bad LONELF"
    [ "$_lonecr" -gt 0 ] && _bad="$_bad LONECR"
    [ "$_tri" -gt 0 ]    && _bad="$_bad TRIGRAPH"
    [ "$_bom" = "yes" ]  && _bad="$_bad BOM"
    [ "$_u8" = "no" ]    && _bad="$_bad NOTUTF8"
    if [ -n "$_exp" ] && [ "$_nl" != "$_exp" ]; then _bad="$_bad LINES($_nl!=$_exp)"; fi

    if [ "$_quiet" = "1" ]; then
        if [ -n "$_bad" ]; then
            echo "  [X] $_f   ($_nl 行, CRLF=$_crlf, 双CR=$_rr, 三元字=$_tri)$_bad"
            BADN=$((BADN + 1))
        else
            echo "  [.] $_f   OK  ($_nl 行, CRLF=$_crlf)"
        fi
        return 0
    fi

    echo "=========================================================================="
    echo "文件 : $_f"
    echo "字节 : $_bytes   行(\\n) : $_nl"
    echo "行尾 : CRLF=$_crlf  孤立LF=$_lonelf  孤立CR=$_lonecr  \\r\\r\\n=$_rr"
    echo "编码 : UTF-8=${_u8}${_bom:+  +BOM}"
    echo "三元字: $_tri 处"
    if [ -n "$_bad" ]; then
        echo "判定 : [X] 有损伤"
        [ "$_rr" -gt 0 ] && echo "   - \\r\\r\\n x$_rr —— 行号会变 2N-1，且切断 \\ 续行（最常见死因）"
        [ "$_lonelf" -gt 0 ] && echo "   - 孤立 LF x$_lonelf —— 行尾混用"
        [ "$_lonecr" -gt 0 ] && echo "   - 孤立 CR x$_lonecr —— GCC 会当换行"
        [ "$_tri" -gt 0 ] && echo "   - 三元字 ??X x$_tri —— 中文已被有损转码成 '?'（DebugText 中文标签全废）"
        [ "$_bom" = "yes" ] && echo "   - 带 UTF-8 BOM"
        [ "$_u8" = "no" ] && echo "   - 不是合法 UTF-8 —— 编码被换过"
        if [ -n "$_exp" ] && [ "$_nl" != "$_exp" ]; then
            echo "   - 行数 $_nl != 期望 $_exp —— 文件被动过（多了/少了几百行）"
        fi
        BADN=$((BADN + 1))
    else
        echo "判定 : [.] 干净（UTF-8 / 统一 CRLF / 无三元字）"
    fi
}

case "$1" in
    --scan)
        shift
        _dir="${1:-.}"
        _list=$(find "$_dir" \( -name 'UsrAI*.cpp' -o -name 'UsrAI*.h' \) \
                    -not -path '*/release/*' -not -path '*/.git/*' \
                    -not -path '*/tmpbuild/*' 2>/dev/null | sort)
        _n=0; for _p in $_list; do _n=$((_n + 1)); done
        echo "扫描根 : $_dir"
        echo "匹配   : $_n 个文件"
        echo "--------------------------------------------------------------------------"
        for _p in $_list; do check_one "$_p" "" 1; done
        echo "--------------------------------------------------------------------------"
        echo "汇总   : $_n 个文件，$BADN 个有损伤"
        ;;
    ""|-h|--help)
        sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
        exit 2
        ;;
    *)
        # 位置参数：非数字参数 = 文件；纯数字参数 = 期望行数（只作用于第 1 个文件）
        _exp=""
        _files=""
        for _a in "$@"; do
            case "$_a" in
                [0-9]*) _exp="$_a" ;;
                *) _files="$_files
$_a" ;;
            esac
        done
        _i=0
        for _f in $_files; do
            _i=$((_i + 1))
            if [ "$_i" = "1" ]; then
                check_one "$_f" "$_exp" 0
            else
                check_one "$_f" "" 0
            fi
        done
        ;;
esac

echo
if [ "$BADN" -gt 0 ]; then
    echo "==> $BADN 个文件有损伤（勿用于编译/提交）"
    exit 1
fi
echo "==> 全部干净"
exit 0
