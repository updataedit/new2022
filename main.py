#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商户升级自动化脚本 - Python Playwright 版本
原版本: Tampermonkey userscript (main.js)

使用方式:
  1. 安装依赖: pip install -r requirements.txt
  2. 安装浏览器: playwright install chromium
  3. 创建 batch_input.txt，每行一条记录
  4. 运行: python main.py

batch_input.txt 格式:
  旧格式: 环境 账号 版本 [额外信息]
  新格式: 公司名称 环境 账号 版本 [额外信息]

示例:
  波罗1 user123 5.55
  某公司 波罗2 user456 5.56
  企信宝 user789 5.57
"""

import asyncio
import json
import os
import re
import sys
from urllib.parse import quote

import requests
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

# ==================== 配置 ====================

FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/363fa124-9d50-46e3-b52b-ebe5532c969a'
API_BASE_URL = 'http://172.16.1.7:5001'
FEISHU_OPENID = 'ou_651d918678c1c4b5ca07906cacd4bd25'
BASE_URL = 'http://m.apollo.****.com'

TYPE_MAP = {
    "企信宝": "qw", "波罗1": "gw", "波罗2": "gw", "波罗3": "gw",
    "波罗4": "gw", "波罗5": "gw", "杭州微客": "gw", "波罗6": "gw"
}
ENV_MAP = {
    "企信宝": "鹊桥", "波罗1": "IDC", "波罗2": "阿里云1", "波罗3": "阿里云2",
    "波罗4": "阿里云3", "波罗5": "阿里云4", "杭州微客": "阿里云4", "波罗6": "阿里云5"
}

CONFIG_FILE = 'config.json'
BATCH_INPUT_FILE = 'batch_input.txt'


# ==================== 工具函数 ====================

def send_feishu(message: str):
    """发送飞书消息通知"""
    print(f'[飞书] 发送消息: {message}')
    try:
        resp = requests.post(
            FEISHU_WEBHOOK,
            json={'msg_type': 'text', 'content': {'text': message}},
            timeout=10
        )
        print(f'[飞书] 响应状态: {resp.status_code}')
    except Exception as e:
        print(f'[飞书] 发送失败: {e}')


def query_shop_id(env: str, account: str) -> str:
    """通过 API 查询商户店铺 ID"""
    url = f'{API_BASE_URL}/api/shopid?env={quote(env)}&user_account={quote(account)}'
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            shop_id = data.get('shopid', '')
            if shop_id and shop_id != '查询失败':
                return shop_id
            else:
                send_feishu(f'商户ID查询失败，需要手动查询\n{env} {account}')
                return '查询失败'
        return '请求失败'
    except Exception as e:
        print(f'[API] 查询失败 [{env} {account}]: {e}')
        return '请求失败'


def load_config() -> dict:
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config: dict):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ==================== 页面操作 ====================

async def perform_actions_by_xpath(
    page: Page,
    xpath: str,
    value: str = None,
    click: bool = True,
    iframe_src: str = None,
    isadd: bool = False
):
    """
    通过 XPath 定位元素并执行操作，对应 JS 版本的 performActionsByXPath。

    参数:
        page      - Playwright Page 对象
        xpath     - XPath 表达式
        value     - 要填入的值，None 则不填
        click     - 是否点击元素
        iframe_src - 元素所在 iframe 的 src 关键字，None 表示主页面
        isadd     - True 时追加到已有值，False 时替换
    """
    try:
        if iframe_src:
            frame_locator = page.frame_locator(f'iframe[src*="{iframe_src}"]')
            locator = frame_locator.locator(f'xpath={xpath}')
        else:
            locator = page.locator(f'xpath={xpath}')

        await locator.wait_for(state='attached', timeout=5000)

        if value is not None:
            if isadd:
                existing = await locator.input_value()
                value = (existing or '') + value
            await locator.fill(value)
            display_val = value[:60] + '...' if len(value) > 60 else value
            print(f'  [设置值] {display_val}')

        if click:
            await locator.click()
            print(f'  [点击] {xpath[:80]}')

    except PlaywrightTimeoutError:
        print(f'  [跳过] 元素未找到: {xpath[:80]}')
    except Exception as e:
        print(f'  [错误] {xpath[:80]} -> {e}')


async def do_login(page: Page, account_password: str):
    """执行登录"""
    if '|' not in account_password:
        print('[登录] 账号密码格式错误，应为: 账号|密码')
        return

    username, password = account_password.split('|', 1)
    print(f'[登录] 账号: {username}')

    await perform_actions_by_xpath(page, '/html/body/div[1]/main/form/div[1]/input', value=username, click=True)
    await perform_actions_by_xpath(page, '/html/body/div[1]/main/form/div[2]/input', value=password, click=True)
    await perform_actions_by_xpath(page, '/html/body/div[1]/main/form/button', click=True)
    await asyncio.sleep(0.5)
    # 处理已有其他设备登录的确认弹窗
    await perform_actions_by_xpath(page, '/html/body/div[3]/div/div/div[2]/button', click=True)


async def do_search(page: Page, env_info: str):
    """填入环境信息并搜索"""
    print(f'[搜索] 环境信息: {env_info}')
    await perform_actions_by_xpath(page, '//*[@id="mobile_package_name"]', value=env_info, click=True)
    await perform_actions_by_xpath(page, '/html/body/div/main/form/button', click=True)


async def execute_actions(
    page: Page,
    upgrade_info: str,
    publish_type: str,
    original_info: str = '',
    complex_value: str = ''
):
    """
    遍历搜索结果表格（最多 11 行），对每行执行：
      点击编辑按钮 -> 在 iframe 中填入升级信息 -> 提交 -> 关闭对话框
    完成后发送飞书通知。
    """
    # 根据升级类型确定 iframe 中的输入框 XPath
    type_xpath_map = {
        'gw':   '//*[@id="EditInput_merchantids_white_list"]',
        'qw':   '//*[@id="EditInput_wwmerchantids_white_list"]',
        'imei': '//*[@id="EditInput_imeis_white_list"]',
    }
    target_input_xpath = type_xpath_map.get(publish_type, type_xpath_map['gw'])

    # 表格最多 11 行的编辑按钮
    row_xpaths = [
        f'/html/body/div/main/table/tbody/tr[{i}]/td[8]/button[1]'
        for i in range(1, 12)
    ]

    submit_xpath = "//button[text()='提交']"
    close_dialog_xpath = '//*[@id="editDialog"]/div/div/div[1]/button'

    for i, row_xpath in enumerate(row_xpaths, 1):
        print(f'\n--- 处理第 {i} 行 ---')

        await asyncio.sleep(1.5)
        # 点击该行的编辑按钮（主页面）
        await perform_actions_by_xpath(page, row_xpath, click=True)

        await asyncio.sleep(1.5)
        # 在 iframe 中追加升级信息并点击（聚焦）
        await perform_actions_by_xpath(
            page, target_input_xpath,
            value=upgrade_info, click=True,
            iframe_src='Edit?', isadd=True
        )

        await asyncio.sleep(3)
        # 在 iframe 中点击提交
        await perform_actions_by_xpath(
            page, submit_xpath,
            click=True, iframe_src='Edit?'
        )

        await asyncio.sleep(1.5)
        # 关闭对话框（主页面）
        await perform_actions_by_xpath(page, close_dialog_xpath, click=True)

    # 发送飞书完成通知
    info = original_info.replace('\t', '--') if original_info else ''
    if info.strip():
        send_feishu(f'该商户已升级完成：\n{info}')
    else:
        send_feishu(f'主账号解析失败，升级完成信息：\n{complex_value}')


# ==================== 批量处理逻辑 ====================

def parse_batch_input(input_text: str) -> dict:
    """
    解析批量输入文本，支持两种格式：
      旧格式: 环境 账号 版本 [额外信息]
      新格式: 公司名称 环境 账号 版本 [额外信息]

    返回结构:
      {
        env: {
          version: {
            items: [{account, shopId, needsQuery, originalLine}],
            extraValues: [...],
            status: 'pending'
          }
        }
      }
    """
    env_results = {}

    for line in input_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        parts = re.split(r'\s+', line)

        # 判断格式
        if parts[0] in ENV_MAP or parts[0] in TYPE_MAP:
            # 旧格式: 环境 账号 版本 [额外]
            env     = parts[0]
            account = parts[1] if len(parts) > 1 else ''
            version = parts[2] if len(parts) > 2 else ''
            extra   = parts[3] if len(parts) > 3 else None
        elif len(parts) >= 4 and (parts[1] in ENV_MAP or parts[1] in TYPE_MAP):
            # 新格式: 公司名称 环境 账号 版本 [额外]
            env     = parts[1]
            account = parts[2]
            version = parts[3]
            extra   = parts[4] if len(parts) > 4 else None
        else:
            # 默认按旧格式处理
            env     = parts[0]
            account = parts[1] if len(parts) > 1 else ''
            version = parts[2] if len(parts) > 2 else ''
            extra   = parts[3] if len(parts) > 3 else None

        if not env or not account:
            continue

        env_results.setdefault(env, {})
        env_results[env].setdefault(version, {
            'items': [],
            'extraValues': [],
            'status': 'pending'
        })

        if extra:
            env_results[env][version]['extraValues'].append(extra)

        env_results[env][version]['items'].append({
            'account':      account,
            'shopId':       extra,       # 有额外信息则直接作为 shopId
            'needsQuery':   extra is None,
            'originalLine': line
        })

    return env_results


def query_all_shop_ids(env_results: dict) -> dict:
    """批量查询所有需要查询的店铺 ID"""
    for env in env_results:
        for version in env_results[env]:
            group = env_results[env][version]
            for item in group['items']:
                if item['needsQuery']:
                    print(f'  查询: {env} / {item["account"]}')
                    item['shopId'] = query_shop_id(env, item['account'])
    return env_results


def build_task_params(env: str, version: str, group: dict) -> dict:
    """
    从任务组数据构建执行所需参数，对应 JS 中 runTask 里的格式化逻辑。

    返回:
      {env_info, upgrade_info, publish_type, original_lines, complex_text}
    """
    mapped_env = ENV_MAP.get(env, env)

    valid_shop_ids = [
        item['shopId'] for item in group['items']
        if item.get('shopId') and item['shopId'] not in ('查询失败', '请求失败')
    ]
    original_lines = '\n'.join(
        item['originalLine'] for item in group['items']
        if item.get('shopId') and item['shopId'] not in ('查询失败', '请求失败')
    )

    has_extra = bool(group.get('extraValues'))

    if has_extra:
        publish_type = 'imei'
        complex_text = f'IMEI】_v{version}|,{",".join(valid_shop_ids)}|imei'
    else:
        publish_type = TYPE_MAP.get(env, 'gw')
        complex_text = f'{mapped_env}】_v{version}|,{",".join(valid_shop_ids)}|{publish_type}'

    # complex_text 格式: "env_info|upgrade_info|type"
    parts = complex_text.split('|')
    env_info = parts[0]
    upgrade_info = parts[1]   # 以逗号开头的 shopId 列表

    return {
        'env_info':      env_info,
        'upgrade_info':  upgrade_info,
        'publish_type':  publish_type,
        'original_lines': original_lines,
        'complex_text':  complex_text
    }


async def run_task(page: Page, env: str, version: str, group: dict):
    """执行单个升级任务（搜索 + 升级操作）"""
    params = build_task_params(env, version, group)

    print(f'\n{"=" * 50}')
    print(f'任务: {env} - v{version}')
    print(f'环境信息: {params["env_info"]}')
    print(f'升级信息: {params["upgrade_info"]}')
    print(f'类型: {params["publish_type"]}')
    print(f'{"=" * 50}')

    # 1. 搜索
    await do_search(page, params['env_info'])
    await asyncio.sleep(3)

    # 2. 执行升级
    await execute_actions(
        page,
        params['upgrade_info'],
        params['publish_type'],
        params['original_lines'],
        params['complex_text']
    )

    group['status'] = 'completed'


# ==================== 主入口 ====================

async def main():
    config = load_config()

    account_password = config.get('account_password', '')
    batch_input_file = config.get('batch_input_file', BATCH_INPUT_FILE)
    headless = config.get('headless', False)

    # 交互式获取账号密码
    if not account_password:
        account_password = input('请输入账号密码 (格式: 账号|密码): ').strip()
        if account_password:
            save_it = input('是否保存到 config.json? (y/N): ').strip().lower()
            if save_it == 'y':
                config['account_password'] = account_password
                save_config(config)

    # 检查批量输入文件
    if not os.path.exists(batch_input_file):
        print(f'\n未找到批量输入文件: {batch_input_file}')
        print('请创建该文件，格式说明:')
        print('  旧格式: 环境 账号 版本 [额外信息]')
        print('  新格式: 公司名称 环境 账号 版本 [额外信息]')
        print('\n示例内容:')
        print('  波罗1 user123 5.55')
        print('  某公司 波罗2 user456 5.56')
        sys.exit(1)

    with open(batch_input_file, 'r', encoding='utf-8') as f:
        batch_input = f.read()

    # 解析批量输入
    print('\n解析批量数据...')
    env_results = parse_batch_input(batch_input)
    if not env_results:
        print('未解析到有效数据，请检查输入格式')
        sys.exit(1)

    # 查询所有店铺 ID
    print('\n查询店铺 ID...')
    env_results = query_all_shop_ids(env_results)

    # 汇总任务列表
    tasks = []
    print('\n任务列表:')
    for env in env_results:
        for version in env_results[env]:
            group = env_results[env][version]
            valid_count = sum(
                1 for item in group['items']
                if item.get('shopId') and item['shopId'] not in ('查询失败', '请求失败')
            )
            tasks.append((env, version, group, valid_count))
            print(f'  [{valid_count} 个有效] {env} - v{version}')

    print(f'\n共 {len(tasks)} 个任务。按 Enter 开始执行，Ctrl+C 取消...')
    input()

    # 启动浏览器
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 登录
            print('\n导航到登录页...')
            await page.goto(f'{BASE_URL}/Home/Login')
            await asyncio.sleep(1)
            await do_login(page, account_password)
            await asyncio.sleep(2)

            # 导航到升级页面
            publish_url = (
                f'{BASE_URL}/Publish/Page'
                '?publish_info_title=&range_type=0&update_type=0&page_size=12'
            )
            await page.goto(publish_url)
            await asyncio.sleep(2)

            # 依次执行所有任务
            for env, version, group, valid_count in tasks:
                if group.get('status') == 'completed':
                    print(f'\n[跳过] 已完成: {env} - v{version}')
                    continue
                if valid_count == 0:
                    print(f'\n[跳过] 无有效商户: {env} - v{version}')
                    continue

                await run_task(page, env, version, group)
                print(f'\n[完成] {env} - v{version}')
                await asyncio.sleep(2)

            send_feishu('该批次任务已执行完成！')
            print('\n所有批量任务已完成！')

        except KeyboardInterrupt:
            print('\n用户中断执行')
        except Exception as e:
            print(f'\n执行出错: {e}')
            raise
        finally:
            input('\n按 Enter 关闭浏览器...')
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
