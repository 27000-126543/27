let API_BASE = '';
let TOKEN = localStorage.getItem('token') || '';
let CURRENT_USER = null;

async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (TOKEN) headers['Authorization'] = `Bearer ${TOKEN}`;
    const res = await fetch(API_BASE + path, { ...options, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || '请求失败');
    return data;
}

function toast(msg, type = 'success') {
    const colors = { success: 'bg-green-500', error: 'bg-red-500', info: 'bg-blue-500', warning: 'bg-amber-500' };
    const icons = { success: 'fa-check', error: 'fa-xmark', info: 'fa-info', warning: 'fa-triangle-exclamation' };
    const el = document.createElement('div');
    el.className = `${colors[type]} text-white px-5 py-3 rounded-xl shadow-lg flex items-center gap-3 min-w-[280px]`;
    el.innerHTML = `<i class="fas ${icons[type]}"></i><span>${msg}</span>`;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = '0.3s'; setTimeout(() => el.remove(), 300); }, 3000);
}

function fmtMoney(n) {
    if (n == null) return '-';
    return '¥ ' + Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function showModal(title, html) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = html;
    document.getElementById('modal').classList.remove('hidden');
}
function closeModal() { document.getElementById('modal').classList.add('hidden'); }

function logout() {
    localStorage.removeItem('token'); TOKEN = ''; CURRENT_USER = null;
    document.getElementById('app-page').classList.add('hidden');
    document.getElementById('login-page').classList.remove('hidden');
    toast('已退出登录', 'info');
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData();
    form.append('username', document.getElementById('login-username').value);
    form.append('password', document.getElementById('login-password').value);
    try {
        const res = await fetch(API_BASE + '/api/auth/login', { method: 'POST', body: form });
        if (!res.ok) throw new Error('用户名或密码错误');
        const data = await res.json();
        TOKEN = data.access_token; localStorage.setItem('token', TOKEN);
        await initApp();
    } catch (err) {
        const el = document.getElementById('login-error');
        el.textContent = err.message; el.classList.remove('hidden');
    }
});

async function initApp() {
    try { CURRENT_USER = await api('/api/auth/me'); }
    catch (e) { localStorage.removeItem('token'); TOKEN = ''; return; }

    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('app-page').classList.remove('hidden');
    document.getElementById('user-name').textContent = CURRENT_USER.full_name;
    const roleNames = { admin: '管理员', sales: '销售人员', sales_manager: '销售经理', region_director: '区域总监', finance: '财务', auditor: '审计员', channel_partner: '渠道商' };
    document.getElementById('user-role').textContent = roleNames[CURRENT_USER.role] || CURRENT_USER.role;

    const now = new Date();
    document.getElementById('current-date').textContent = now.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });

    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            const page = item.dataset.page;
            document.querySelectorAll('.page-content').forEach(c => c.classList.add('hidden'));
            document.getElementById('page-' + page).classList.remove('hidden');
            const titles = {
                dashboard: ['仪表盘', '系统概览'],
                commission: ['佣金明细', '销售人员佣金记录'],
                rebate: ['渠道返利', '渠道商返利记录'],
                approval: ['审批中心', '待审批事项'],
                appeal: ['异议申诉', '佣金返利申诉处理'],
                reports: ['分析报告', '月度分析报告与导出'],
                calc: ['计算与同步', '数据同步与计算']
            };
            document.getElementById('page-title').textContent = titles[page][0];
            document.getElementById('page-subtitle').textContent = titles[page][1];
            loadPage(page);
        });
    });

    loadPage('dashboard');
    updateApprovalBadge();
}

async function updateApprovalBadge() {
    try {
        const res = await api('/api/workflow/pending');
        const count = res.data.total_count || 0;
        const badge = document.getElementById('approval-badge');
        if (count > 0) { badge.textContent = count; badge.classList.remove('hidden'); }
        else badge.classList.add('hidden');
    } catch (e) {}
}

function navigate(page) { document.querySelector(`[data-page="${page}"]`).click(); }

async function loadPage(page) {
    if (page === 'dashboard') await renderDashboard();
    if (page === 'commission') await renderCommission();
    if (page === 'rebate') await renderRebate();
    if (page === 'approval') await renderApproval();
    if (page === 'appeal') await renderAppeal();
    if (page === 'reports') await renderReports();
    if (page === 'calc') await renderCalc();
}

async function renderDashboard() {
    const container = document.getElementById('page-dashboard');
    container.innerHTML = '<div class="text-center py-20"><i class="fas fa-spinner fa-spin text-primary-500 text-3xl"></i></div>';
    let data;
    try { data = (await api('/api/calculation/dashboard')).data; }
    catch (e) { container.innerHTML = '<div class="text-red-500">加载失败: ' + e.message + '</div>'; return; }

    container.innerHTML = `
        <div class="grid grid-cols-4 gap-6">
            <div class="bg-white rounded-2xl p-6 shadow-sm card-hover">
                <div class="flex items-center justify-between">
                    <div><div class="text-sm text-slate-500">本月佣金总额</div><div class="text-2xl font-bold text-slate-800 mt-1">${fmtMoney(data.commission.total_current_month)}</div></div>
                    <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center"><i class="fas fa-coins text-blue-600 text-xl"></i></div>
                </div>
                <div class="mt-4 text-xs text-slate-400">待审批 <span class="text-amber-500 font-medium">${fmtMoney(data.commission.pending)}</span> · 已通过 <span class="text-green-500 font-medium">${fmtMoney(data.commission.approved)}</span></div>
            </div>
            <div class="bg-white rounded-2xl p-6 shadow-sm card-hover">
                <div class="flex items-center justify-between">
                    <div><div class="text-sm text-slate-500">本季返利总额</div><div class="text-2xl font-bold text-slate-800 mt-1">${fmtMoney(data.rebate.total_current_quarter)}</div></div>
                    <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center"><i class="fas fa-hand-holding-dollar text-emerald-600 text-xl"></i></div>
                </div>
                <div class="mt-4 text-xs text-slate-400">冻结金额 <span class="text-red-500 font-medium">${fmtMoney(data.rebate.frozen_amount)}</span> · 预警 <span class="text-amber-500 font-medium">${data.rebate.warning_count}</span> 条</div>
            </div>
            <div class="bg-white rounded-2xl p-6 shadow-sm card-hover">
                <div class="flex items-center justify-between">
                    <div><div class="text-sm text-slate-500">待办审批</div><div class="text-2xl font-bold text-slate-800 mt-1">${data.workflow.pending_approvals}</div></div>
                    <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center"><i class="fas fa-clipboard-check text-amber-600 text-xl"></i></div>
                </div>
                <div class="mt-4 text-xs text-slate-400">待付款指令 <span class="font-medium">${data.workflow.pending_payments}</span> 条</div>
            </div>
            <div class="bg-white rounded-2xl p-6 shadow-sm card-hover">
                <div class="flex items-center justify-between">
                    <div><div class="text-sm text-slate-500">活跃主体</div><div class="text-2xl font-bold text-slate-800 mt-1">${data.overview.active_salespersons + data.overview.active_partners}</div></div>
                    <div class="w-12 h-12 bg-violet-100 rounded-xl flex items-center justify-center"><i class="fas fa-users text-violet-600 text-xl"></i></div>
                </div>
                <div class="mt-4 text-xs text-slate-400">销售人员 <span class="font-medium">${data.overview.active_salespersons}</span> · 渠道商 <span class="font-medium">${data.overview.active_partners}</span></div>
            </div>
        </div>
        <div class="grid grid-cols-2 gap-6">
            <div class="bg-white rounded-2xl p-6 shadow-sm">
                <h3 class="font-bold text-slate-800 mb-4">快捷操作</h3>
                <div class="grid grid-cols-2 gap-4">
                    <button onclick="navigate('calc')" class="flex items-center gap-3 p-4 border border-slate-200 rounded-xl hover:bg-primary-50 hover:border-primary-300 transition-all text-left"><i class="fas fa-database text-primary-500"></i><div><div class="font-medium text-slate-800">数据同步</div><div class="text-xs text-slate-400">CRM/订单</div></div></button>
                    <button onclick="navigate('calc')" class="flex items-center gap-3 p-4 border border-slate-200 rounded-xl hover:bg-primary-50 hover:border-primary-300 transition-all text-left"><i class="fas fa-calculator text-primary-500"></i><div><div class="font-medium text-slate-800">计算佣金</div><div class="text-xs text-slate-400">月度计算</div></div></button>
                    <button onclick="navigate('approval')" class="flex items-center gap-3 p-4 border border-slate-200 rounded-xl hover:bg-primary-50 hover:border-primary-300 transition-all text-left"><i class="fas fa-clipboard-check text-primary-500"></i><div><div class="font-medium text-slate-800">审批处理</div><div class="text-xs text-slate-400">待处理</div></div></button>
                    <button onclick="navigate('reports')" class="flex items-center gap-3 p-4 border border-slate-200 rounded-xl hover:bg-primary-50 hover:border-primary-300 transition-all text-left"><i class="fas fa-file-chart-column text-primary-500"></i><div><div class="font-medium text-slate-800">生成报告</div><div class="text-xs text-slate-400">月度分析</div></div></button>
                </div>
            </div>
            <div class="bg-white rounded-2xl p-6 shadow-sm">
                <h3 class="font-bold text-slate-800 mb-4">系统说明</h3>
                <div class="space-y-3 text-sm text-slate-600">
                    <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl"><span>月度周期</span><span class="font-bold text-primary-600">${data.current_period}</span></div>
                    <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl"><span>季度周期</span><span class="font-bold text-emerald-600">${data.current_quarter}</span></div>
                    <div class="p-3 bg-amber-50 rounded-xl text-amber-800"><i class="fas fa-circle-info mr-2"></i>每月5日自动生成报告，每周日清理过期日志</div>
                </div>
            </div>
        </div>
    `;
}

async function renderCommission() {
    const container = document.getElementById('page-commission');
    const now = new Date(); const year = now.getFullYear(); const month = now.getMonth() + 1;
    let salespersons = [];
    try { salespersons = (await api('/api/reports/salespersons')).data.salespersons || []; } catch(e) {}
    container.innerHTML = `
        <div class="bg-white rounded-2xl p-6 shadow-sm">
            <div class="grid grid-cols-5 gap-4">
                <div><label class="text-xs text-slate-500 block mb-1">年份</label>
                    <select id="q-year" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm">${[year, year-1, year-2].map(y => `<option value="${y}" ${y===year?'selected':''}>${y}</option>`).join('')}</select>
                </div>
                <div><label class="text-xs text-slate-500 block mb-1">月份</label>
                    <select id="q-month" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm">${Array.from({length:12}, (_,i)=>i+1).map(m => `<option value="${m}" ${m===month?'selected':''}>${m}月</option>`).join('')}</select>
                </div>
                <div><label class="text-xs text-slate-500 block mb-1">销售人员</label>
                    <select id="q-sp" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"><option value="">全部</option>${salespersons.map(s => `<option value="${s.id}">${s.name || s.code}</option>`).join('')}</select>
                </div>
                <div><label class="text-xs text-slate-500 block mb-1">审批状态</label>
                    <select id="q-status" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"><option value="">全部</option><option value="pending">待审批</option><option value="approved">已通过</option><option value="rejected">已驳回</option><option value="escalated">已升级</option></select>
                </div>
                <div class="flex items-end gap-2">
                    <button onclick="searchCommission()" class="flex-1 bg-primary-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-primary-700"><i class="fas fa-search mr-1"></i>查询</button>
                    <button onclick="exportCommission()" class="px-4 py-2 border border-slate-200 rounded-lg text-sm hover:bg-slate-50"><i class="fas fa-file-excel text-green-600"></i></button>
                </div>
            </div>
        </div>
        <div class="bg-white rounded-2xl shadow-sm overflow-hidden"><div id="commission-result" class="p-10 text-center text-slate-400">请点击查询按钮</div></div>
    `;
}

async function searchCommission() {
    const body = { period_year: +document.getElementById('q-year').value, period_month: +document.getElementById('q-month').value, page: 1, page_size: 100 };
    if (document.getElementById('q-sp').value) body.salesperson_id = +document.getElementById('q-sp').value;
    if (document.getElementById('q-status').value) body.approval_status = document.getElementById('q-status').value;
    let res; try { res = await api('/api/calculation/commission/query', { method: 'POST', body: JSON.stringify(body) }); }
    catch (e) { toast(e.message, 'error'); return; }
    const records = res.data.records || [];
    const total = res.data.total || 0;
    const totalAmount = records.reduce((s, r) => s + r.total_commission, 0);
    const statusColors = { pending: 'bg-amber-100 text-amber-700', approved: 'bg-green-100 text-green-700', rejected: 'bg-red-100 text-red-700', escalated: 'bg-blue-100 text-blue-700' };
    const statusNames = { pending: '待审批', approved: '已通过', rejected: '已驳回', escalated: '已升级' };
    if (!records.length) { document.getElementById('commission-result').innerHTML = '<div class="text-slate-400">暂无数据</div>'; return; }
    document.getElementById('commission-result').innerHTML = `
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
            <div>共 <span class="font-bold text-primary-600">${total}</span> 条记录，合计佣金：<span class="font-bold text-emerald-600">${fmtMoney(totalAmount)}</span></div>
        </div>
        <table class="w-full text-sm"><thead class="bg-slate-50 text-slate-600"><tr>
            <th class="px-4 py-3 text-left">记录编号</th><th class="px-4 py-3 text-left">周期</th><th class="px-4 py-3 text-left">销售人员</th>
            <th class="px-4 py-3 text-left">产品类别</th><th class="px-4 py-3 text-right">计算基数</th><th class="px-4 py-3 text-right">佣金率</th>
            <th class="px-4 py-3 text-right">基础佣金</th><th class="px-4 py-3 text-right">奖励</th><th class="px-4 py-3 text-right">总佣金</th>
            <th class="px-4 py-3 text-center">状态</th><th class="px-4 py-3 text-center">操作</th>
        </tr></thead><tbody>
        ${records.map(r => `<tr class="border-t border-slate-100 hover:bg-slate-50">
            <td class="px-4 py-3 font-mono text-xs">${r.code}</td>
            <td class="px-4 py-3">${r.period}</td>
            <td class="px-4 py-3">${r.salesperson_name || '-'}</td>
            <td class="px-4 py-3">${r.product_category || '-'}</td>
            <td class="px-4 py-3 text-right">${fmtMoney(r.base_amount)}</td>
            <td class="px-4 py-3 text-right">${(r.commission_rate*100).toFixed(2)}%</td>
            <td class="px-4 py-3 text-right">${fmtMoney(r.base_commission)}</td>
            <td class="px-4 py-3 text-right text-amber-600">${fmtMoney(r.bonus_amount)}</td>
            <td class="px-4 py-3 text-right font-bold text-emerald-600">${fmtMoney(r.total_commission)}</td>
            <td class="px-4 py-3 text-center"><span class="px-2 py-1 rounded-full text-xs ${statusColors[r.approval_status] || ''}">${statusNames[r.approval_status] || r.approval_status}</span></td>
            <td class="px-4 py-3 text-center">
                <button onclick="viewCommissionDetail(${r.id})" class="text-primary-600 hover:underline text-xs">详情</button>
                ${r.approval_status === 'pending' && ['admin','sales_manager','region_director','finance'].includes(CURRENT_USER.role) ? `<button onclick="submitApproval('commission',${r.id})" class="text-emerald-600 hover:underline text-xs ml-2">提交审批</button>` : ''}
            </td>
        </tr>`).join('')}
        </tbody></table>
    `;
}

async function viewCommissionDetail(id) {
    try {
        const res = await api('/api/calculation/commission/' + id);
        showModal('佣金详情', `<div class="space-y-4">
            <div class="p-4 bg-slate-50 rounded-xl"><div class="text-sm text-slate-500">总佣金</div><div class="text-3xl font-bold text-emerald-600 mt-1">${fmtMoney(res.data.total_commission)}</div></div>
            <div class="p-4 bg-primary-50 rounded-xl"><div class="text-sm font-medium text-primary-800 mb-2">计算明细</div><pre class="text-xs text-slate-600 whitespace-pre-wrap">${JSON.stringify(res.data.details || {}, null, 2)}</pre></div>
            <div class="text-center"><button onclick="closeModal()" class="px-6 py-2 bg-primary-600 text-white rounded-lg">关闭</button></div>
        </div>`);
    } catch (e) { toast(e.message, 'error'); }
}

async function submitApproval(type, id) {
    try { await api(`/api/workflow/${type}/${id}/submit`, { method: 'POST' }); toast('已提交审批', 'success'); searchCommission(); updateApprovalBadge(); }
    catch (e) { toast(e.message, 'error'); }
}

function exportCommission() {
    const year = +document.getElementById('q-year').value;
    const month = +document.getElementById('q-month').value;
    const sp = document.getElementById('q-sp').value;
    let url = `/api/reports/commissions/export?period_year=${year}&period_month=${month}`;
    if (sp) url += `&salesperson_id=${sp}`;
    window.open(url, '_blank');
}


async function renderRebate() {
    const container = document.getElementById('page-rebate');
    const now = new Date(); const year = now.getFullYear(); const q = Math.ceil((now.getMonth() + 1) / 3);
    let partners = [];
    try { partners = (await api('/api/reports/channel-partners')).data.partners || []; } catch(e) {}
    container.innerHTML = `
        <div class="bg-white rounded-2xl p-6 shadow-sm">
            <div class="grid grid-cols-5 gap-4">
                <div><label class="text-xs text-slate-500 block mb-1">年份</label>
                    <select id="r-year" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm">${[year, year-1, year-2].map(y => `<option value="${y}" ${y===year?'selected':''}>${y}</option>`).join('')}</select>
                </div>
                <div><label class="text-xs text-slate-500 block mb-1">季度</label>
                    <select id="r-quarter" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm">${[1,2,3,4].map(x => `<option value="${x}" ${x===q?'selected':''}>Q${x}</option>`).join('')}</select>
                </div>
                <div><label class="text-xs text-slate-500 block mb-1">渠道商</label>
                    <select id="r-partner" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"><option value="">全部</option>${partners.map(p => `<option value="${p.id}">${p.name}</option>`).join('')}</select>
                </div>
                <div><label class="text-xs text-slate-500 block mb-1">状态</label>
                    <select id="r-status" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"><option value="">全部</option><option value="calculated">已计算</option><option value="approved">已审批</option><option value="warning">预警</option><option value="frozen">已冻结</option></select>
                </div>
                <div class="flex items-end gap-2">
                    <button onclick="searchRebate()" class="flex-1 bg-primary-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-primary-700"><i class="fas fa-search mr-1"></i>查询</button>
                    <button onclick="exportRebate()" class="px-4 py-2 border border-slate-200 rounded-lg text-sm hover:bg-slate-50"><i class="fas fa-file-excel text-green-600"></i></button>
                </div>
            </div>
        </div>
        <div class="bg-white rounded-2xl shadow-sm overflow-hidden"><div id="rebate-result" class="p-10 text-center text-slate-400">请点击查询按钮</div></div>
    `;
}

async function searchRebate() {
    const body = { period_year: +document.getElementById('r-year').value, period_quarter: +document.getElementById('r-quarter').value, page: 1, page_size: 100 };
    if (document.getElementById('r-partner').value) body.channel_partner_id = +document.getElementById('r-partner').value;
    if (document.getElementById('r-status').value) body.status = document.getElementById('r-status').value;
    let res; try { res = await api('/api/calculation/rebate/query', { method: 'POST', body: JSON.stringify(body) }); }
    catch (e) { toast(e.message, 'error'); return; }
    const records = res.data.records || [];
    const total = res.data.total || 0;
    const totalAmount = records.reduce((s, r) => s + r.total_rebate, 0);
    const statusColors = { pending: 'bg-slate-100', calculated: 'bg-blue-100 text-blue-700', approved: 'bg-green-100 text-green-700', warning: 'bg-amber-100 text-amber-700', frozen: 'bg-red-100 text-red-700', paid: 'bg-emerald-100' };
    const statusNames = { pending: '待计算', calculated: '已计算', approved: '已审批', warning: '预警', frozen: '已冻结', paid: '已支付' };
    if (!records.length) { document.getElementById('rebate-result').innerHTML = '<div class="text-slate-400">暂无数据</div>'; return; }
    document.getElementById('rebate-result').innerHTML = `
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
            <div>共 <span class="font-bold text-primary-600">${total}</span> 条记录，合计返利：<span class="font-bold text-emerald-600">${fmtMoney(totalAmount)}</span></div>
        </div>
        <table class="w-full text-sm"><thead class="bg-slate-50 text-slate-600"><tr>
            <th class="px-4 py-3 text-left">记录编号</th><th class="px-4 py-3 text-left">周期</th><th class="px-4 py-3 text-left">渠道商</th>
            <th class="px-4 py-3 text-right">累计销售</th><th class="px-4 py-3 text-right">返利率</th><th class="px-4 py-3 text-right">总返利</th>
            <th class="px-4 py-3 text-right">预算利用率</th><th class="px-4 py-3 text-center">状态</th><th class="px-4 py-3 text-center">操作</th>
        </tr></thead><tbody>
        ${records.map(r => `<tr class="border-t border-slate-100 hover:bg-slate-50 ${r.is_frozen ? 'bg-red-50/30' : ''}">
            <td class="px-4 py-3 font-mono text-xs">${r.code}</td>
            <td class="px-4 py-3">${r.period}</td>
            <td class="px-4 py-3">${r.partner_name || '-'}</td>
            <td class="px-4 py-3 text-right">${fmtMoney(r.total_sales)}</td>
            <td class="px-4 py-3 text-right">${(r.rebate_rate*100).toFixed(2)}%</td>
            <td class="px-4 py-3 text-right font-bold text-emerald-600">${fmtMoney(r.total_rebate)}</td>
            <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-2">
                    <div class="w-16 h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div class="h-full ${r.budget_utilization > 100 ? 'bg-red-500' : (r.budget_utilization > 80 ? 'bg-amber-500' : 'bg-green-500')}" style="width:${Math.min(r.budget_utilization, 100)}%"></div>
                    </div>
                    <span class="${r.budget_utilization > 100 ? 'text-red-600' : 'text-slate-600'}">${r.budget_utilization}%</span>
                </div>
            </td>
            <td class="px-4 py-3 text-center"><span class="px-2 py-1 rounded-full text-xs ${statusColors[r.status] || ''}">${r.is_frozen ? '已冻结' : (statusNames[r.status] || r.status)}</span></td>
            <td class="px-4 py-3 text-center">
                ${r.is_frozen && ['admin','finance','region_director'].includes(CURRENT_USER.role) ? `<button onclick="unfreezeRebate(${r.id})" class="text-emerald-600 hover:underline text-xs mr-2">解冻</button>` : ''}
                ${r.status !== 'approved' && !r.is_frozen && ['admin','finance'].includes(CURRENT_USER.role) ? `<button onclick="submitRebateApproval(${r.id})" class="text-primary-600 hover:underline text-xs">审批</button>` : ''}
            </td>
        </tr>`).join('')}
        </tbody></table>
    `;
}

async function unfreezeRebate(id) {
    if (!confirm('确定解冻该返利？')) return;
    try { await api(`/api/calculation/rebate/${id}/unfreeze`); toast('已解冻', 'success'); searchRebate(); }
    catch (e) { toast(e.message, 'error'); }
}

async function submitRebateApproval(id) {
    try { await api(`/api/workflow/rebate/${id}/submit`, { method: 'POST' }); toast('已提交审批', 'success'); searchRebate(); updateApprovalBadge(); }
    catch (e) { toast(e.message, 'error'); }
}

function exportRebate() {
    const year = +document.getElementById('r-year').value;
    const quarter = +document.getElementById('r-quarter').value;
    window.open(`/api/reports/rebates/export?period_year=${year}&period_quarter=${quarter}`, '_blank');
}

async function renderApproval() {
    const container = document.getElementById('page-approval');
    container.innerHTML = '<div class="text-center py-20"><i class="fas fa-spinner fa-spin text-primary-500 text-3xl"></i></div>';
    try {
        const res = await api('/api/workflow/pending');
        const data = res.data;
        const commissions = data.commissions || [];
        const rebates = data.rebates || [];
        container.innerHTML = `
            <div class="bg-white rounded-2xl shadow-sm overflow-hidden">
                <div class="flex border-b border-slate-100">
                    <button class="tab-btn active px-6 py-4 font-medium text-slate-600" onclick="switchTab(event, 'comm')">佣金审批 (${commissions.length})</button>
                    <button class="tab-btn px-6 py-4 font-medium text-slate-600" onclick="switchTab(event, 'rbt')">返利审批 (${rebates.length})</button>
                </div>
                <div id="tab-comm" class="tab-content p-6">
                    ${commissions.length === 0 ? '<div class="text-center py-10 text-slate-400">暂无待审批</div>' : `
                        <div class="space-y-3">
                            ${commissions.map(c => `<div class="flex items-center justify-between p-4 border border-slate-200 rounded-xl hover:bg-slate-50">
                                <div><div class="flex items-center gap-2"><span class="font-mono text-xs text-slate-400">${c.code}</span><span class="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">第${c.level}级</span></div><div class="mt-1 font-medium">${c.salesperson} · ${c.period}</div></div>
                                <div class="flex items-center gap-4">
                                    <div class="text-right"><div class="text-2xl font-bold text-emerald-600">${fmtMoney(c.amount)}</div><div class="text-xs text-slate-400">审批金额</div></div>
                                    <button onclick="doApprove('commission', ${c.id})" class="px-4 py-2 bg-emerald-500 text-white rounded-lg text-sm hover:bg-emerald-600"><i class="fas fa-check mr-1"></i>通过</button>
                                    <button onclick="doReject('commission', ${c.id})" class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600"><i class="fas fa-times mr-1"></i>驳回</button>
                                </div>
                            </div>`).join('')}
                        </div>`}
                </div>
                <div id="tab-rbt" class="tab-content p-6 hidden">
                    ${rebates.length === 0 ? '<div class="text-center py-10 text-slate-400">暂无待审批</div>' : `
                        <div class="space-y-3">
                            ${rebates.map(r => `<div class="flex items-center justify-between p-4 border border-slate-200 rounded-xl hover:bg-slate-50 ${r.frozen ? 'bg-red-50/50':''}">
                                <div><div class="flex items-center gap-2"><span class="font-mono text-xs text-slate-400">${r.code}</span>${r.frozen ? '<span class="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded">已冻结</span>' : ''}</div><div class="mt-1 font-medium">${r.partner} · ${r.period}</div></div>
                                <div class="flex items-center gap-4">
                                    <div class="text-right"><div class="text-2xl font-bold text-emerald-600">${fmtMoney(r.amount)}</div><div class="text-xs text-slate-400">审批金额</div></div>
                                    <button onclick="doApprove('rebate', ${r.id})" class="px-4 py-2 bg-emerald-500 text-white rounded-lg text-sm hover:bg-emerald-600"><i class="fas fa-check mr-1"></i>通过</button>
                                    <button onclick="doReject('rebate', ${r.id})" class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600"><i class="fas fa-times mr-1"></i>驳回</button>
                                </div>
                            </div>`).join('')}
                        </div>`}
                </div>
            </div>
            <div class="bg-white rounded-2xl p-6 shadow-sm">
                <h3 class="font-bold text-slate-800 mb-4">审批历史</h3>
                <div id="approval-history" class="text-sm"><button onclick="loadApprovalHistory()" class="text-primary-600 hover:underline text-sm">点击加载审批历史</button></div>
            </div>
        `;
    } catch (e) { container.innerHTML = '<div class="text-red-500">加载失败</div>'; }
}

function switchTab(e, tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    e.target.classList.add('active');
    document.getElementById('tab-' + tab).classList.remove('hidden');
}

async function doApprove(type, id) {
    const comments = prompt('审批意见（可选）', '审批通过');
    if (comments === null) return;
    try { await api(`/api/workflow/${type}/${id}/approve`, { method: 'POST', body: JSON.stringify({ comments }) });
        toast('审批通过', 'success'); renderApproval(); updateApprovalBadge(); }
    catch (e) { toast(e.message, 'error'); }
}

async function doReject(type, id) {
    const comments = prompt('驳回原因（必填）', '');
    if (!comments) { toast('请填写驳回原因', 'warning'); return; }
    try { await api(`/api/workflow/${type}/${id}/reject`, { method: 'POST', body: JSON.stringify({ comments }) });
        toast('已驳回', 'success'); renderApproval(); updateApprovalBadge(); }
    catch (e) { toast(e.message, 'error'); }
}

async function loadApprovalHistory() {
    try {
        const res = await api('/api/workflow/approval-history?page_size=20');
        const records = res.data.records || [];
        const actionColors = { pending: 'bg-slate-100 text-slate-600', approved: 'bg-green-100 text-green-700', rejected: 'bg-red-100 text-red-700', escalated: 'bg-blue-100 text-blue-700' };
        const actionNames = { pending: '待处理', approved: '通过', rejected: '驳回', escalated: '升级' };
        document.getElementById('approval-history').innerHTML = records.length === 0 ? '<div class="text-slate-400">暂无记录</div>' : `
            <table class="w-full text-sm"><thead class="text-slate-500"><tr>
                <th class="text-left py-2">时间</th><th class="text-left py-2">类型</th><th class="text-left py-2">目标编号</th>
                <th class="text-left py-2">审批人</th><th class="text-center py-2">动作</th><th class="text-left py-2">意见</th>
            </tr></thead><tbody>
                ${records.map(r => `<tr class="border-t border-slate-100">
                    <td class="py-2 text-slate-500">${new Date(r.approval_date).toLocaleString('zh-CN')}</td>
                    <td class="py-2">${r.type === 'commission' ? '佣金' : '返利'}</td>
                    <td class="py-2 font-mono text-xs">${r.target_code}</td>
                    <td class="py-2">${r.approver}</td>
                    <td class="py-2 text-center"><span class="px-2 py-0.5 rounded text-xs ${actionColors[r.action]}">${actionNames[r.action]}</span></td>
                    <td class="py-2 text-slate-600">${r.comments || '-'}</td>
                </tr>`).join('')}
            </tbody></table>
        `;
    } catch (e) { toast(e.message, 'error'); }
}

async function renderAppeal() {
    const container = document.getElementById('page-appeal');
    const isReviewer = ['admin','sales_manager','region_director','auditor','finance'].includes(CURRENT_USER.role);
    let commissions = [];
    try { commissions = (await api('/api/calculation/commission/query', { method: 'POST', body: JSON.stringify({ page: 1, page_size: 200 }) })).data.records || []; } catch(e) {}
    container.innerHTML = `
        <div class="grid grid-cols-2 gap-6">
            <div class="bg-white rounded-2xl p-6 shadow-sm">
                <h3 class="font-bold text-slate-800 mb-4">提交申诉</h3>
                <form id="appeal-form" class="space-y-4">
                    <div><label class="text-sm text-slate-600 block mb-1">申诉类型</label>
                        <select id="appeal-type" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"><option value="commission">佣金异议</option><option value="rebate">返利异议</option><option value="other">其他</option></select>
                    </div>
                    <div><label class="text-sm text-slate-600 block mb-1">关联佣金记录</label>
                        <select id="appeal-commission-id" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"><option value="">请选择</option>${commissions.map(c => `<option value="${c.id}">${c.code} - ${c.salesperson_name || ''} - ${fmtMoney(c.total_commission)}</option>`).join('')}</select>
                    </div>
                    <div><label class="text-sm text-slate-600 block mb-1">申诉原因 *</label>
                        <textarea id="appeal-reason" rows="4" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="请详细说明申诉原因..." required></textarea>
                    </div>
                    <div><label class="text-sm text-slate-600 block mb-1">证据/备注</label>
                        <textarea id="appeal-evidence" rows="2" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="订单号、合同号等..."></textarea>
                    </div>
                    <button type="submit" class="w-full bg-primary-600 text-white py-2.5 rounded-lg font-medium hover:bg-primary-700"><i class="fas fa-paper-plane mr-2"></i>提交申诉</button>
                </form>
            </div>
            <div class="bg-white rounded-2xl p-6 shadow-sm">
                <h3 class="font-bold text-slate-800 mb-4">我的申诉记录</h3>
                <div id="my-appeals" class="space-y-3"></div>
            </div>
        </div>
        ${isReviewer ? `<div class="bg-white rounded-2xl p-6 shadow-sm"><div class="flex items-center justify-between mb-4">
            <h3 class="font-bold text-slate-800">待复核申诉</h3>
            <button onclick="loadPendingAppeals()" class="text-sm text-primary-600 hover:underline"><i class="fas fa-sync mr-1"></i>刷新</button>
        </div><div id="pending-appeals" class="text-slate-400 text-sm">点击刷新加载</div></div>` : ''}
    `;
    document.getElementById('appeal-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const body = { appeal_type: document.getElementById('appeal-type').value, reason: document.getElementById('appeal-reason').value, evidence: document.getElementById('appeal-evidence')?.value };
        const commId = document.getElementById('appeal-commission-id')?.value;
        if (commId) body.commission_record_id = +commId;
        try { await api('/api/workflow/appeals', { method: 'POST', body: JSON.stringify(body) });
            toast('申诉已提交', 'success'); e.target.reset(); loadMyAppeals(); }
        catch (e) { toast(e.message, 'error'); }
    });
    loadMyAppeals();
    if (isReviewer) loadPendingAppeals();
}

async function loadMyAppeals() {
    try {
        const appeals = (await api('/api/workflow/appeals/mine')).data.appeals || [];
        const statusColors = { submitted: 'bg-amber-100 text-amber-700', under_review: 'bg-blue-100 text-blue-700', approved: 'bg-green-100 text-green-700', rejected: 'bg-red-100 text-red-700' };
        const statusNames = { submitted: '已提交', under_review: '复核中', approved: '已通过', rejected: '已驳回' };
        document.getElementById('my-appeals').innerHTML = appeals.length === 0 ?
            '<div class="text-slate-400 text-sm text-center py-8">暂无申诉记录</div>' :
            appeals.map(a => `<div class="p-4 border border-slate-200 rounded-xl">
                <div class="flex items-center justify-between"><span class="font-mono text-xs text-slate-400">${a.code}</span><span class="px-2 py-0.5 rounded-full text-xs ${statusColors[a.status]}">${statusNames[a.status]}</span></div>
                <div class="mt-2 text-sm">${a.reason}</div>
                ${a.is_resolved ? `<div class="mt-2 text-xs text-emerald-600"><i class="fas fa-circle-check mr-1"></i>${a.review_comments || '已处理'}</div>` : ''}
                <div class="mt-2 text-xs text-slate-400">${new Date(a.created_at).toLocaleString('zh-CN')}</div>
            </div>`).join('');
    } catch (e) {}
}

async function loadPendingAppeals() {
    try {
        const appeals = (await api('/api/workflow/appeals/pending')).data.appeals || [];
        if (!appeals.length) { document.getElementById('pending-appeals').innerHTML = '<div class="text-slate-400 text-sm text-center py-4">暂无待复核申诉</div>'; return; }
        document.getElementById('pending-appeals').innerHTML = `<div class="space-y-3">
            ${appeals.map(a => `<div class="flex items-center justify-between p-4 border border-slate-200 rounded-xl">
                <div><div class="flex items-center gap-2"><span class="font-mono text-xs text-slate-400">${a.code}</span><span class="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded">${a.type}</span></div>
                <div class="mt-1 font-medium">${a.appellant}</div><div class="mt-1 text-sm text-slate-600">${a.reason}</div></div>
                <button onclick="reviewAppealDetail(${a.id})" class="px-3 py-1.5 text-primary-600 border border-primary-200 rounded-lg text-sm hover:bg-primary-50">查看详情</button>
            </div>`).join('')}
        </div>`;
    } catch (e) { toast(e.message, 'error'); }
}

async function reviewAppealDetail(id) {
    try {
        const data = (await api('/api/workflow/appeals/' + id)).data;
        const appeal = data.appeal;
        showModal('申诉详情 - ' + appeal.code, `<div class="space-y-4">
            <div class="grid grid-cols-2 gap-4 text-sm"><div><span class="text-slate-500">申诉人：</span>${appeal.appellant}</div><div><span class="text-slate-500">提交时间：</span>${new Date(appeal.created_at).toLocaleString('zh-CN')}</div><div><span class="text-slate-500">申诉类型：</span>${appeal.type}</div><div><span class="text-slate-500">状态：</span>${appeal.status}</div></div>
            <div class="p-4 bg-slate-50 rounded-xl"><div class="text-sm font-medium mb-2">申诉原因</div><div class="text-sm text-slate-700">${appeal.reason}</div></div>
            ${data.commission_record ? `<div class="p-4 bg-emerald-50 rounded-xl"><div class="text-sm font-medium mb-2">关联佣金</div><div class="grid grid-cols-2 gap-2 text-sm"><div>周期：${data.commission_record.period}</div><div>总佣金：${fmtMoney(data.commission_record.total_commission)}</div></div></div>` : ''}
            ${data.orders && data.orders.length ? `<div><div class="text-sm font-medium mb-2">关联订单 (${data.orders.length})</div><div class="max-h-32 overflow-auto border border-slate-200 rounded-xl">
                <table class="w-full text-xs"><thead class="bg-slate-50"><tr><th class="px-3 py-2 text-left">订单号</th><th class="px-3 py-2 text-left">客户</th><th class="px-3 py-2 text-right">金额</th></tr></thead><tbody>
                    ${data.orders.map(o => `<tr class="border-t border-slate-100"><td class="px-3 py-2">${o.order_number}</td><td class="px-3 py-2">${o.customer}</td><td class="px-3 py-2 text-right">${fmtMoney(o.net_amount)}</td></tr>`).join('')}
                </tbody></table></div></div>` : ''}
            <div><label class="text-sm font-medium block mb-2">复核意见 *</label><textarea id="review-comments" rows="3" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="请填写复核意见..."></textarea></div>
            <div class="flex gap-3 justify-end">
                <button onclick="closeModal()" class="px-5 py-2 border border-slate-200 rounded-lg text-sm">取消</button>
                <button onclick="doReviewAppeal(${id}, false)" class="px-5 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600">驳回</button>
                <button onclick="doReviewAppeal(${id}, true)" class="px-5 py-2 bg-emerald-500 text-white rounded-lg text-sm hover:bg-emerald-600">通过并重算</button>
            </div>
        </div>`);
    } catch (e) { toast(e.message, 'error'); }
}

async function doReviewAppeal(id, approved) {
    const comments = document.getElementById('review-comments')?.value;
    if (!comments) { toast('请填写复核意见', 'warning'); return; }
    try {
        await api(`/api/workflow/appeals/${id}/review`, { method: 'POST', body: JSON.stringify({ approved, review_comments: comments }) });
        toast('复核完成', 'success'); closeModal(); loadPendingAppeals(); loadMyAppeals();
    } catch (e) { toast(e.message, 'error'); }
}

async function renderReports() {
    const container = document.getElementById('page-reports');
    const now = new Date(); const year = now.getFullYear(); const month = now.getMonth() + 1;
    container.innerHTML = `
        <div class="bg-white rounded-2xl p-6 shadow-sm">
            <div class="flex items-center justify-between">
                <h3 class="font-bold text-slate-800">月度分析报告</h3>
                <div class="flex items-center gap-2">
                    <select id="rp-year" class="px-3 py-2 border border-slate-200 rounded-lg text-sm">${[year, year-1, year-2].map(y => `<option value="${y}" ${y===year?'selected':''}>${y}</option>`).join('')}</select>
                    <select id="rp-month" class="px-3 py-2 border border-slate-200 rounded-lg text-sm">${Array.from({length:12}, (_,i)=>i+1).map(m => `<option value="${m}" ${m===month?'selected':''}>${m}月</option>`).join('')}</select>
                    <button onclick="generateReport()" class="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700"><i class="fas fa-wand-magic-sparkles mr-1"></i>生成报告</button>
                </div>
            </div>
        </div>
        <div class="bg-white rounded-2xl p-6 shadow-sm">
            <div class="flex items-center justify-between mb-4"><h3 class="font-bold text-slate-800">历史报告列表</h3><button onclick="loadReportList()" class="text-sm text-primary-600 hover:underline"><i class="fas fa-sync mr-1"></i>刷新</button></div>
            <div id="report-list"></div>
        </div>
        <div class="grid grid-cols-2 gap-6">
            <div class="bg-white rounded-2xl p-6 shadow-sm"><h3 class="font-bold text-slate-800 mb-4">佣金规则配置</h3><div id="comm-rules" class="text-sm"></div></div>
            <div class="bg-white rounded-2xl p-6 shadow-sm"><h3 class="font-bold text-slate-800 mb-4">返利规则配置</h3><div id="rb-rules" class="text-sm"></div></div>
        </div>
    `;
    loadReportList();
    loadRules();
}

async function generateReport() {
    const year = +document.getElementById('rp-year').value;
    const month = +document.getElementById('rp-month').value;
    try { await api(`/api/reports/generate-monthly?year=${year}&month=${month}`, { method: 'POST' }); toast('报告已生成', 'success'); loadReportList(); }
    catch (e) { toast(e.message, 'error'); }
}

async function loadReportList() {
    try {
        const reports = (await api('/api/reports/list')).data.reports || [];
        document.getElementById('report-list').innerHTML = reports.length === 0 ? '<div class="text-slate-400 text-sm">暂无报告</div>' : `
            <table class="w-full text-sm"><thead class="text-slate-500"><tr>
                <th class="text-left py-2">报告编号</th><th class="text-left py-2">标题</th><th class="text-left py-2">周期</th>
                <th class="text-left py-2">生成时间</th><th class="text-center py-2">自动</th><th class="text-center py-2">下载</th>
            </tr></thead><tbody>
                ${reports.map(r => `<tr class="border-t border-slate-100">
                    <td class="py-2 font-mono text-xs">${r.code}</td>
                    <td class="py-2">${r.title}</td>
                    <td class="py-2">${r.period}</td>
                    <td class="py-2 text-slate-500">${new Date(r.generated_at).toLocaleString('zh-CN')}</td>
                    <td class="py-2 text-center">${r.is_auto ? '<i class="fas fa-check text-green-500"></i>' : '-'}</td>
                    <td class="py-2 text-center">
                        ${r.has_pdf ? `<a href="/api/reports/${r.id}/download?format=pdf" target="_blank" class="text-red-500 hover:underline text-xs mr-2"><i class="fas fa-file-pdf mr-1"></i>PDF</a>` : ''}
                        ${r.has_excel ? `<a href="/api/reports/${r.id}/download?format=excel" target="_blank" class="text-green-600 hover:underline text-xs"><i class="fas fa-file-excel mr-1"></i>Excel</a>` : ''}
                    </td>
                </tr>`).join('')}
            </tbody></table>
        `;
    } catch (e) {}
}

async function loadRules() {
    try {
        const cr = await api('/api/reports/rules/commission');
        const rr = await api('/api/reports/rules/rebate');
        document.getElementById('comm-rules').innerHTML = `
            <div class="mb-3 font-medium text-slate-600">阶梯佣金规则</div>
            <table class="w-full text-xs"><thead class="bg-slate-50"><tr><th class="px-2 py-1.5 text-left">名称</th><th class="px-2 py-1.5 text-left">产品</th><th class="px-2 py-1.5 text-left">客户</th><th class="px-2 py-1.5 text-right">基础率</th><th class="px-2 py-1.5 text-right">奖励率</th></tr></thead><tbody>
                ${(cr.data.tier_rules || []).map(r => `<tr class="border-t border-slate-100"><td class="px-2 py-1.5">${r.name}</td><td class="px-2 py-1.5">${r.category || '全部'}</td><td class="px-2 py-1.5">${r.customer_level || '全部'}</td><td class="px-2 py-1.5 text-right">${(r.base_rate*100).toFixed(2)}%</td><td class="px-2 py-1.5 text-right text-amber-600">${(r.bonus_rate*100).toFixed(2)}%</td></tr>`).join('')}
            </tbody></table>
            <div class="mt-4 mb-2 font-medium text-slate-600">额外奖励规则</div>
            <table class="w-full text-xs"><thead class="bg-slate-50"><tr><th class="px-2 py-1.5 text-left">名称</th><th class="px-2 py-1.5 text-right">门槛</th><th class="px-2 py-1.5 text-right">奖励</th></tr></thead><tbody>
                ${(cr.data.bonus_rules || []).map(r => `<tr class="border-t border-slate-100"><td class="px-2 py-1.5">${r.name}</td><td class="px-2 py-1.5 text-right">${fmtMoney(r.threshold)}</td><td class="px-2 py-1.5 text-right text-emerald-600">${r.bonus ? fmtMoney(r.bonus) : (r.percentage*100).toFixed(2) + '%'}</td></tr>`).join('')}
            </tbody></table>
        `;
        document.getElementById('rb-rules').innerHTML = `
            <table class="w-full text-xs"><thead class="bg-slate-50"><tr><th class="px-2 py-1.5 text-left">名称</th><th class="px-2 py-1.5 text-left">级别</th><th class="px-2 py-1.5 text-right">返利率</th><th class="px-2 py-1.5 text-right">奖励率</th></tr></thead><tbody>
                ${(rr.data.rules || []).map(r => `<tr class="border-t border-slate-100"><td class="px-2 py-1.5">${r.name}</td><td class="px-2 py-1.5">${r.tier || '全部'}</td><td class="px-2 py-1.5 text-right">${(r.rate*100).toFixed(2)}%</td><td class="px-2 py-1.5 text-right text-amber-600">${(r.bonus_rate*100).toFixed(2)}%</td></tr>`).join('')}
            </tbody></table>
        `;
    } catch (e) {}
}

async function renderCalc() {
    const container = document.getElementById('page-calc');
    const now = new Date(); const year = now.getFullYear(); const month = now.getMonth() + 1; const q = Math.ceil(month / 3);
    container.innerHTML = `
        <div class="grid grid-cols-2 gap-6">
            <div class="bg-white rounded-2xl p-6 shadow-sm">
                <h3 class="font-bold text-slate-800 mb-4 flex items-center gap-2"><i class="fas fa-database text-primary-500"></i>数据同步</h3>
                <p class="text-sm text-slate-500 mb-4">从 CRM 和订单系统同步基础数据和销售订单。系统每日凌晨自动执行。</p>
                <div class="space-y-3">
                    <button onclick="runSync('crm')" class="w-full flex items-center justify-between px-4 py-3 border border-slate-200 rounded-xl hover:bg-primary-50 hover:border-primary-300 transition-all">
                        <span><i class="fas fa-users text-blue-500 mr-2"></i>同步 CRM 数据（客户、人员、渠道商、产品）</span>
                        <i class="fas fa-chevron-right text-slate-400"></i>
                    </button>
                    <button onclick="runSync('order')" class="w-full flex items-center justify-between px-4 py-3 border border-slate-200 rounded-xl hover:bg-primary-50 hover:border-primary-300 transition-all">
                        <span><i class="fas fa-file-invoice-dollar text-emerald-500 mr-2"></i>同步订单数据</span>
                        <i class="fas fa-chevron-right text-slate-400"></i>
                    </button>
                    <button onclick="runSync('all')" class="w-full flex items-center justify-between px-4 py-3 bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-xl hover:from-primary-700 hover:to-primary-800 transition-all">
                        <span><i class="fas fa-sync-alt mr-2"></i>一键同步全部数据</span>
                        <i class="fas fa-rocket"></i>
                    </button>
                </div>
                <div id="sync-result" class="mt-4"></div>
            </div>
            <div class="bg-white rounded-2xl p-6 shadow-sm">
                <h3 class="font-bold text-slate-800 mb-4 flex items-center gap-2"><i class="fas fa-calculator text-primary-500"></i>计算任务</h3>
                <p class="text-sm text-slate-500 mb-4">手动触发佣金和返利计算。每月1号自动计算上月佣金，每季度首月自动计算上季度返利。</p>
                <div class="space-y-4">
                    <div class="p-4 border border-slate-200 rounded-xl">
                        <div class="flex items-center gap-2 mb-3">
                            <span class="font-medium">月度佣金计算</span>
                        </div>
                        <div class="flex gap-2 mb-3">
                            <select id="calc-year" class="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm">${[year, year-1, year-2].map(y => `<option value="${y}" ${y===year?'selected':''}>${y}</option>`).join('')}</select>
                            <select id="calc-month" class="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm">${Array.from({length:12}, (_,i)=>i+1).map(m => `<option value="${m}" ${m===month?'selected':''}>${m}月</option>`).join('')}</select>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="calcCommission(false)" class="flex-1 px-3 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700">计算</button>
                            <button onclick="calcCommission(true)" class="flex-1 px-3 py-2 border border-red-200 text-red-600 rounded-lg text-sm hover:bg-red-50">强制重算</button>
                        </div>
                    </div>
                    <div class="p-4 border border-slate-200 rounded-xl">
                        <div class="flex items-center gap-2 mb-3">
                            <span class="font-medium">季度返利计算</span>
                        </div>
                        <div class="flex gap-2 mb-3">
                            <select id="calc-r-year" class="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm">${[year, year-1, year-2].map(y => `<option value="${y}" ${y===year?'selected':''}>${y}</option>`).join('')}</select>
                            <select id="calc-q" class="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm">${[1,2,3,4].map(x => `<option value="${x}" ${x===q?'selected':''}>Q${x}</option>`).join('')}</select>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="calcRebate(false)" class="flex-1 px-3 py-2 bg-emerald-500 text-white rounded-lg text-sm hover:bg-emerald-600">计算</button>
                            <button onclick="calcRebate(true)" class="flex-1 px-3 py-2 border border-red-200 text-red-600 rounded-lg text-sm hover:bg-red-50">强制重算</button>
                        </div>
                    </div>
                </div>
                <div id="calc-result" class="mt-4"></div>
            </div>
        </div>
        <div class="bg-white rounded-2xl p-6 shadow-sm">
            <h3 class="font-bold text-slate-800 mb-4 flex items-center gap-2"><i class="fas fa-clock text-primary-500"></i>定时任务配置</h3>
            <div class="grid grid-cols-5 gap-4 text-sm">
                <div class="p-4 bg-slate-50 rounded-xl"><div class="font-medium mb-1">数据同步</div><div class="text-xs text-slate-500">每日 01:30</div><i class="fas fa-check text-green-500 text-xs mt-1 block">已启用</i></div>
                <div class="p-4 bg-slate-50 rounded-xl"><div class="font-medium mb-1">佣金计算</div><div class="text-xs text-slate-500">每月1日 03:00</div><i class="fas fa-check text-green-500 text-xs mt-1 block">已启用</i></div>
                <div class="p-4 bg-slate-50 rounded-xl"><div class="font-medium mb-1">返利计算</div><div class="text-xs text-slate-500">每季首日 04:00</div><i class="fas fa-check text-green-500 text-xs mt-1 block">已启用</i></div>
                <div class="p-4 bg-slate-50 rounded-xl"><div class="font-medium mb-1">月度报告</div><div class="text-xs text-slate-500">每月5日 02:00</div><i class="fas fa-check text-green-500 text-xs mt-1 block">已启用</i></div>
                <div class="p-4 bg-slate-50 rounded-xl"><div class="font-medium mb-1">日志清理</div><div class="text-xs text-slate-500">每周日 05:00</div><i class="fas fa-check text-green-500 text-xs mt-1 block">已启用</i></div>
            </div>
        </div>
    `;
}

async function runSync(type) {
    try {
        const res = await api(`/api/calculation/sync?sync_type=${type}`, { method: 'POST' });
        document.getElementById('sync-result').innerHTML = `<div class="p-4 bg-green-50 text-green-800 rounded-xl text-sm"><pre>${JSON.stringify(res.data, null, 2)}</pre></div>`;
        toast('同步完成', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function calcCommission(force) {
    const body = { year: +document.getElementById('calc-year').value, month: +document.getElementById('calc-month').value, force_recalculate: force };
    try {
        const res = await api('/api/calculation/commission/calculate', { method: 'POST', body: JSON.stringify(body) });
        document.getElementById('calc-result').innerHTML = `<div class="p-4 bg-green-50 text-green-800 rounded-xl text-sm"><pre>${JSON.stringify(res.data, null, 2)}</pre></div>`;
        toast('佣金计算完成', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function calcRebate(force) {
    const body = { year: +document.getElementById('calc-r-year').value, quarter: +document.getElementById('calc-q').value, force_recalculate: force };
    try {
        const res = await api('/api/calculation/rebate/calculate', { method: 'POST', body: JSON.stringify(body) });
        document.getElementById('calc-result').innerHTML = `<div class="p-4 bg-green-50 text-green-800 rounded-xl text-sm"><pre>${JSON.stringify(res.data, null, 2)}</pre></div>`;
        toast('返利计算完成', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

if (TOKEN) { initApp(); }
