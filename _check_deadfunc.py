# -*- coding: utf-8 -*-
"""改进版：剥除注释后再统计成员函数调用，避免把注释/字符串里的 `NAME()` 误算成调用。
同时检查「.h 声明但 cpp 无 UsrAI:: 实现」的遗漏实现项。"""
import re, collections

CPP = r'C:\new-aoe3.0.7g\UsrAI.cpp'
H   = r'C:\new-aoe3.0.7g\UsrAI.h'
raw_cpp = open(CPP, encoding='utf-8', errors='replace').read()
h       = open(H,   encoding='utf-8', errors='replace').read()

def strip_comments(s):
    s = re.sub(r'//[^\n]*', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return s

cpp = strip_comments(raw_cpp)   # 用于调用统计（已去注释）

ENGINE_CB = {
    'processData','processFrame','HumanMove','HumanAction','HumanBuild',
    'BuildingAction','PinPointStrike','AddToIns','clearInsRet',
    'refreshSnapshot','event','commitInstruction','logEnvOnce',
    'logSnapBeat','checkDirtySnapshot','think','onMessage','init',
    'onLoad','save','load','run','stopThread','wakeAll','wait',
}

# 成员函数定义（cpp，剥注释后）
defs = re.findall(r'(?:UsrAI|UsrAICore)::(\w+)\s*\(', cpp)
defc = collections.Counter(defs)

# .h 中声明的类内成员函数名（UsrAI + UsrAICore 块内）
def class_block(h, cls):
    i = h.find('class ' + cls)
    if i < 0: return ''
    j = h.find('};', i)
    return h[i:j]
h_funcs = set()
for cls in ['UsrAICore', 'UsrAI']:
    blk = class_block(h, cls)
    for m in re.finditer(r'(?:virtual\s+|static\s+|inline\s+)?(?:[\w:<>&*,\s]+?)\b(\w+)\s*\([^;{]*\)\s*(?:const\s*)?(?=\{|;)', blk):
        h_funcs.add(m.group(1))
# 去掉 ctor/dtor/枚举值/纯类型
NOISE = {'UsrAICore','UsrAI','State','UsrAI','~UsrAI','~UsrAICore'}
h_funcs -= NOISE

rows = []
for name, ndef in sorted(defc.items()):
    # 调用 = 剥注释后 cpp 中 `\bNAME(` 出现，减去 `UsrAI::NAME(`/`UsrAICore::NAME(` 定义
    total = len(re.findall(r'\b' + re.escape(name) + r'\s*\(', cpp))
    def_here = len(re.findall(r'(?:UsrAI|UsrAICore)::' + re.escape(name) + r'\s*\(', cpp))
    calls = total - def_here
    rows.append((name, ndef, total, calls))

print('=' * 88)
print('成员函数调用排查（已剥注释；calls = 出现 − 定义）')
print('=' * 88)
print(f'{"函数名":36} {"定义":>4} {"总出现":>6} {"调用":>5}  判读')
print('-' * 88)

dead = []   # 强候选：零调用、非引擎回调
weak = []
for name, ndef, total, calls in rows:
    if calls == 0:
        if name in ENGINE_CB:
            print(f'{name:36} {ndef:>4} {total:>6} {calls:>5}   引擎回调(保留)')
        else:
            dead.append(name)
            print(f'{name:36} {ndef:>4} {total:>6} {calls:>5}   ★零调用 = 候选死代码')
    elif calls <= 2:
        weak.append((name, calls))
        print(f'{name:36} {ndef:>4} {total:>6} {calls:>5}   低频(人工确认)')

print()
print('=' * 88)
print('零调用成员函数（强候选死代码，已排除引擎回调）：')
print('=' * 88)
print('  (无)' if not dead else '\n'.join('  - ' + d for d in dead))

# .h 声明但 cpp 无 UsrAI::/UsrAICore:: 实现（排除内联与引擎回调）
inline_impl = set(re.findall(r'((?:virtual\s+|static\s+|inline\s+)?[\w:<>&*,\s]+?\b(\w+)\s*\([^;]*\)\s*(?:const\s*)?\s*\{)', h))
# 上面返回的是整匹配；改抓名字
inline_names = set(re.findall(r'(?:virtual\s+|static\s+|inline\s+)?[\w:<>&*,\s]+?\b(\w+)\s*\([^;]*\)\s*(?:const\s*)?\s*\{', h))
missing = sorted(f for f in h_funcs
                 if f not in defc and f not in inline_names and f not in ENGINE_CB
                 and not f.startswith('~'))
print()
print('=' * 88)
print('.h 声明但 cpp 无实现且无内联（可能的遗漏实现 / 纯虚 stub）：')
print('=' * 88)
print('  (无)' if not missing else '\n'.join('  - ' + m for m in missing))

print()
print(f'统计：成员函数定义={len(rows)}，零调用候选={len(dead)}，低频弱候选={len(weak)}，遗漏实现={len(missing)}')
