import ast
import math
import operator
import random
import time
from datetime import datetime, timedelta
from itertools import permutations, product
from typing import List, Tuple, Dict, Optional

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event, MessageSegment
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import check_command_enabled, get_context, get_database

add_info('速算', '速算游戏 - 支持难度选择和排行榜\n'
         '/速算 [简单|中等|困难|地狱] - 生成对应难度题目\n'
         '/速算 [表达式] - 提交答案\n'
         '/速算 答案 - 查看当前题目答案(不获得积分)\n'
         '/速算 排行榜 [日|周|月|平均] - 查看排行榜\n'
         '/求解速算 [数字1] [数字2] [数字3] [数字4] [目标数] - 求解指定题目')

add_info('求解速算', '速算求解器 - 计算指定数字的所有解法\n'
         '用法: /求解速算 [数字1] [数字2] [数字3] [数字4] [目标数]\n'
         '显示最多20条解法，包含解法数量\n'
         '注意: 使用此命令会导致相同题目无法获得积分')

speed_calc = on_command("速算")

# 难度配置（基于解法数量）
DIFFICULTY_CONFIG = {
    '简单': {'solution_min': 10, 'solution_max': float('inf'), 'multiplier': 0.1, 'name': '简单'},
    '中等': {'solution_min': 4, 'solution_max': 9, 'multiplier': 1.0, 'name': '中等'},
    '困难': {'solution_min': 1, 'solution_max': 3, 'multiplier': 3.0, 'name': '困难'},
    '地狱': {'solution_min': 1, 'solution_max': 1, 'multiplier': 10.0, 'name': '地狱'}
}

@speed_calc.handle()
@check_command_enabled('速算')
async def handle_speed_calc(event: Event):
    user, arg_list, group = get_context(event)
    
    db = get_database('speed_calc_game')
    collection = db.get_db()
    
    # 构建查询条件（仅按用户绑定）
    query = {'user_id': user.id}
    current_problem = collection.find_one(query)
    
    # 无参数时生成中等难度题目
    if not arg_list:
        await generate_problem_with_difficulty(collection, query, '中等', user, group)
        return
    
    # 处理难度选择
    if arg_list[0] in DIFFICULTY_CONFIG:
        await generate_problem_with_difficulty(collection, query, arg_list[0], user, group)
        return
    
    # 处理排行榜查询
    if arg_list[0] == "排行榜":
        rank_type = arg_list[1] if len(arg_list) > 1 else "日"
        await show_leaderboard(rank_type, group)
        return
    
    # 处理答案查询
    if arg_list[0] == "答案":
        if not current_problem:
            await speed_calc.send("请先使用 /速算 生成题目")
            return
        
        # 标记已查看答案，不再获得积分
        collection.update_one(query, {'$set': {'answer_viewed': True}})
        
        solutions = solve_integer_results(current_problem['numbers'], current_problem['target'])
        
        if solutions:
            sample_solutions = random.sample(solutions, min(3, len(solutions)))
            answer_text = f"当前题目的答案示例：\n" + "\n".join(sample_solutions)
            answer_text += f"\n\n总共有 {len(solutions)} 种解法"
        else:
            answer_text = "未找到解法"
            
        await speed_calc.send(answer_text)
        return
    
    # 验证答案
    if not current_problem:
        await speed_calc.send("请先使用 /速算 生成题目")
        return
    
    expression = arg_list[0]
    is_valid, message, result = validate_expression_target(expression, current_problem['numbers'], current_problem['target'])
    
    if is_valid:
        # 计算积分（如果未查看答案且未使用solve作弊）
        score = 0
        if not current_problem.get('answer_viewed', False) and not current_problem.get('solve_used', False):
            solve_time = time.time() - current_problem.get('start_time', time.time())
            difficulty_multiplier = DIFFICULTY_CONFIG[current_problem.get('difficulty', '中等')]['multiplier']
            base_score = 100 / math.sqrt(max(solve_time, 1))
            score = int(base_score * difficulty_multiplier)
            
            # 保存积分记录
            await save_score_record(user, group, score, current_problem['difficulty'], solve_time)
        
        if score > 0:
            await speed_calc.send(f"🎉 回答正确！获得积分：{score}\n计算结果：{result}\n\n继续使用这些数字尝试其他解法，或使用 /速算 生成新题目")
        else:
            cheat_reason = "已查看答案" if current_problem.get('answer_viewed') else "已使用求解速算"
            await speed_calc.send(f"🎉 回答正确！但因{cheat_reason}不获得积分\n计算结果：{result}\n\n继续使用这些数字尝试其他解法，或使用 /速算 生成新题目")
    else:
        await speed_calc.send(f"❌ 错误：{message}")

def solve_integer_results(numbers: List[int], target: int = None) -> List[str]:
    """求解指定整数目标"""
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
                    # 只保留正整数结果
                    if (result > 0 and result <= 10000 and not math.isinf(result) and 
                        abs(result - round(result)) < 1e-6):
                        result = int(round(result))
                        if target is None or result == target:
                            solutions.append(expr)
                except (ZeroDivisionError, OverflowError, ValueError):
                    continue
    
    return list(set(solutions))

async def generate_problem_with_difficulty(collection, query, difficulty: str, user, group):
    """生成指定难度的题目"""
    max_attempts = 8192
    for _ in range(max_attempts):
        # 从1-20范围生成4个数字
        numbers = [random.randint(1, 25) for _ in range(4)]
        
        # 计算所有可能的整数结果及其解法数
        all_results = {}
        ops = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv}
        
        for nums in permutations(numbers):
            a, b, c, d = nums
            for op1, op2, op3 in product(ops.keys(), repeat=3):
                for expr in generate_all_expressions(a, b, c, d, op1, op2, op3):
                    try:
                        result = eval(expr)
                        if (result > 0 and result <= 100 and not math.isinf(result) and
                            abs(result - round(result)) < 1e-6):
                            result = int(round(result))
                            if result not in all_results:
                                all_results[result] = []
                            all_results[result].append(expr)
                    except (ZeroDivisionError, OverflowError, ValueError):
                        continue
        
        # 去重解法
        for result in all_results:
            all_results[result] = list(set(all_results[result]))
        
        if not all_results:
            continue
        
        # 根据难度配置选择合适的目标数
        difficulty_config = DIFFICULTY_CONFIG[difficulty]
        suitable_targets = []
        
        for result, solutions in all_results.items():
            solution_count = len(solutions)
            if (difficulty_config['solution_min'] <= solution_count <= 
                difficulty_config['solution_max']):
                suitable_targets.append((result, solution_count))
        
        if suitable_targets:
            # 随机选择一个符合难度的目标
            target, solution_count = random.choice(suitable_targets)
            
            update_data = {
                'numbers': numbers,
                'target': target,
                'difficulty': difficulty,
                'solution_count': solution_count,
                'start_time': time.time(),
                'answer_viewed': False,
                'solve_used': False,
                'user_id': user.id
            }
            collection.update_one(query, {'$set': update_data}, upsert=True)
            
            await speed_calc.send(
                f"【{difficulty}难度】新题目：\n"
                f"用 {numbers} 通过加减乘除计算出 {target}\n"
                f"解法数量：{solution_count}\n"
                f"请输入表达式（支持括号）\n"
                f"示例格式：/速算 (3+5)*(6-3)"
            )
            return
    
    # 如果生成失败，使用默认题目
    await speed_calc.send(
        f"【{difficulty}难度】题目生成失败\n"
        f"请尝试重新生成或选择其他难度"
    )

async def save_score_record(user, group, score: int, difficulty: str, solve_time: float):
    """保存积分记录"""
    score_db = get_database('speed_calc_scores')
    collection = score_db.get_db()
    
    record = {
        'user_id': user.id,
        'score': score,
        'difficulty': difficulty,
        'solve_time': solve_time,
        'timestamp': datetime.now()
    }
    
    collection.insert_one(record)

async def show_leaderboard(rank_type: str, group):
    """显示排行榜"""
    score_db = get_database('speed_calc_scores')
    collection = score_db.get_db()
    
    now = datetime.now()
    query_filter = {}
    
    # 时间过滤
    if rank_type == "日":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query_filter['timestamp'] = {'$gte': start_time}
        title = "今日积分排行榜"
    elif rank_type == "周":
        start_time = now - timedelta(days=now.weekday())
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        query_filter['timestamp'] = {'$gte': start_time}
        title = "本周积分排行榜"
    elif rank_type == "月":
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query_filter['timestamp'] = {'$gte': start_time}
        title = "本月积分排行榜"
    else:  # 平均积分
        title = "平均积分排行榜(最近100题)"
    
    if rank_type == "平均":
        # 计算平均积分（最近100题）
        pipeline = [
            {'$match': query_filter},
            {'$sort': {'timestamp': -1}},
            {'$group': {
                '_id': '$user_id',
                'records': {'$push': '$$ROOT'},
                'total_score': {'$sum': '$score'},
                'count': {'$sum': 1}
            }},
            {'$addFields': {
                'recent_100': {'$slice': ['$records', 100]},
                'recent_100_score': {
                    '$sum': {
                        '$slice': [
                            {'$map': {
                                'input': '$records',
                                'in': '$$this.score'
                            }}, 100
                        ]
                    }
                },
                'recent_100_count': {
                    '$size': {'$slice': ['$records', 100]}
                }
            }},
            {'$addFields': {
                'avg_score': {
                    '$divide': ['$recent_100_score', '$recent_100_count']
                }
            }},
            {'$sort': {'avg_score': -1}},
            {'$limit': 10}
        ]
    else:
        # 计算总积分
        pipeline = [
            {'$match': query_filter},
            {'$group': {
                '_id': '$user_id',
                'total_score': {'$sum': '$score'},
                'count': {'$sum': 1}
            }},
            {'$sort': {'total_score': -1}},
            {'$limit': 10}
        ]
    
    results = list(collection.aggregate(pipeline))
    
    if not results:
        await speed_calc.send(f"{title}\n暂无记录")
        return
    
    leaderboard_text = f"{title}\n"
    for i, result in enumerate(results, 1):
        user_id = result['_id']
        if rank_type == "平均":
            score = result['avg_score']
            count = result['recent_100_count']
            leaderboard_text += f"{i}. {user_id}: {score:.1f}分 ({count}题)\n"
        else:
            score = result['total_score']
            count = result['count']
            leaderboard_text += f"{i}. {user_id}: {score}分 ({count}题)\n"
    
    await speed_calc.send(leaderboard_text)

def validate_expression_target(expr: str, target_numbers: List[int], target: int) -> Tuple[bool, str, float]:
    """验证表达式是否正确计算出目标数"""
    try:
        # 安全检测
        check_expression_safety(expr)
        
        # 提取数字
        numbers_used = extract_numbers(expr)
        
        # 验证数字使用
        if sorted(numbers_used) != sorted(target_numbers):
            return False, "使用的数字与题目不一致", 0
        
        # 计算结果
        result = eval(expr)
        
        # 检查是否为目标数
        if abs(result - target) > 1e-6:
            return False, f"计算结果 {result} 不等于目标数 {target}", result
        
        return True, "", result
    except Exception as e:
        return False, f"无效表达式: {str(e)}", 0

def generate_all_expressions(a, b, c, d, op1, op2, op3):
    """生成所有可能的表达式"""
    return [
        f"(({a}{op1}{b}){op2}{c}){op3}{d}",
        f"({a}{op1}({b}{op2}{c})){op3}{d}",
        f"{a}{op1}(({b}{op2}{c}){op3}{d})",
        f"{a}{op1}({b}{op2}({c}{op3}{d}))",
        f"({a}{op1}{b}){op2}({c}{op3}{d})"
    ]



def extract_numbers(expr: str) -> List[float]:
    """从表达式中提取数字"""
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError("语法错误") from e
    
    numbers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            numbers.append(node.value)
    return numbers

def check_expression_safety(expr: str):
    """检查表达式安全性"""
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

# 求解速算命令
solve_speed_calc = on_command('求解速算')

@solve_speed_calc.handle()
@check_command_enabled('求解速算')
async def solve_speed_calc_handler(event: Event):
    user, args, group = get_context(event)
    
    if len(args) < 5:
        await solve_speed_calc.send("用法：/求解速算 [数字1] [数字2] [数字3] [数字4] [目标数]")
        return
    
    try:
        numbers = [int(args[i]) for i in range(4)]
        target = int(args[4])
    except ValueError:
        await solve_speed_calc.send("请输入有效的数字")
        return
    
    # 标记当前题目已使用求解（反作弊）
    db = get_database('speed_calc_game')
    collection = db.get_db()
    query = {'user_id': user.id}
    current_problem = collection.find_one(query)
    
    if (current_problem and 
        sorted(current_problem.get('numbers', [])) == sorted(numbers) and
        current_problem.get('target') == target):
        collection.update_one(query, {'$set': {'solve_used': True}})
    
    # 求解
    solutions = solve_integer_results(numbers, target)
    
    if not solutions:
        await solve_speed_calc.send(f"数字 {numbers} 无法得到 {target}")
        return
    
    # 显示最多20条结果
    display_solutions = solutions[:20]
    result_text = f"数字 {numbers} 计算 {target} 的解法：\n"
    result_text += f"解法总数：{len(solutions)} 种\n\n"
    
    for i, sol in enumerate(display_solutions, 1):
        result_text += f"{i}. {sol}\n"
    
    if len(solutions) > 20:
        result_text += f"\n... 还有 {len(solutions) - 20} 种解法未显示"
    
    await solve_speed_calc.send(result_text)