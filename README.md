// ==UserScript==
// @name         商户升级
// @namespace    http://tampermonkey.net/
// @version      0.3
// @description  工作手机升级页面 v1.0 (已合并批量处理功能)
// @match        http://m.apollo.wechatgj.com/Publish/Page*
// @match        http://m.apollo.wechatgj.com/Home/Login*
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// ==/UserScript==

(function() {
    'use strict';

    const FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/363fa124-9d50-46e3-b52b-ebe5532c969a';
    // 如果API不在当前域名下，请在此配置完整URL，例如 'http://your-api-server.com'
    const API_BASE_URL = 'http://172.16.1.7:5001';
    const feishu_openid = 'ou_651d918678c1c4b5ca07906cacd4bd25';
    function sendFeishu(message) {
        return new Promise((resolve, reject) => {
            console.log('准备发送飞书消息:', message);
            GM_xmlhttpRequest({
                method: 'POST',
                url: FEISHU_WEBHOOK,
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify({
                    msg_type: 'text',
                    content: { text: message }
                }),
                onload: function(response) {
                    console.log('飞书发送响应:', response.status, response.responseText);
                    if (response.status === 200) {
                        resolve(response);
                    } else {
                        console.error('飞书发送失败，状态码:', response.status);
                        // 即使失败也 resolve，避免阻塞后续流程，但记录错误
                        resolve(response);
                    }
                },
                onerror: function(err) {
                    console.error('飞书发送网络错误:', err);
                    resolve(err); // 同样 resolve 避免阻塞
                }
            });
        });
    }

    // 更新 localStorage 中的值
    function updateLocalStorage() {
      localStorage.setItem('env_info_input', env_info_input.value);
      localStorage.setItem('mdid_info_input', mdid_info_input.value);
      localStorage.setItem('complex_input', complex_input.value);
      const selectedRadio1 = document.querySelector('input[name="radio"]:checked');
      if (selectedRadio1) {
        localStorage.setItem('publish_type', selectedRadio1.value);
      }
    }

    const url = new URL(window.location.href);
    if (!url.searchParams.has('page_size')) {
        url.searchParams.set('page_size', '12');
        window.location.replace(url.toString());
    }

    // 创建表单
    const form = document.createElement('form');
    form.style.zoom = '0.8'; // 缩放
    form.style.position = 'fixed';
    form.style.top = '10px';
    form.style.right = '10px';
    form.style.padding = '20px';
    form.style.border = '1px solid #ddd';
    form.style.backgroundColor = '#fff';
    form.style.borderRadius = '8px';
    form.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
    form.style.zIndex = '10000';
    // form.style.maxHeight = '90vh';
    form.style.overflowY = 'auto';
    form.style.width = '350px'; // 稍微加宽一点以容纳更多内容

    // ==================== 批量处理区域 (新功能) ====================
    const batchContainer = document.createElement('div');
    batchContainer.style.marginBottom = '20px';
    batchContainer.style.borderBottom = '1px solid #eee';
    batchContainer.style.paddingBottom = '10px';

    const batchTitle = document.createElement('h3');
    batchTitle.textContent = '1. 批量数据处理';
    batchTitle.style.fontSize = '16px';
    batchTitle.style.margin = '0 0 10px 0';
    batchContainer.appendChild(batchTitle);

    // 映射表移动到外层供全局使用
    const typeMap = {
        "企信宝": "qw", "波罗1": "gw", "波罗2": "gw", "波罗3": "gw",
        "波罗4": "gw", "波罗5": "gw", "杭州微客": "gw", "波罗6": "gw"
    };
    const envMap = {
        "企信宝": "鹊桥", "波罗1": "IDC", "波罗2": "阿里云1", "波罗3": "阿里云2",
        "波罗4": "阿里云3", "波罗5": "阿里云4", "杭州微客": "阿里云4", "波罗6": "阿里云5"
    };

    const batchInput = document.createElement('textarea');
    batchInput.placeholder = '在此粘贴批量数据\n格式：公司名称 环境 账号 版本 [额外信息]';
    batchInput.style.width = '100%';
    batchInput.style.height = '80px';
    batchInput.style.marginBottom = '10px';
    batchInput.style.padding = '8px';
    batchInput.style.border = '1px solid #ccc';
    batchInput.style.borderRadius = '4px';
    batchInput.style.resize = 'vertical';
    // 自动保存批量输入内容
    batchInput.addEventListener('input', () => {
        localStorage.setItem('batch_input_data', batchInput.value);
    });
    batchContainer.appendChild(batchInput);
    // 添加清空任务按钮
    const clearTasksBtn = createButton('4清空', () => {
        localStorage.removeItem('batch_task_results');
        taskList.innerHTML = '';
        batchInput.value = '';
        localStorage.removeItem('batch_input_data');
        sessionStorage.removeItem('current_task_original_info');
    });
    clearTasksBtn.style.width = '40%';
    clearTasksBtn.style.backgroundColor = '#dc3545'; // 红色
    clearTasksBtn.onmouseover = function() {
        clearTasksBtn.style.backgroundColor = '#c82333';
    };
    clearTasksBtn.onmouseout = function() {
        clearTasksBtn.style.backgroundColor = '#dc3545';
    };
    batchContainer.appendChild(clearTasksBtn);

    // 添加生成任务按钮
    const processBtn = createButton('1生成', processBatchData);
    processBtn.style.width = '40%'; // 调整宽度
    batchContainer.appendChild(processBtn);

    // 添加停止执行按钮
    const stopBatchBtn = createButton('3停止', stopBatchRun);
    stopBatchBtn.style.width = '40%';
    stopBatchBtn.style.backgroundColor = '#ffc107';
    stopBatchBtn.style.color = '#000';
    stopBatchBtn.onmouseover = function() { stopBatchBtn.style.backgroundColor = '#e0a800'; };
    stopBatchBtn.onmouseout = function() { stopBatchBtn.style.backgroundColor = '#ffc107'; };
    batchContainer.appendChild(stopBatchBtn);

    // 添加批量执行按钮
    const startBatchBtn = createButton('2执行', startBatchRun);
    startBatchBtn.style.width = '40%';
    startBatchBtn.style.backgroundColor = '#007bff';
    startBatchBtn.onmouseover = function() { startBatchBtn.style.backgroundColor = '#0056b3'; };
    startBatchBtn.onmouseout = function() { startBatchBtn.style.backgroundColor = '#007bff'; };
    batchContainer.appendChild(startBatchBtn);




    const taskList = document.createElement('div');
    taskList.id = 'task-list';
    taskList.style.marginTop = '10px';
    batchContainer.appendChild(taskList);

    form.appendChild(batchContainer);

    // ==================== 自动恢复逻辑 ====================
    // 0. 恢复输入框内容
    const savedBatchInput = localStorage.getItem('batch_input_data');
    if (savedBatchInput) {
        batchInput.value = savedBatchInput;
    }

    // 1. 恢复任务列表
    const savedTaskResults = localStorage.getItem('batch_task_results');
    if (savedTaskResults) {
        try {
            const results = JSON.parse(savedTaskResults);
            renderTaskList(results);
        } catch (e) {
            console.error('恢复任务列表失败', e);
        }
    }

    // 2. 检查自动执行状态 (跨页面刷新)
    const autoRunState = sessionStorage.getItem('auto_run_state');
    if (autoRunState === 'searching') {
        console.log('检测到自动执行状态：搜索完成，准备执行操作');

        // 显示提示
        const statusTip = document.createElement('div');
        statusTip.textContent = '自动执行中：搜索完成，3秒后执行升级操作...';
        statusTip.style.backgroundColor = '#d4edda';
        statusTip.style.color = '#155724';
        statusTip.style.padding = '10px';
        statusTip.style.marginBottom = '10px';
        statusTip.style.borderRadius = '4px';
        statusTip.style.textAlign = 'center';
        form.insertBefore(statusTip, form.firstChild);

        // 延迟执行
        setTimeout(async () => {
            try {
                // 清除状态，防止死循环 (如果executeActions刷新页面，需要更复杂的逻辑，但目前假设它不刷新或刷新意味着结束)
                sessionStorage.removeItem('auto_run_state');

                // 滚动到底部
                executeButton.scrollIntoView({ behavior: 'smooth' });

                await executeActions();

                statusTip.textContent = '自动执行完成！';
                setTimeout(() => statusTip.remove(), 3000);
            } catch (err) {
                console.error('自动执行第二阶段出错:', err);
                statusTip.textContent = '自动执行出错: ' + err.message;
                statusTip.style.backgroundColor = '#f8d7da';
                statusTip.style.color = '#721c24';
            }
        }, 3000);
    }

    // ==================== 批量执行逻辑 ====================
    function startBatchRun() {
        // 创建倒计时提示框
        const tip = document.createElement('div');
        tip.style.position = 'fixed';
        tip.style.top = '50%';
        tip.style.left = '50%';
        tip.style.transform = 'translate(-50%, -50%)';
        tip.style.backgroundColor = '#fff';
        tip.style.padding = '20px';
        tip.style.border = '1px solid #ccc';
        tip.style.boxShadow = '0 2px 15px rgba(0,0,0,0.2)';
        tip.style.zIndex = '20000';
        tip.style.textAlign = 'center';
        tip.style.borderRadius = '8px';
        tip.style.minWidth = '300px';

        const msg = document.createElement('div');
        msg.style.marginBottom = '15px';
        msg.style.fontSize = '16px';
        msg.style.fontWeight = 'bold';

        const textNode = document.createTextNode('准备开始批量执行... ');
        const timerSpan = document.createElement('span');
        timerSpan.style.color = '#dc3545';
        timerSpan.style.fontSize = '20px';
        timerSpan.textContent = '5';
        const unitNode = document.createTextNode(' 秒后自动开始');

        msg.appendChild(textNode);
        msg.appendChild(timerSpan);
        msg.appendChild(unitNode);
        tip.appendChild(msg);

        const subMsg = document.createElement('div');
        subMsg.textContent = '请保持页面开启，不要关闭';
        subMsg.style.marginBottom = '15px';
        subMsg.style.color = '#666';
        subMsg.style.fontSize = '14px';
        tip.appendChild(subMsg);

        const cancelBtn = createButton('取消执行', () => {
            clearInterval(intervalId);
            tip.remove();
        });
        cancelBtn.style.width = '100%';
        cancelBtn.style.backgroundColor = '#6c757d';
        cancelBtn.style.margin = '0';
        tip.appendChild(cancelBtn);

        document.body.appendChild(tip);

        let countdown = 5;
        const intervalId = setInterval(() => {
            countdown--;
            timerSpan.textContent = countdown;
            if (countdown <= 0) {
                clearInterval(intervalId);
                tip.remove();
                localStorage.setItem('is_batch_running', 'true');
                continueBatchRun();
            }
        }, 1000);
    }

    function stopBatchRun() {
        localStorage.setItem('is_batch_running', 'false');
        alert('已停止批量执行。当前正在运行的任务完成后将停止。');
    }

    async function continueBatchRun() {
        const savedTaskResults = localStorage.getItem('batch_task_results');
        if (!savedTaskResults) {
            alert('没有可执行的任务');
            localStorage.setItem('is_batch_running', 'false');
            return;
        }

        const results = JSON.parse(savedTaskResults);
        let nextTask = null;

        // 查找第一个未完成的任务
        for (const env in results) {
            for (const version in results[env]) {
                if (results[env][version].status !== 'completed') {
                    nextTask = { env, version, group: results[env][version] };
                    break;
                }
            }
            if (nextTask) break;
        }

        if (nextTask) {
             console.log(`准备执行批量任务: ${nextTask.env} - ${nextTask.version}`);
             // 显示提示
             const statusTip = document.createElement('div');
             statusTip.textContent = `批量执行中：正在启动 ${nextTask.env} - v${nextTask.version}`;
             statusTip.style.backgroundColor = '#d4edda';
             statusTip.style.color = '#155724';
             statusTip.style.padding = '10px';
             statusTip.style.position = 'fixed';
             statusTip.style.top = '50%';
             statusTip.style.left = '50%';
             statusTip.style.transform = 'translate(-50%, -50%)';
             statusTip.style.zIndex = '10001';
             statusTip.style.borderRadius = '4px';
             document.body.appendChild(statusTip);

             await runTask(nextTask.env, nextTask.version, nextTask.group);
        } else {
            sendFeishu('该批次任务已执行完成！')
            alert('所有批量任务已完成！');
            localStorage.setItem('is_batch_running', 'false');
        }
    }

    async function runTask(env, version, group) {
        // 1. 准备数据 (逻辑移植自原 prepareTask)
        // 保存原始信息供飞书通知使用
        const originalLines = group.items
            .filter(item => item.shopId && item.shopId !== '查询失败' && item.shopId !== '请求失败')
            .map(item => item.originalLine)
            .join('\n');
        sessionStorage.setItem('current_task_original_info', originalLines);

        // 生成格式化字符串
        const mappedEnv = envMap[env] || env;
        const validShopIds = group.items
            .map(i => i.shopId)
            .filter(id => id && id !== '查询失败' && id !== '请求失败');
        const hasExtraValues = group.extraValues && group.extraValues.length > 0;

        let text;
        if (hasExtraValues) {
            text = 'IMEI】_v' + version + '|,' + validShopIds.join(',') + '|imei';
        } else {
            text = mappedEnv + '】_v' + version + '|,' + validShopIds.join(',') + '|' + (typeMap[env] || 'gw');
        }

        // 填充并解析
        complex_input.value = text;
        parseComplexInput();

        // 2. 标记自动执行状态
        sessionStorage.setItem('auto_run_state', 'searching');
        sessionStorage.setItem('current_task_key', JSON.stringify({ env, version }));

        // 3. 执行操作
        try {
            console.log('开始执行任务(第一阶段)...');
            await ins();
        } catch (err) {
            console.error('任务启动失败:', err);
            alert('任务启动失败: ' + err.message);
            sessionStorage.removeItem('auto_run_state');
            sessionStorage.removeItem('current_task_key');
        }
    }

    // ==================== 现有功能区域 ====================
    const existingTitle = document.createElement('h3');
    existingTitle.textContent = '2. 单任务执行';
    existingTitle.style.fontSize = '16px';
    existingTitle.style.margin = '0 0 10px 0';
    form.appendChild(existingTitle);

    // 创建账号密码输入框（仅当缓存不存在时显示）
    const account_input = document.createElement('input');
    account_input.type = 'text';
    account_input.name = 'account_input';
    account_input.placeholder = '请输入账号|密码';
    account_input.style.display = 'block';
    account_input.style.width = '100%';
    account_input.style.marginBottom = '10px';
    account_input.style.padding = '8px';
    account_input.style.border = '1px solid #ccc';
    account_input.style.borderRadius = '4px';

    // 从 localStorage 读取账号密码
    const savedAccount = localStorage.getItem('login_account_password');
    if (savedAccount) {
        // 缓存存在，不显示输入框
        account_input.style.display = 'none';
    } else {
        // alert('请在输入框中输入账号和密码，格式：账号|密码'); // 移除弹窗干扰
        form.appendChild(account_input);
    }

    // 监听输入框变化，实时保存到 localStorage
    account_input.addEventListener('input', () => {
        localStorage.setItem('login_account_password', account_input.value);
    });

    async function login() {
        const usernameXPath = '/html/body/div[1]/main/form/div[1]/input';
        const passwordXPath = '/html/body/div[1]/main/form/div[2]/input';
        const submitXPath = '/html/body/div[1]/main/form/button';
        const confirmXPath = '/html/body/div[3]/div/div/div[2]/button';

        // 读取缓存账号密码并解析
        let accountPassword = localStorage.getItem('login_account_password') || '';
        if (!accountPassword.includes('|')) {
            alert('账号密码格式错误，应为 账号|密码');
            return;
        }
        const [usernameValue, passwordValue] = accountPassword.split('|');

        // 填充用户名
        await performActionsByXPath(usernameXPath, 'red', usernameValue, true);
        // 填充密码
        await performActionsByXPath(passwordXPath, 'red', passwordValue, true);
        // 点击登录
        await performActionsByXPath(submitXPath, 'red', null, true);
        await new Promise(resolve => setTimeout(resolve, 500));
        // 处理弹窗确认
        await performActionsByXPath(confirmXPath, 'red', null, true);
    }

    // 添加复杂输入框和解析按钮
    const complex_input = document.createElement('input');
    complex_input.type = 'text';
    complex_input.name = 'complex_input';
    complex_input.placeholder = '输入复杂格式内容(如:阿里云1】_v5.55|100958,101276|gw)';
    complex_input.style.display = 'block';
    complex_input.style.width = '100%';
    complex_input.style.marginBottom = '10px';
    complex_input.style.padding = '8px';
    complex_input.style.border = '1px solid #ccc';
    complex_input.style.borderRadius = '4px';
    form.appendChild(complex_input);

    // 从 localStorage 加载复杂输入框内容
    const savedComplexValue = localStorage.getItem('complex_input');
    if (savedComplexValue) {
        complex_input.value = savedComplexValue;
    }
    // 监听复杂输入框内容变化
    complex_input.addEventListener('input', updateLocalStorage);

    const parseButton = createButton('解析内容', parseComplexInput);
    form.appendChild(parseButton);

    async function parseComplexInput() {
        const complexValue = complex_input.value.trim();
        if (!complexValue) {
            alert('请输入需要解析的内容');
            return;
        }

        // 使用|分割内容
        const parts = complexValue.split('|');
        if (parts.length !== 3) {
            alert('输入格式不正确，请使用正确的格式，如：阿里云1】_v5.55|100958,101276|gw');
            return;
        }

        // 设置环境信息
        env_info_input.value = parts[0];
        // 设置升级信息
        mdid_info_input.value = parts[1];
        // 设置单选框
        const radioType = parts[2].toLowerCase();
        const radio = document.querySelector(`input[name="radio"][value="${radioType}"]`);
        if (radio) {
            radio.checked = true;
        }

        // 更新localStorage
        updateLocalStorage();

        // 视觉反馈
        complex_input.style.backgroundColor = '#e8f0fe';
        setTimeout(() => complex_input.style.backgroundColor = '', 500);
    }

    // 新增环境信息输入框
    const env_info_input = document.createElement('input');
    env_info_input.type = 'text';
    env_info_input.name = 'env_info_input';
    env_info_input.placeholder = '升级环境信息';
    env_info_input.style.display = 'block';
    env_info_input.style.width = '100%';
    env_info_input.style.marginBottom = '10px';
    env_info_input.style.padding = '8px';
    env_info_input.style.border = '1px solid #ccc';
    env_info_input.style.borderRadius = '4px';
    form.appendChild(env_info_input);

    // 从 localStorage 加载内容到输入框
    const ttValue = localStorage.getItem('env_info_input');
    if (ttValue) {
        env_info_input.value = ttValue;
    }
    // 监听输入框内容变化
    env_info_input.addEventListener('input', updateLocalStorage);

    const insButton = createButton('录入&搜索', ins);
    async function ins(){
        const storedValue = localStorage.getItem('env_info_input');
        console.log(storedValue)
        await performActionsByXPath('//*[@id="mobile_package_name"]', 'yellow', storedValue, true);
        await performActionsByXPath('/html/body/div/main/form/button', 'yellow', null, true);
    }
    form.appendChild(insButton);
    form.appendChild(env_info_input);

    const mdid_info_input = document.createElement('input');
    mdid_info_input.id = 'text10086';
    mdid_info_input.type = 'text';
    mdid_info_input.name = 'mdid_info_input';
    mdid_info_input.placeholder = '输入升级信息';
    mdid_info_input.style.display = 'block';
    mdid_info_input.style.width = '100%';
    mdid_info_input.style.marginBottom = '10px';
    mdid_info_input.style.padding = '8px';
    mdid_info_input.style.border = '1px solid #ccc';
    mdid_info_input.style.borderRadius = '4px';
    form.appendChild(mdid_info_input);

    // 创建一个清空按钮
    const clearButton = createButton('清空', clearbutton);
    form.appendChild(clearButton);
    async function clearbutton(){
        mdid_info_input.value = '';
    };

    // 从 localStorage 加载内容到输入框
    const storedValue = localStorage.getItem('mdid_info_input');
    if (storedValue) {
        mdid_info_input.value = storedValue;
    }

    // 监听输入框内容变化
    mdid_info_input.addEventListener('input', updateLocalStorage);

    // 创建单选框
    const radioOptions = [
        { text: '个微', value: 'gw'},
        { text: '企微', value: 'qw' },
        { text: 'IMEI', value: 'imei' }
    ];
    const savedValue = localStorage.getItem('publish_type');

    radioOptions.forEach((option) => {
        const container = document.createElement('div');
        container.style.marginBottom = '10px';

        const label = document.createElement('label');
        label.style.marginRight = '10px';
        label.textContent = option.text;

        const input = document.createElement('input');
        input.type = 'radio';
        input.name = 'radio';
        input.value = option.value;

        // 如果localStorage中有值，且和当前value匹配，默认选中，否则默认选第一个
        if (savedValue) {
            input.checked = (savedValue === option.value);
        } else {
            input.checked = (radioOptions[0].value === option.value);
        }

        // 监听选中事件，选中时写入localStorage
        input.addEventListener('change', (e) => {
            if (e.target.checked) {
                localStorage.setItem('publish_type', e.target.value);
            }
        });

        label.prepend(input);
        container.appendChild(label);
        form.appendChild(container);
    });

    // 创建按钮
    function createButton(text, clickHandler) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = text;
        button.style.backgroundColor = '#007bff';
        button.style.color = '#fff';
        button.style.border = 'none';
        button.style.borderRadius = '4px';
        button.style.padding = '10px 15px';
        button.style.cursor = 'pointer';
        button.style.fontSize = '16px';
        button.style.transition = 'background-color 0.3s ease';
        button.style.marginBottom = '10px';
        button.style.marginRight = '10px';
        button.onmouseover = function() {
            button.style.backgroundColor = '#0056b3';
        };
        button.onmouseout = function() {
            button.style.backgroundColor = '#007bff';
        };
        button.addEventListener('click', clickHandler);
        return button;
    }

    const loginButton = createButton('登录', login);
    form.appendChild(loginButton);

    const executeButton = createButton('执行操作', executeActions);
    form.appendChild(executeButton);

    // 创建超链接
    const links = [
        { href: 'http://m.apollo.wechatgj.com/Publish/Page?publish_info_title=&range_type=0&update_type=0', text: '升级页面' },
        { href: 'http://m.apollo.wechatgj.com/Home/Login', text: '登录页' },
        { href: 'http://m.apollo.wechatgj.com/VersionUpdate/Page', text: '商户id搜索' }
    ];

    links.forEach(linkInfo => {
        const link = document.createElement('a');
        link.href = linkInfo.href;
        link.textContent = linkInfo.text;
        link.style.display = 'block';
        link.style.marginTop = '10px';
        link.style.color = '#007bff';
        link.style.textDecoration = 'none';
        link.style.fontSize = '16px';

        link.onmouseover = function() {
            link.style.textDecoration = 'underline';
        };
        link.onmouseout = function() {
            link.style.textDecoration = 'none';
        };
        form.appendChild(link);
    });

    document.body.appendChild(form);

    // ==================== 批量处理逻辑 (移植自 HTML) ====================
    async function processBatchData() {
        const input = batchInput.value.trim();
        if (!input) {
            alert('请输入要查询的账号列表');
            return;
        }
        localStorage.setItem('batch_input_data', input);

        taskList.innerHTML = '<div style="color: #666;">处理中...</div>';
        const lines = input.split('\n');
        const envResults = {};

        // 解析数据
        for (const line of lines) {
            const parts = line.trim().split(/\s+/);
            let env, account, version, extra;

            // 兼容新旧格式
            // 旧格式：环境 账号 版本 [额外信息]
            // 新格式：公司名称 环境 账号 版本 [额外信息]
            if (envMap[parts[0]] || typeMap[parts[0]]) {
                env = parts[0];
                account = parts[1];
                version = parts[2];
                extra = parts[3];
            } else if (parts.length >= 4 && (envMap[parts[1]] || typeMap[parts[1]])) {
                env = parts[1];
                account = parts[2];
                version = parts[3];
                extra = parts[4];
            } else {
                // 默认按旧格式
                env = parts[0];
                account = parts[1];
                version = parts[2];
                extra = parts[3];
            }

            if (!env || !account) continue;

            if (!envResults[env]) {
                envResults[env] = {};
            }
            if (!envResults[env][version]) {
                envResults[env][version] = {
                    items: [],
                    extraValues: []
                };
            }

            if (extra) {
                envResults[env][version].extraValues.push(extra);
            }

            envResults[env][version].items.push({
                account,
                shopId: extra || null, // 如果有额外信息，直接作为 shopId
                needsQuery: !extra,
                originalLine: line
            });
        }

        // 查询店铺ID
        taskList.innerHTML = '<div style="color: #666;">查询店铺ID中...</div>';

        for (const env in envResults) {
            for (const version in envResults[env]) {
                const group = envResults[env][version];
                for (const item of group.items) {
                    if (item.needsQuery) {
                        try {
                            const result = await queryShopId(env, item.account);
                            item.shopId = result;
                        } catch (e) {
                            console.error(`Query failed for ${item.account}`, e);
                            item.shopId = '查询失败';
                        }
                    }
                }
            }
        }

        // 渲染任务列表
        renderTaskList(envResults);

        // 保存到 localStorage 以便页面刷新后恢复
        localStorage.setItem('batch_task_results', JSON.stringify(envResults));
    }

    function queryShopId(env, account) {
        return new Promise((resolve, reject) => {
            // 构建 URL，注意 API_BASE_URL 的使用
            let url = `${API_BASE_URL}/api/shopid?env=${encodeURIComponent(env)}&user_account=${encodeURIComponent(account)}`;
            // 如果 API_BASE_URL 为空且当前页面不是同源，这可能会失败。但按照原逻辑，我们尝试请求。

            GM_xmlhttpRequest({
                method: 'GET',
                url: url,
                onload: function(response) {
                    if (response.status === 200) {
                        try {
                            const data = JSON.parse(response.responseText);
                            if (data.shopid && data.shopid !== "查询失败") {
                                resolve(data.shopid);
                            } else {
                                sendFeishu(`<at user_id="${feishu_openid}"></at>商户ID查询失败，需要手动查询\n${env} ${account}`);
                                resolve('查询失败');
                            }
                        } catch (e) {
                            reject(e);
                        }
                    } else {
                        reject(new Error(response.statusText));
                    }
                },
                onerror: function(err) {
                    reject(err);
                }
            });
        });
    }

    function renderTaskList(envResults) {
        taskList.innerHTML = '';

        let hasTasks = false;
        for (const env in envResults) {
            for (const version in envResults[env]) {
                hasTasks = true;
                const group = envResults[env][version];
                const validShopIds = group.items
                    .map(i => i.shopId)
                    .filter(id => id && id !== '查询失败' && id !== '请求失败');

                const taskRow = document.createElement('div');
                taskRow.style.display = 'flex';
                taskRow.style.marginBottom = '5px';
                taskRow.style.gap = '5px';

                // 左侧信息按钮
                const infoBtn = document.createElement('button');
                infoBtn.type = 'button';
                infoBtn.style.flex = '1';
                infoBtn.style.padding = '8px';
                infoBtn.style.textAlign = 'left';
                infoBtn.style.backgroundColor = '#f8f9fa';
                infoBtn.style.border = '1px solid #ddd';
                infoBtn.style.cursor = 'pointer';
                infoBtn.style.borderRadius = '4px';

                const count = validShopIds.length;
                infoBtn.innerHTML = `<strong>${env}</strong> - v${version} <span style="float:right; color: green;">${count}个有效</span>`;

                // 简化版 prepareTask (仅用于UI交互，不执行)
                const previewTask = () => {
                    // 保存原始信息供飞书通知使用
                    const originalLines = group.items
                        .filter(item => item.shopId && item.shopId !== '查询失败' && item.shopId !== '请求失败')
                        .map(item => item.originalLine)
                        .join('\n');
                    sessionStorage.setItem('current_task_original_info', originalLines);

                    // 生成格式化字符串
                    const mappedEnv = envMap[env] || env;
                    const hasExtraValues = group.extraValues && group.extraValues.length > 0;

                    let text;
                    if (hasExtraValues) {
                        text = 'IMEI】_v' + version + '|,' + validShopIds.join(',') + '|imei';
                    } else {
                        text = mappedEnv + '】_v' + version + '|,' + validShopIds.join(',') + '|' + (typeMap[env] || 'gw');
                    }

                    // 填充并解析
                    complex_input.value = text;
                    parseComplexInput();

                    // 高亮当前按钮
                    Array.from(taskList.children).forEach(row => {
                        row.children[0].style.backgroundColor = '#f8f9fa';
                    });
                    infoBtn.style.backgroundColor = '#d1e7dd';
                };

                infoBtn.onclick = () => {
                    previewTask();
                    // 滚动到底部
                    executeButton.scrollIntoView({ behavior: 'smooth' });
                };

                // 右侧执行按钮
                const runBtn = document.createElement('button');
                runBtn.type = 'button';

                // 根据状态设置按钮样式
                if (group.status === 'completed') {
                    runBtn.textContent = '已执行';
                    runBtn.style.backgroundColor = '#6c757d'; // 灰色
                    infoBtn.style.textDecoration = 'line-through';
                    infoBtn.style.color = '#666';
                } else {
                    runBtn.textContent = '执行';
                    runBtn.style.backgroundColor = '#28a745'; // 绿色
                }

                runBtn.style.width = '70px';
                runBtn.style.padding = '8px';
                runBtn.style.color = '#fff';
                runBtn.style.border = 'none';
                runBtn.style.borderRadius = '4px';
                runBtn.style.cursor = 'pointer';

                runBtn.onclick = async () => {
                    // 如果已执行，询问是否重新执行
                    if (group.status === 'completed') {
                        if (!confirm('该任务已执行过，确定要重新执行吗？')) {
                            return;
                        }
                    }
                    // 使用统一的 runTask
                    executeButton.scrollIntoView({ behavior: 'smooth' });
                    await runTask(env, version, group);
                };

                taskRow.appendChild(infoBtn);
                taskRow.appendChild(runBtn);
                taskList.appendChild(taskRow);
            }
        }

        if (!hasTasks) {
            taskList.innerHTML = '<div style="color: red;">未找到有效数据</div>';
        }
    }

    // ==================== 执行逻辑 (保持不变) ====================
    async function executeActions() {
        const upgrade_info = document.querySelector('input[name="mdid_info_input"]').value;
        var types = null
        if (document.querySelector('input[name="radio"]:checked')?.value == 'gw'){
            types = '//*[@id="EditInput_merchantids_white_list"]';
        }
        else if (document.querySelector('input[name="radio"]:checked')?.value == 'qw'){
            types = '//*[@id="EditInput_wwmerchantids_white_list"]';
        }
        else{
            types = '//*[@id="EditInput_imeis_white_list"]'};

        const xpaths = [
            '/html/body/div/main/table/tbody/tr[1]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[2]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[3]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[4]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[5]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[6]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[7]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[8]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[9]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[10]/td[8]/button[1]',
            '/html/body/div/main/table/tbody/tr[11]/td[8]/button[1]',
        ];

        const color = 'yellow';
        const submitXPath = "//button[text()='提交']";
        const submitXPath2 = '//*[@id="editDialog"]/div/div/div[1]/button';

        for (let i = 0; i < xpaths.length; i++) {
            await new Promise(resolve => setTimeout(resolve, 1500));
            await performActionsByXPath(xpaths[i], color, null);
            await new Promise(resolve => setTimeout(resolve, 1500));
            console.log('元素：：',types)
            await performActionsByXPath(types, color, upgrade_info, true, 'Edit?','isadd');
            await new Promise(resolve => setTimeout(resolve, 3000));
            await performActionsByXPath(submitXPath, color,null,true, 'Edit?');
            await new Promise(resolve => setTimeout(resolve, 1500));
            await performActionsByXPath(submitXPath2, color,null,true);
        }

        // 发送飞书通知
        // 优先发送原始信息（如果存在），否则发送解析后的信息
        let originalInfo = sessionStorage.getItem('current_task_original_info');
        if (originalInfo) {
            originalInfo = originalInfo.replace(/\t/g, '--');
        }
        try {
            if (originalInfo && originalInfo.trim()) {
                await sendFeishu('该商户已升级完成：\n' + originalInfo);
                sessionStorage.removeItem('current_task_original_info');
            } else {
                await sendFeishu('主账号解析失败，升级完成信息：\n' + complex_input.value);
              }
        } catch (err) {
            console.error('发送飞书通知过程中出错:', err);
        }

        // 更新任务状态为已完成
        const taskKeyJson = sessionStorage.getItem('current_task_key');
        if (taskKeyJson) {
            try {
                const { env, version } = JSON.parse(taskKeyJson);
                const savedTaskResults = localStorage.getItem('batch_task_results');
                if (savedTaskResults) {
                    const results = JSON.parse(savedTaskResults);
                    if (results[env] && results[env][version]) {
                        results[env][version].status = 'completed';
                        localStorage.setItem('batch_task_results', JSON.stringify(results));
                        // 重新渲染任务列表以更新UI
                        renderTaskList(results);
                    }
                }
                sessionStorage.removeItem('current_task_key');
            } catch (e) {
                console.error('更新任务状态失败', e);
            }
        }

        // 检查是否处于批量自动执行模式
        if (localStorage.getItem('is_batch_running') === 'true') {
            console.log('检测到批量执行模式，准备执行下一个任务...');
            setTimeout(() => {
                continueBatchRun();
            }, 2000); // 延迟2秒，给用户一点反应时间，也防止请求过于频繁
        }
    }

    function performActionsByXPath(xpath, color, value = null, click = true, iframeSrc = null, isadd = null) {
        return new Promise((resolve) => {
            let doc = document;
            if (iframeSrc) {
                const iframe = Array.from(document.querySelectorAll('iframe')).find(iframe => iframe.src.includes(iframeSrc));
                if (iframe) {
                    doc = iframe.contentDocument || iframe.contentWindow.document;
                } else {
                    console.log("未找到指定的 iframe");
                    resolve();
                    return;
                }
            }

            const result = doc.evaluate(xpath, doc, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            const element = result.singleNodeValue;

            if (element) {
                element.style.backgroundColor = color;
                console.log(xpath, "颜色已改变");

                if (value !== null) {
                    if (isadd !== null){
                        console.log(element.value, "element的值");
                        value = (element.value || '') + value;
                    }
                    element.value = value;
                    console.log(xpath, "设置了值:", element.value);
                }

                if (click) {
                    element.click();
                    console.log(xpath, "点击了");
                }

                resolve();
            } else {
                console.log(xpath, "没找到元素");
                resolve();
            }
        });
    }
})();
