#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商户升级自动化 - FastAPI 接口服务

运行:
  uvicorn api:app --host 0.0.0.0 --port 8000 --reload

接口列表:
  POST   /jobs            提交批量升级任务
  GET    /jobs            列出所有任务
  GET    /jobs/{job_id}   查询任务状态
  POST   /jobs/{job_id}/stop  停止任务
  DELETE /jobs/{job_id}   删除已完成任务记录
  POST   /shopid          查询单个商户店铺 ID
  GET    /health          健康检查
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright

from main import (
    BASE_URL,
    build_task_params,
    do_login,
    execute_actions,
    do_search,
    load_config,
    parse_batch_input,
    query_all_shop_ids,
    query_shop_id,
    run_task,
    send_feishu,
)

# ==================== 应用初始化 ====================

app = FastAPI(
    title="商户升级自动化 API",
    version="1.0.0",
    description="通过 Playwright 驱动浏览器执行商户升级操作的 REST 接口服务",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 任务存储（内存），job_id -> dict
jobs: dict[str, dict] = {}

# 同一时间只允许一个浏览器实例运行，避免并发冲突
_browser_semaphore = asyncio.Semaphore(1)


# ==================== 数据模型 ====================

class BatchJobRequest(BaseModel):
    batch_text: str
    """批量输入文本，每行一条记录（格式同 batch_input.txt）"""

    account_password: Optional[str] = None
    """账号|密码，为空时从 config.json 读取"""

    headless: bool = False
    """是否以无头模式运行浏览器"""


class ShopIdRequest(BaseModel):
    env: str
    account: str


class TaskInfo(BaseModel):
    env: str
    version: str
    valid_count: int
    status: str   # pending / running / completed / failed / skipped
    error: Optional[str] = None


class JobStatus(BaseModel):
    job_id: str
    status: str   # queued / running / completed / failed / stopped
    created_at: str
    updated_at: str
    tasks: List[TaskInfo]
    error: Optional[str] = None


# ==================== 内部工具 ====================

def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _job_to_response(job_id: str) -> JobStatus:
    job = jobs[job_id]
    task_infos = [
        TaskInfo(
            env=t['env'],
            version=t['version'],
            valid_count=t['valid_count'],
            status=t['status'],
            error=t.get('error'),
        )
        for t in job.get('task_list', [])
    ]
    return JobStatus(
        job_id=job_id,
        status=job['status'],
        created_at=job['created_at'],
        updated_at=job['updated_at'],
        tasks=task_infos,
        error=job.get('error'),
    )


# ==================== 后台执行逻辑 ====================

async def _execute_job(job_id: str, batch_text: str, account_password: str, headless: bool):
    """
    后台任务：解析数据 -> 查询 shopId -> 启动浏览器 -> 依次执行升级。
    通过 _browser_semaphore 保证同一时间只有一个任务在操作浏览器。
    """
    job = jobs[job_id]

    async with _browser_semaphore:
        job['status'] = 'running'
        job['updated_at'] = _now()

        try:
            # 1. 解析批量文本
            env_results = parse_batch_input(batch_text)
            if not env_results:
                raise ValueError('未解析到有效任务数据，请检查输入格式')

            # 2. 查询 shopId（同步 IO，在当前协程中执行）
            env_results = await asyncio.to_thread(query_all_shop_ids, env_results)

            # 3. 构建任务列表并写入 job 记录（供状态查询使用）
            task_list: list[dict] = []
            for env in env_results:
                for version in env_results[env]:
                    group = env_results[env][version]
                    valid_count = sum(
                        1 for item in group['items']
                        if item.get('shopId') and str(item['shopId']) not in ('查询失败', '请求失败')
                    )
                    task_list.append({
                        'env': env,
                        'version': version,
                        'group': group,
                        'valid_count': valid_count,
                        'status': 'pending',
                        'error': None,
                    })
            job['task_list'] = task_list
            job['updated_at'] = _now()

            # 4. 启动浏览器并执行
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                page = await (await browser.new_context()).new_page()

                try:
                    # 登录
                    await page.goto(f'{BASE_URL}/Home/Login')
                    await asyncio.sleep(1)
                    await do_login(page, account_password)
                    await asyncio.sleep(2)

                    # 导航到升级页面
                    await page.goto(
                        f'{BASE_URL}/Publish/Page'
                        '?publish_info_title=&range_type=0&update_type=0&page_size=12'
                    )
                    await asyncio.sleep(2)

                    # 依次执行每个子任务
                    for task in task_list:
                        if job.get('stop_requested'):
                            task['status'] = 'skipped'
                            continue

                        if task['valid_count'] == 0:
                            task['status'] = 'skipped'
                            job['updated_at'] = _now()
                            continue

                        task['status'] = 'running'
                        job['updated_at'] = _now()

                        try:
                            await run_task(page, task['env'], task['version'], task['group'])
                            task['status'] = 'completed'
                        except Exception as e:
                            task['status'] = 'failed'
                            task['error'] = str(e)

                        job['updated_at'] = _now()
                        await asyncio.sleep(2)

                finally:
                    await browser.close()

            # 5. 结束处理
            if job.get('stop_requested'):
                job['status'] = 'stopped'
            else:
                send_feishu('该批次任务已执行完成！')
                job['status'] = 'completed'

        except Exception as e:
            job['status'] = 'failed'
            job['error'] = str(e)

        job['updated_at'] = _now()


# ==================== API 路由 ====================

@app.post(
    '/jobs',
    response_model=JobStatus,
    status_code=202,
    summary='提交批量升级任务',
    description=(
        '接收批量文本，异步执行商户升级流程，立即返回 job_id。\n\n'
        '**batch_text 格式**（每行一条，空格分隔）：\n'
        '- 旧格式：`环境 账号 版本 [额外信息]`\n'
        '- 新格式：`公司名称 环境 账号 版本 [额外信息]`\n\n'
        '**示例**：\n'
        '```\n波罗1 user123 5.55\n某公司 波罗2 user456 5.56\n```'
    ),
)
async def create_job(req: BatchJobRequest):
    # 获取账号密码
    account_password = req.account_password
    if not account_password:
        account_password = load_config().get('account_password', '')
    if not account_password:
        raise HTTPException(
            status_code=400,
            detail='缺少账号密码，请在请求体中提供 account_password 或在 config.json 中配置',
        )

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {
        'status': 'queued',
        'created_at': _now(),
        'updated_at': _now(),
        'task_list': [],
        'error': None,
        'stop_requested': False,
    }

    # 使用 asyncio.create_task 让任务真正在后台运行，与请求生命周期解耦
    task = asyncio.create_task(
        _execute_job(job_id, req.batch_text, account_password, req.headless)
    )
    # 保留引用防止被 GC 回收
    jobs[job_id]['_task'] = task

    return _job_to_response(job_id)


@app.get(
    '/jobs',
    response_model=List[JobStatus],
    summary='列出所有任务',
)
async def list_jobs():
    return [_job_to_response(jid) for jid in jobs]


@app.get(
    '/jobs/{job_id}',
    response_model=JobStatus,
    summary='查询任务状态',
)
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail='任务不存在')
    return _job_to_response(job_id)


@app.post(
    '/jobs/{job_id}/stop',
    summary='停止任务',
    description='向任务发送停止信号，当前正在执行的子任务完成后停止。',
)
async def stop_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail='任务不存在')
    job = jobs[job_id]
    if job['status'] not in ('queued', 'running'):
        raise HTTPException(status_code=400, detail=f'任务当前状态为 {job["status"]}，无法停止')
    job['stop_requested'] = True
    return {'ok': True, 'message': '停止信号已发送，当前子任务完成后将停止'}


@app.delete(
    '/jobs/{job_id}',
    summary='删除任务记录',
    description='仅允许删除已完成/失败/已停止的任务记录。',
)
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail='任务不存在')
    if jobs[job_id]['status'] in ('queued', 'running'):
        raise HTTPException(status_code=400, detail='任务仍在运行，请先停止再删除')
    del jobs[job_id]
    return {'ok': True}


@app.post(
    '/shopid',
    summary='查询单个商户店铺 ID',
    description='直接调用内部 API 查询商户 shopId，不启动浏览器。',
)
async def get_shop_id(req: ShopIdRequest):
    result = await asyncio.to_thread(query_shop_id, req.env, req.account)
    return {'shopid': result, 'env': req.env, 'account': req.account}


@app.get('/health', summary='健康检查')
async def health():
    running = sum(1 for j in jobs.values() if j['status'] == 'running')
    queued  = sum(1 for j in jobs.values() if j['status'] == 'queued')
    return {'status': 'ok', 'jobs_running': running, 'jobs_queued': queued}
