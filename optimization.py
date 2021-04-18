from timeit import Timer
from types import CodeType

from opcode import opmap

UB = -1


def hot_process_mark_fast(co: CodeType, bc, target: int):
    """
    arguments:
        co: CodeType
        bc: [[int, int, int], ...]
        target: int
    return: [[int, int, int], ...]
    """
    # init state              => state == 0
    # LOAD_GLOBAL label       => state == 0, state = 1
    # LOAD_FAST label-name    => state == 1, state = 2
    # BINARY_MATRIX_MULTIPLY  => state == 2, state = 3
    # POP_TOP                 => state == 3, state = 0
    # otherwise               => state == n, state = 0
    LOAD_GLOBAL = opmap["LOAD_GLOBAL"]
    LOAD_FAST = opmap["LOAD_FAST"]
    BINARY_MATRIX_MULTIPLY = opmap["BINARY_MATRIX_MULTIPLY"]
    POP_TOP = opmap["POP_TOP"]
    JUMP_ABSOLUTE = opmap["JUMP_ABSOLUTE"]
    state = 0
    for idx, (pc, op, arg) in enumerate(bc):
        if state == 0 and op == LOAD_GLOBAL and co.co_names[arg] == "goto":
            state = 1
        elif state == 1 and op == LOAD_FAST:
            state = 2
        elif state == 2 and op == BINARY_MATRIX_MULTIPLY:
            state = 3
        elif state == 3 and op == POP_TOP:
            state = 0
            bc[idx - 3][1] = UB
            bc[idx - 2][1] = UB
            bc[idx - 1][1] = UB
            bc[idx][1] = JUMP_ABSOLUTE
            addr, _, index = bc[idx - 2]
            bc[idx][2] = target
        else:
            state = 0

    return bc


def bytecode2list(bc: bytes) -> "[[int, int, int], ...]":
    return [[pc, bc[pc], bc[pc + 1]] for pc in range(0, len(bc), 2)]


def list2bytecode(lst: "[[int, int, int], ...]") -> bytes:
    bc = []
    push = bc.append
    NOP = opmap["NOP"]
    for _, op, arg in lst:
        push(op if op != -1 else NOP)
        push(arg)
    return bytes(bc)


def post_process_mark_label(co: CodeType, bc):
    """
    arguments:
        co: CodeType
        bc: [[int, int, int], ...]
    return: ([[int, int, int], ...], {[key: str]: [value: int]})
    """
    # init state              => state == 0
    # LOAD_GLOBAL label       => state == 0, state = 1
    # LOAD_CONST label-name   => state == 1, state = 2
    # BINARY_MATRIX_MULTIPLY  => state == 2, state = 3
    # POP_TOP                 => state == 3, state = 0
    # otherwise               => state == n, state = 0
    LOAD_GLOBAL = opmap["LOAD_GLOBAL"]
    LOAD_CONST = opmap["LOAD_CONST"]
    BINARY_MATRIX_MULTIPLY = opmap["BINARY_MATRIX_MULTIPLY"]
    POP_TOP = opmap["POP_TOP"]
    state = 0
    labels = {}

    for idx, (pc, op, arg) in enumerate(bc):
        if state == 0 and op == LOAD_GLOBAL and co.co_names[arg] == "label":
            state = 1
        elif state == 1 and op == LOAD_CONST:
            state = 2
        elif state == 2 and op == BINARY_MATRIX_MULTIPLY:
            state = 3
        elif state == 3 and op == POP_TOP:
            state = 0
            bc[idx - 3][1] = UB
            bc[idx - 2][1] = UB
            bc[idx - 1][1] = UB
            bc[idx][1] = UB
            addr, _, index = bc[idx - 2]
            labels[co.co_consts[index]] = addr - 2
        else:
            state = 0

    return bc, labels


def post_process_mark_goto(co: CodeType, bc, labels: dict):
    """
    arguments:
        co: CodeType
        bc: [[int, int, int], ...]
        labels: {[key: str]: [value: int]}
    return: [[int, int, int], ...]
    """
    # init state              => state == 0
    # LOAD_GLOBAL label       => state == 0, state = 1
    # LOAD_CONST label-name   => state == 1, state = 2
    # BINARY_MATRIX_MULTIPLY  => state == 2, state = 3
    # POP_TOP                 => state == 3, state = 0
    # otherwise               => state == n, state = 0
    LOAD_GLOBAL = opmap["LOAD_GLOBAL"]
    LOAD_CONST = opmap["LOAD_CONST"]
    BINARY_MATRIX_MULTIPLY = opmap["BINARY_MATRIX_MULTIPLY"]
    POP_TOP = opmap["POP_TOP"]
    JUMP_ABSOLUTE = opmap["JUMP_ABSOLUTE"]
    state = 0

    for idx, (pc, op, arg) in enumerate(bc):
        if state == 0 and op == LOAD_GLOBAL and co.co_names[arg] == "goto":
            state = 1
        elif state == 1 and op == LOAD_CONST:
            state = 2
        elif state == 2 and op == BINARY_MATRIX_MULTIPLY:
            state = 3
        elif state == 3 and op == POP_TOP:
            state = 0
            bc[idx - 3][1] = UB
            bc[idx - 2][1] = UB
            bc[idx - 1][1] = UB
            bc[idx][1] = JUMP_ABSOLUTE
            addr, _, index = bc[idx - 2]
            target = labels.get(co.co_consts[index], None)
            if target is None:
                raise Exception
            bc[idx][2] = target
        else:
            state = 0

    return bc


def post_process_mark_clean_nop(co: CodeType, bc):
    """
    arguments:
        co: CodeType
        bc: [[int, int, int], ...]
    return: [[int, int, int], ...]
    """
    # target
    POP_JUMP_IF_TRUE = opmap["POP_JUMP_IF_TRUE"]
    POP_JUMP_IF_FALSE = opmap["POP_JUMP_IF_FALSE"]
    JUMP_IF_NOT_EXC_MATCH = opmap["JUMP_IF_NOT_EXC_MATCH"]
    JUMP_IF_TRUE_OR_POP = opmap["JUMP_IF_TRUE_OR_POP"]
    JUMP_IF_FALSE_OR_POP = opmap["JUMP_IF_FALSE_OR_POP"]
    JUMP_ABSOLUTE = opmap["JUMP_ABSOLUTE"]
    target = (POP_JUMP_IF_TRUE, POP_JUMP_IF_FALSE, JUMP_IF_NOT_EXC_MATCH,
              JUMP_IF_TRUE_OR_POP, JUMP_IF_FALSE_OR_POP, JUMP_ABSOLUTE)
    # delta
    SETUP_WITH = opmap["SETUP_WITH"]
    JUMP_FORWARD = opmap["JUMP_FORWARD"]
    FOR_ITER = opmap["FOR_ITER"]
    SETUP_FINALLY = opmap["SETUP_FINALLY"]
    delta = (SETUP_WITH, JUMP_FORWARD, FOR_ITER, SETUP_FINALLY)
    # init state
    labels = []
    push2label = labels.append
    NOP = opmap["NOP"]
    # init
    patched_bc = []
    push2bc = patched_bc.append

    for pc, op, arg in bc:
        if op in target:
            push2label(arg)
            push2bc([pc, True, op, labels.index(arg)])
        elif op in delta:
            pos = pc + arg + 2
            push2label(pos)
            push2bc([pc, True, op, labels.index(pos)])
        else:
            push2bc([pc, False, op, arg])

    labeled_bc = []
    push2bc = labeled_bc.append

    for pc, patched, op, arg in patched_bc:
        if pc in labels:
            push2bc([labels.index(pc), pc, patched, op, arg])
        else:
            push2bc([None, pc, patched, op, arg])

    for idx, (label, pc, patched, op, arg) in enumerate(labeled_bc):
        if label is not None and op == UB:
            if idx + 1 < len(labeled_bc):
                labels[label] = labeled_bc[idx + 1][1]
                labeled_bc[idx][0] = None
                labeled_bc[idx + 1][0] = label
            else:
                labeled_bc[idx][3] = NOP

    labeled_bc = [[label, pc, patched, op, arg]
                  for label, pc, patched, op, arg in labeled_bc
                  if label is not None or op != -1]

    for idx, (label, pc, patched, op, arg) in enumerate(labeled_bc):
        if label is not None:
            labels[label] = idx

    cleaned_bc = []
    push2bc = cleaned_bc.append

    for idx, (_, __, ___, op, arg) in enumerate(labeled_bc):
        if op in target:
            push2bc([idx, op, labels[arg] * 2])
        elif op in delta:
            push2bc([idx, op, (labels[arg] - idx - 2) * 2])
        else:
            push2bc([idx, op, arg])

    return cleaned_bc


condition_nums = 30

mem_caches = {str(k): k for k in range(condition_nums)}


def demo0(value):
    return mem_caches[value]


def demo1(value: str):
    result = 0
    if value == "0":
        result = 0
    elif value == "1":
        result = 1
    elif value == "2":
        result = 2
    elif value == "3":
        result = 3
    elif value == "4":
        result = 4
    elif value == "5":
        result = 5
    elif value == "6":
        result = 6
    elif value == "7":
        result = 7
    elif value == "8":
        result = 8
    elif value == "9":
        result = 9
    elif value == "10":
        result = 10
    elif value == "11":
        result = 11
    elif value == "12":
        result = 12
    elif value == "13":
        result = 13
    elif value == "14":
        result = 14
    elif value == "15":
        result = 15
    elif value == "16":
        result = 16
    elif value == "17":
        result = 17
    elif value == "18":
        result = 18
    elif value == "19":
        result = 19
    elif value == "20":
        result = 20
    elif value == "21":
        result = 21
    elif value == "22":
        result = 22
    elif value == "23":
        result = 23
    elif value == "24":
        result = 24
    elif value == "25":
        result = 25
    elif value == "26":
        result = 26
    elif value == "27":
        result = 27
    elif value == "28":
        result = 28
    elif value == "29":
        result = 29
    return result


def example(value: str):
    global goto, label
    result = 0
    goto @ value
    label @ "0"
    result = 0
    goto @ "done"
    label @ "1"
    result = 1
    goto @ "done"
    label @ "2"
    result = 2
    goto @ "done"
    label @ "3"
    result = 3
    goto @ "done"
    label @ "4"
    result = 4
    goto @ "done"
    label @ "5"
    result = 5
    goto @ "done"
    label @ "6"
    result = 6
    goto @ "done"
    label @ "7"
    result = 7
    goto @ "done"
    label @ "8"
    result = 8
    goto @ "done"
    label @ "9"
    result = 9
    goto @ "done"
    label @ "10"
    result = 10
    goto @ "done"
    label @ "11"
    result = 11
    goto @ "done"
    label @ "12"
    result = 12
    goto @ "done"
    label @ "13"
    result = 13
    goto @ "done"
    label @ "14"
    result = 14
    goto @ "done"
    label @ "15"
    result = 15
    goto @ "done"
    label @ "16"
    result = 16
    goto @ "done"
    label @ "17"
    result = 17
    goto @ "done"
    label @ "18"
    result = 18
    goto @ "done"
    label @ "19"
    result = 19
    goto @ "done"
    label @ "20"
    result = 20
    goto @ "done"
    label @ "21"
    result = 21
    goto @ "done"
    label @ "22"
    result = 22
    goto @ "done"
    label @ "23"
    result = 23
    goto @ "done"
    label @ "24"
    result = 24
    goto @ "done"
    label @ "25"
    result = 25
    goto @ "done"
    label @ "26"
    result = 26
    goto @ "done"
    label @ "27"
    result = 27
    goto @ "done"
    label @ "28"
    result = 28
    goto @ "done"
    label @ "29"
    result = 29
    goto @ "done"
    label @ "done"
    return result


print("-" * 100)
cache_code = example.__code__
preload_caches = {}


def preload(value) -> CodeType:
    cache = preload_caches.get(value, None)
    if cache is None:
        co = cache_code
        bc = bytecode2list(co.co_code)
        bc, labels = post_process_mark_label(co, bc)
        bc = post_process_mark_goto(co, bc, labels)
        bc = hot_process_mark_fast(co, bc, labels[value])
        bc = post_process_mark_clean_nop(co, bc)
        co = co.replace(co_code=list2bytecode(bc))
        preload_caches[value] = co
        cache = co
    return cache


# preload
# for i in range(condition_nums):
#     preload(str(i))


def demo2(value):
    example.__code__ = preload(value)
    return example(value)


def test0():
    for i in range(condition_nums):
        demo0(str(i))


def test1():
    for i in range(condition_nums):
        demo1(str(i))


def test2():
    for i in range(condition_nums):
        demo2(str(i))


number = 50000
t0 = Timer("test0()", globals=globals()).timeit(number)
t1 = Timer("test1()", globals=globals()).timeit(number)
t2 = Timer("test2()", globals=globals()).timeit(number)

print(len(preload_caches))
print(t0, t1, t2)
print("-" * 100)
