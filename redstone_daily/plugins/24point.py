import ast
import math
import operator
import random
from itertools import permutations, product

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event, MessageSegment
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import check_command_enabled, get_context, get_database

add_info('24', '生成可解24点题目，提交答案或获取答案 参数:\n /24 [expr/答案]')

game_24 = on_command("24")


@game_24.handle()
@check_command_enabled('24')
async def handle_24(event: Event):
    user, arg_list, group = get_context(event)

    db = get_database('24_game')
    collection = db.get_db()

    # 构建查询条件
    query = {'group_id': group.id} if group else {'user_id': user.id}
    current_problem = collection.find_one(query)

    # 无参数时生成新题目
    if not arg_list:
        numbers, solution = generate_24_problem()
        update_data = {
            'numbers': numbers,
            'solution': solution,
            'group_id': group.id if group else None,
            'user_id': user.id if not group else None
        }
        collection.update_one(query, {'$set': update_data}, upsert=True)
        await game_24.send(f"新题目：用 {numbers} 通过加减乘除计算24，请输入表达式（支持括号）。\n示例格式：/24 (3+5)*(6-3)")
        return

    # 处理特殊指令
    if arg_list[0] == "答案":
        if not current_problem:
            await game_24.send("请先使用 /24 生成题目")
            return
        await game_24.send(f"当前题目的答案是：{current_problem['solution']}")
        return

    # 验证答案
    if not current_problem:
        await game_24.send("请先使用 /24 生成题目")
        return

    expression = arg_list[0]
    is_valid, message = validate_expression(expression, current_problem['numbers'])
    if is_valid:
        await game_24.send("🎉 回答正确！")
    else:
        await game_24.send(f"❌ 错误：{message}")


def generate_24_problem():
    while True:
        numbers = [random.randint(1, 13) for _ in range(4)]
        solutions = solve_24(numbers)
        if solutions:
            return numbers, random.choice(solutions)


def solve_24(numbers):
    ops = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv}
    solutions = []

    # 遍历所有数字排列组合
    for nums in permutations(numbers):
        a, b, c, d = nums

        # 遍历所有运算符组合
        for op1, op2, op3 in product(ops.keys(), repeat=3):
            # 尝试不同运算顺序
            for expr in generate_all_expressions(a, b, c, d, op1, op2, op3):
                try:
                    result = eval(expr)
                    if math.isclose(result, 24, rel_tol=1e-6):
                        solutions.append(expr)
                except ZeroDivisionError:
                    continue

    return list(set(solutions))


def generate_all_expressions(a, b, c, d, op1, op2, op3):
    return [
        f"(({a}{op1}{b}){op2}{c}){op3}{d}",
        f"({a}{op1}({b}{op2}{c})){op3}{d}",
        f"{a}{op1}(({b}{op2}{c}){op3}{d})",
        f"{a}{op1}({b}{op2}({c}{op3}{d}))",
        f"({a}{op1}{b}){op2}({c}{op3}{d})"
    ]


def validate_expression(expr, target_numbers):
    try:
        # 安全检测
        check_expression_safety(expr)

        # 提取数字
        numbers_used = extract_numbers(expr)

        # 验证数字使用
        if sorted(numbers_used) != sorted(target_numbers):
            return False, "使用的数字与题目不一致"

        # 计算结果
        result = eval(expr)
        if not math.isclose(result, 24, rel_tol=1e-6):
            return False, "计算结果不等于24"

        return True, ""
    except Exception as e:
        return False, f"无效表达式: {str(e)}"


def extract_numbers(expr):
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError("语法错误") from e

    numbers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            numbers.append(node.value)
    return numbers


def check_expression_safety(expr):
    allowed_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                     ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)

    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError("语法错误") from e

    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError("检测到非法操作符或语法")
        if isinstance(node, ast.UnaryOp) and not isinstance(node.op, (ast.USub, ast.UAdd)):
            raise ValueError("不支持的单目运算符")
