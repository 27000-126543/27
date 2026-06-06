import requests
import json
import time

BASE = "http://localhost:8000"

print("=" * 70)
print("专项测试：申诉复核流程 + 佣金重复计算 + 多产品类别")
print("=" * 70)

print("\n[0] 初始化 + 登录")
requests.post(f"{BASE}/api/auth/init-admin")
r = requests.post(f"{BASE}/api/auth/login", data={"username": "admin", "password": "admin123"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("  ✅ 登录成功")

print("\n[1] 同步基础数据 + 订单")
r = requests.post(f"{BASE}/api/calculation/sync?sync_type=all", headers=headers)
data = r.json()["data"]
print(f"  ✅ CRM同步: 客户{data['crm']['customers']} 销售{data['crm']['salespersons']} 渠道{data['crm']['partners']} 产品{data['crm']['products']}")
print(f"  ✅ 订单同步: {data['order']['processed']} 条订单")

print("\n[2] 第一次计算6月佣金")
r = requests.post(f"{BASE}/api/calculation/commission/calculate",
    headers=headers, json={"year": 2026, "month": 6, "force_recalculate": False})
d = r.json()["data"]
print(f"  ✅ 处理订单: {d['processed_orders']}, 创建记录: {d['created_records']}, 跳过: {d['skipped_records']}, 总佣金: ¥{d['total_amount']:,.2f}")
created_first = d["created_records"]

print("\n[3] 第二次计算（防重复测试）")
r = requests.post(f"{BASE}/api/calculation/commission/calculate",
    headers=headers, json={"year": 2026, "month": 6, "force_recalculate": False})
d = r.json()["data"]
print(f"  ✅ 处理订单: {d['processed_orders']}, 创建记录: {d['created_records']}, 跳过: {d['skipped_records']}")
if d["created_records"] == 0 and d["skipped_records"] > 0:
    print("  ✅ 防重复校验生效！第二次没有创建新记录")
else:
    print(f"  ⚠️ 可能有问题: 第二次还创建了 {d['created_records']} 条新记录")

print("\n[4] 验证一单多产品类别")
r = requests.post(f"{BASE}/api/calculation/commission/query",
    headers=headers, json={"period_year": 2026, "period_month": 6, "page": 1, "page_size": 100})
records = r.json()["data"]["records"]
order_categories = {}
for rec in records:
    oid = rec["order_id"]
    if oid not in order_categories:
        order_categories[oid] = []
    order_categories[oid].append(rec["product_category"])
multi_cat_orders = {oid: cats for oid, cats in order_categories.items() if len(cats) > 1}
if multi_cat_orders:
    print(f"  ✅ 存在 {len(multi_cat_orders)} 个订单含多个产品类别:")
    for oid, cats in list(multi_cat_orders.items())[:3]:
        print(f"     订单ID {oid}: {', '.join(cats)}")
else:
    print("  ℹ️ 当前数据中暂无一单多类别，需要验证record_code包含category")

print("\n[5] 测试佣金审批 + 申诉复核")
r = requests.post(f"{BASE}/api/calculation/commission/query",
    headers=headers, json={"period_year": 2026, "period_month": 6, "page": 1, "page_size": 5})
records = r.json()["data"]["records"]
target_rec = records[0]
print(f"  目标记录: {target_rec['code']} | {target_rec['salesperson_name']} | ¥{target_rec['total_commission']:,.2f} | {target_rec['product_category']}")

r = requests.post(f"{BASE}/api/workflow/commission/{target_rec['id']}/submit", headers=headers)
print(f"  ✅ 提交审批: {r.json()['message']}")

r = requests.post(f"{BASE}/api/workflow/commission/{target_rec['id']}/approve",
    headers=headers, json={"comments": "正常审批通过"})
print(f"  ✅ 审批通过: {r.json()['data']['status']}")

target_code = target_rec['code']
print(f"\n  提交申诉 (对 {target_code})")
r = requests.post(f"{BASE}/api/workflow/appeals", headers=headers, json={
    "appeal_type": "commission",
    "reason": "佣金计算可能有误，申请复核",
    "commission_record_id": target_rec["id"],
    "evidence": "合同金额与系统数据不符"
})
print(f"  ✅ 申诉提交: {r.json()['message']}, 申诉号: {r.json()['data']['appeal_code']}")

pending = requests.get(f"{BASE}/api/workflow/appeals/pending", headers=headers).json()["data"]["appeals"]
appeal_id = pending[0]["id"]
print(f"  获取待复核申诉: {len(pending)} 条, ID={appeal_id}")

r = requests.get(f"{BASE}/api/workflow/appeals/{appeal_id}", headers=headers)
detail = r.json()["data"]
print(f"  ✅ 申诉详情: 关联订单={len(detail.get('orders', []))} 条, 关联佣金={detail.get('commission_record', {}).get('code')}")

print(f"\n  复核申诉 #{appeal_id} (通过 + 自动重算)")
r = requests.post(f"{BASE}/api/workflow/appeals/{appeal_id}/review", headers=headers, json={
    "approved": True,
    "review_comments": "经核实，确实需要修正，已触发重算"
})
if r.status_code != 200:
    print(f"  ❌ 复核失败: {r.status_code} {r.text[:200]}")
else:
    rd = r.json()
    print(f"  ✅ 复核结果: {rd['message']}")
    print(f"     处理说明: {rd['data'].get('resolution', 'N/A')}")

print("\n[6] 验证原记录标记 is_corrected 且新记录 record_code 唯一")
r = requests.post(f"{BASE}/api/calculation/commission/query",
    headers=headers, json={"period_year": 2026, "period_month": 6, "page": 1, "page_size": 100})
all_records = r.json()["data"]["records"]

original = None
corrected_new = None
for rec in all_records:
    if rec["id"] == target_rec["id"]:
        original = rec
    if rec.get("original_record_id") == target_rec["id"]:
        corrected_new = rec

if original:
    print(f"  原记录 {original['code']}: is_corrected={original.get('is_corrected', 'N/A')}")
else:
    print("  ⚠️ 未找到原记录")

if corrected_new:
    print(f"  新记录 {corrected_new['code']}: ¥{corrected_new['total_commission']:,.2f}")
    print(f"     remarks: {corrected_new.get('remarks', 'N/A')}")
    print(f"     包含R修正标记: {'R' in corrected_new['code']}")
    if corrected_new["code"] != target_rec["code"]:
        print("  ✅ 新记录record_code与原记录不同，保证唯一性")
    else:
        print("  ❌ 新记录record_code与原记录重复！")
else:
    print("  ⚠️ 未找到修正后的新记录")

record_codes = [r["code"] for r in all_records]
if len(record_codes) == len(set(record_codes)):
    print(f"  ✅ 全部 {len(record_codes)} 条佣金记录的 record_code 唯一，无重复")
else:
    print(f"  ❌ 存在重复的 record_code！")

print("\n" + "=" * 70)
print("所有专项测试完成！")
print("=" * 70)
