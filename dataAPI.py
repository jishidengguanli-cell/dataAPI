import os
import shutil
import json
import csv
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
import asyncio
import time

# ======================== 基本設定 ========================
TARGET_TW_HOUR = 0
TARGET_TW_MINUTE = 1

TELEGRAM_API_ID = 20304868
TELEGRAM_API_HASH = '2d0fba4d7d3725443b4bc398a3097897'
TELEGRAM_SESSION = 'user'
TELEGRAM_GROUP_ID = -4913948412
TELEGRAM_GROUP_ID2 = -4913948412

zh_font = fm.FontProperties(fname="/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc")
# zh_font = fm.FontProperties(fname="C:/Windows/Fonts/msjh.ttc")


# ======================== 兩組專案配置 ========================
PROJECTS = [
    {
        "name": "AI",
        "region": "cn-hangzhou",
        "ecs_info": {
            "i-bp1g277zg9kr572u5quv": "ai-20250704",
            "i-bp1hcuque34pzzb8168j": "ai0704主定时任务",
            "i-bp1aes2nyk1x3c9855t5": "kf_0719"
        },
        "rds_instance": "rm-bp15n5674aexk1eqy",
        "redis_instance": "r-bp157ei747pqpo841v",
        "access_key_id": os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'],
        "access_key_secret": os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET'],
    },
    {
        "name": "醫療",
        "region": "cn-shenzhen",
        "ecs_info": {
            "i-wz94wiykw1yc2o625fsz": "医疗-后台-20250823",
            "i-wz9ih1zuo8ucb196c0un": "医疗-202508191304",
            "i-wz9i9pgld1t1qucumanj": "launch-advisor-20250731",
            "i-wz98ymajhdog9vp01v2w": "AI-20250731"
        },
        "rds_instance": "rm-wz9laki2z98go38rp",
        "redis_instance": "r-wz9dshkdd6oklqqxjb",
        "access_key_id": os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID_2'],
        "access_key_secret": os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET_2'],
    },
    {
        "name": "越直播",
        "region": "ap-southeast-7",
        "ecs_info": {
            "i-0joi9y7r33g9sgl4o5i9": "node",
            "i-0joi9y7r33g9nb482zr4": "主-ht"
        },
        "rds_instance": "rm-0jo09sr8094jkhkjw",
        "redis_instance": "r-0jolmxjgeedz20d0jl",
        "access_key_id": os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID_3'],
        "access_key_secret": os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET_3'],
    }
]

# ======================== 共用時間處理 ========================
def get_tw_utc_range_for_yesterday():
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz=tz_tw)
    target_tw_date = now_tw.date() - timedelta(days=1)
    tw_start = datetime.combine(target_tw_date, datetime.min.time(), tzinfo=tz_tw)
    tw_end = tw_start + timedelta(hours=23, minutes=59, seconds=59)
    start_utc = tw_start.astimezone(timezone.utc)
    end_utc = tw_end.astimezone(timezone.utc)
    return tw_start, tw_end, start_utc, end_utc

def tw_time(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=8)))

def ensure_folder(day_str):
    if not os.path.isdir(day_str):
        os.mkdir(day_str)

def cleanup_old_folder(old_day_str):
    if os.path.isdir(old_day_str):
        shutil.rmtree(old_day_str)

# ======================== ECS/RDS/Redis CSV ========================
def fetch_and_save_ecs_csv(project, day_dir, date_str, start_utc, end_utc):
    client = AcsClient(project['access_key_id'], project['access_key_secret'], project['region'])
    for INSTANCE_ID, ECS_NAME in project['ecs_info'].items():
        ecs_data = []
        curr = start_utc
        while curr < end_utc:
            next_t = min(curr + timedelta(hours=1), end_utc)
            req = CommonRequest()
            if(project['name']=="越直播"):
                req.set_domain('ecs.ap-southeast-7.aliyuncs.com')
            else: 
                req.set_domain('ecs.aliyuncs.com')
            req.set_version('2014-05-26')
            req.set_action_name('DescribeInstanceMonitorData')
            req.set_method('POST')
            req.add_query_param('InstanceId', INSTANCE_ID)
            req.add_query_param('StartTime', curr.strftime('%Y-%m-%dT%H:%M:%SZ'))
            req.add_query_param('EndTime', next_t.strftime('%Y-%m-%dT%H:%M:%SZ'))
            req.add_query_param('Period', 60)
            resp = client.do_action_with_exception(req)
            resp_json = json.loads(resp)
            data = resp_json.get("MonitorData", {}).get("InstanceMonitorData", [])
            ecs_data.extend(data)
            curr = next_t
        rows = []
        for v in ecs_data:
            try:
                utc_time = datetime.strptime(v["TimeStamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                tw_dt = tw_time(utc_time)
                row = {
                    "UTC_Time": utc_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "TW_Time": tw_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "CPU": v.get("CPU", ""),
                    "IntranetTX": v.get("IntranetTX", ""),
                    "IntranetRX": v.get("IntranetRX", ""),
                    "InternetTX": v.get("InternetTX", ""),
                    "InternetRX": v.get("InternetRX", ""),
                    "BPSRead": v.get("BPSRead", ""),
                    "BPSWrite": v.get("BPSWrite", ""),
                    "IOPSRead": v.get("IOPSRead", ""),
                    "IOPSWrite": v.get("IOPSWrite", "")
                }
                rows.append(row)
            except Exception as e:
                continue
        out_csv = os.path.join(day_dir, f"{project['name']}_ecs_{ECS_NAME}_{date_str}.csv")
        if rows:
            with open(out_csv, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            print(f"✅ [{project['name']}] ECS {ECS_NAME} 資料存成 {out_csv}")

def fetch_and_save_rds_csv(project, day_dir, date_str, start_utc, end_utc):
    client = AcsClient(project['access_key_id'], project['access_key_secret'], project['region'])
    keys_list = [
        ("MySQL_MemCpuUsage", ["CPU", "Memory"]),
        ("MySQL_DetailedSpaceUsage", ["ins_size", "data_size", "log_size", "tmp_size", "other_size"]),
        ("MySQL_IOPS", ["IOPS"]),
        ("MySQL_QPSTPS", ["QPS", "TPS"]),
        ("MySQL_InnoDBDataReadWriten", ["ReadKBs", "WriteKBs"]),
        ("MySQL_MBPS", ["MBPS"]),
        ("MySQL_Sessions", ["ActiveSessions", "TotalSessions"]),
        ("MySQL_COMDML", ["Delete", "Insert", "Insert_Select", "Replace", "Replace_Select", "Select", "Update"])
    ]
    all_data = {}
    for key, cols in keys_list:
        req = CommonRequest()
        if(project['name']=="越直播"):
            req.set_domain('rds.ap-southeast-7.aliyuncs.com')
        else:
            req.set_domain('rds.aliyuncs.com')
        req.set_version('2014-08-15')
        req.set_action_name('DescribeDBInstancePerformance')
        req.set_method('POST')
        req.add_query_param('DBInstanceId', project['rds_instance'])
        req.add_query_param('Key', key)
        req.add_query_param('StartTime', start_utc.strftime('%Y-%m-%dT%H:%MZ'))
        req.add_query_param('EndTime', end_utc.strftime('%Y-%m-%dT%H:%MZ'))
        resp = client.do_action_with_exception(req)
        result = json.loads(resp)
        perf = result["PerformanceKeys"]["PerformanceKey"][0]["Values"]["PerformanceValue"]
        for idx, item in enumerate(perf):
            if isinstance(item, str):
                dt_str, val_str = item.split(",", 1)
            else:
                dt_str = item["Date"]
                val_str = item["Value"]
            utc_dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            tw_dt = tw_time(utc_dt)
            tw_dt_str = tw_dt.strftime("%Y-%m-%d %H:%M:%S")
            if tw_dt_str not in all_data:
                all_data[tw_dt_str] = {
                    "UTC_Time": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "TW_Time": tw_dt_str
                }
            parts = val_str.split("&")
            for i, c in enumerate(cols):
                all_data[tw_dt_str][c] = float(parts[i]) if i < len(parts) else ""
    out_csv = os.path.join(day_dir, f"{project['name']}_rds_{date_str}.csv")
    keys = ["UTC_Time", "TW_Time"] + [c for k, cols in keys_list for c in cols]
    if all_data:
        with open(out_csv, "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in sorted(all_data.values(), key=lambda x: x['TW_Time']):
                writer.writerow(row)
        print(f"✅ [{project['name']}] RDS 資料存成 {out_csv}")

def fetch_and_save_redis_csv(project, day_dir, date_str, start_utc, end_utc):
    client = AcsClient(project['access_key_id'], project['access_key_secret'], project['region'])
    metrics = [
        ("CpuUsage", ["CpuUsage"]),
        ("MemoryUsage", ["memoryUsage"]),
        ("UsedMemory", ["UsedMemory"]),
        ("UsedQPS", ["TotalQps", "GetQps", "PutQps", "OtherOps"]),
        ("ConnectionUsage", ["connectionUsage"]),
        ("UsedConnection", ["ConnCount"]),
        ("IntranetIn,IntranetOut", ["InFlow", "OutFlow"]),
        ("IntranetInRatio,IntranetOutRatio", ["intranetInRatio", "intranetOutRatio"])
    ]
    data_dict = {}
    for metric_keys, cols in metrics:
        req = CommonRequest()
        if(project['name']=="越直播"):
            req.set_domain('r-kvstore.ap-southeast-7.aliyuncs.com')
        else:
            req.set_domain('r-kvstore.aliyuncs.com')
        req.set_version('2015-01-01')
        req.set_action_name('DescribeHistoryMonitorValues')
        req.set_method('POST')
        req.add_query_param('InstanceId', project['redis_instance'])
        req.add_query_param('StartTime', start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'))
        req.add_query_param('EndTime', end_utc.strftime('%Y-%m-%dT%H:%M:%SZ'))
        req.add_query_param('IntervalForHistory', '01m')
        req.add_query_param('MonitorKeys', metric_keys)
        resp = client.do_action_with_exception(req)
        result = json.loads(resp)
        d = json.loads(result.get("MonitorHistory", "{}"))
        for ts, row in d.items():
            utc_dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            tw_dt = tw_time(utc_dt)
            tw_dt_str = tw_dt.strftime("%Y-%m-%d %H:%M:%S")
            if tw_dt_str not in data_dict:
                data_dict[tw_dt_str] = {
                    "UTC_Time": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "TW_Time": tw_dt_str
                }
            for c in cols:
                data_dict[tw_dt_str][c] = row.get(c, "")
    out_csv = os.path.join(day_dir, f"{project['name']}_redis_{date_str}.csv")
    all_cols = ["UTC_Time", "TW_Time"] + [c for _, cols in metrics for c in cols]
    if data_dict:
        with open(out_csv, "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_cols)
            writer.writeheader()
            for row in sorted(data_dict.values(), key=lambda x: x['TW_Time']):
                writer.writerow(row)
        print(f"✅ [{project['name']}] Redis 資料存成 {out_csv}")

# ======================== 畫圖（讀csv） ========================
def plot_ecs_from_csv(project, day_dir, date_str):
    for ECS_NAME in project['ecs_info'].values():
        csv_file = os.path.join(day_dir, f"{project['name']}_ecs_{ECS_NAME}_{date_str}.csv")
        if not os.path.isfile(csv_file):
            continue
        df = pd.read_csv(csv_file, parse_dates=['TW_Time'])
        fig, axs = plt.subplots(3, 2, figsize=(18, 14))
        axs = axs.flatten()
        axs[0].plot(df['TW_Time'], df['CPU'], color='blue', label='CPU')
        axs[0].set_title("CPU使用率 (%)", fontproperties=zh_font, fontsize=13)
        axs[0].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[0].xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,3)))
        axs[0].legend(); axs[0].grid(True, linestyle="--", alpha=0.5)
        axs[1].plot(df['TW_Time'], df['IntranetTX'], color='green', label='IntranetTX')
        axs[1].plot(df['TW_Time'], df['IntranetRX'], color='orange', label='IntranetRX')
        axs[1].set_title("總帶寬 (bit/s)", fontproperties=zh_font, fontsize=13)
        axs[1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[1].xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,3)))
        axs[1].legend(); axs[1].grid(True, linestyle="--", alpha=0.5)
        axs[2].plot(df['TW_Time'], df['InternetTX'], color='blue', label='InternetTX')
        axs[2].plot(df['TW_Time'], df['InternetRX'], color='red', label='InternetRX')
        axs[2].set_title("公网帶寬 (bit/s)", fontproperties=zh_font, fontsize=13)
        axs[2].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[2].xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,3)))
        axs[2].legend(); axs[2].grid(True, linestyle="--", alpha=0.5)
        axs[3].plot(df['TW_Time'], df['BPSRead'], color='purple', label='BPSRead')
        axs[3].plot(df['TW_Time'], df['BPSWrite'], color='brown', label='BPSWrite')
        axs[3].set_title("磁碟讀寫BPS (bytes/s)", fontproperties=zh_font, fontsize=13)
        axs[3].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[3].xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,3)))
        axs[3].legend(); axs[3].grid(True, linestyle="--", alpha=0.5)
        axs[4].plot(df['TW_Time'], df['IOPSRead'], color='black', label='IOPSRead')
        axs[4].plot(df['TW_Time'], df['IOPSWrite'], color='gray', label='IOPSWrite')
        axs[4].set_title("磁碟讀寫IOPS (Count/Second)", fontproperties=zh_font, fontsize=13)
        axs[4].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[4].xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,3)))
        axs[4].legend(); axs[4].grid(True, linestyle="--", alpha=0.5)
        axs[5].axis('off')
        axs[5].text(0.5, 0.5, f"ECS監控彙總\n{ECS_NAME}", ha='center', va='center', fontproperties=zh_font, fontsize=18)
        plt.tight_layout()
        out_name = os.path.join(day_dir, f"{project['name']}_ecs_{ECS_NAME}_{date_str}.png")
        plt.savefig(out_name)
        plt.close()
        print(f"✅ [{project['name']}] ECS 圖表已輸出：{out_name}")

def plot_rds_from_csv(project, day_dir, date_str):
    csv_file = os.path.join(day_dir, f"{project['name']}_rds_{date_str}.csv")
    if not os.path.isfile(csv_file):
        return
    df = pd.read_csv(csv_file, parse_dates=['TW_Time'])
    fig, axs = plt.subplots(3, 3, figsize=(22, 16))
    axs = axs.flatten()
    axs[0].plot(df['TW_Time'], df['CPU'], label='CPU (%)', color='blue')
    axs[0].plot(df['TW_Time'], df['Memory'], label='Memory (%)', color='green')
    axs[0].set_title("MySQL CPU/內存利用率", fontproperties=zh_font, fontsize=13)
    axs[1].plot(df['TW_Time'], df['ins_size'], label='ins_size', color='purple')
    axs[1].plot(df['TW_Time'], df['data_size'], label='data_size', color='green')
    axs[1].plot(df['TW_Time'], df['log_size'], label='log_size', color='blue')
    axs[1].plot(df['TW_Time'], df['tmp_size'], label='tmp_size', color='orange')
    axs[1].plot(df['TW_Time'], df['other_size'], label='other_size', color='gray')
    axs[1].set_title("MySQL 空間使用量 (MB)", fontproperties=zh_font, fontsize=13)
    axs[2].plot(df['TW_Time'], df['IOPS'], label='IOPS', color='red')
    axs[2].set_title("MySQL IOPS 使用率", fontproperties=zh_font, fontsize=13)
    axs[3].plot(df['TW_Time'], df['QPS'], label='QPS', color='blue')
    axs[3].plot(df['TW_Time'], df['TPS'], label='TPS', color='green')
    axs[3].set_title("TPS/QPS", fontproperties=zh_font, fontsize=13)
    axs[4].plot(df['TW_Time'], df['ReadKBs'], label='Read KB/s', color='blue')
    axs[4].plot(df['TW_Time'], df['WriteKBs'], label='Write KB/s', color='green')
    axs[4].set_title("InnoDB Data 讀寫吞吐量(KB)", fontproperties=zh_font, fontsize=13)
    axs[5].plot(df['TW_Time'], df['MBPS'], label='MBPS', color='blue')
    axs[5].set_title("MySQL每秒讀寫吞吐量(B)", fontproperties=zh_font, fontsize=13)
    axs[6].plot(df['TW_Time'], df['ActiveSessions'], label='Active', color='orange')
    axs[6].plot(df['TW_Time'], df['TotalSessions'], label='Total', color='gray')
    axs[6].set_title("會話連接", fontproperties=zh_font, fontsize=13)
    axs[7].plot(df['TW_Time'], df['Delete'], label='Delete', color='red')
    axs[7].plot(df['TW_Time'], df['Insert'], label='Insert', color='green')
    axs[7].plot(df['TW_Time'], df['Insert_Select'], label='Insert_Select', color='blue')
    axs[7].plot(df['TW_Time'], df['Replace'], label='Replace', color='orange')
    axs[7].plot(df['TW_Time'], df['Replace_Select'], label='Replace_Select', color='purple')
    axs[7].plot(df['TW_Time'], df['Select'], label='Select', color='gray')
    axs[7].plot(df['TW_Time'], df['Update'], label='Update', color='brown')
    axs[7].set_title("執行次數", fontproperties=zh_font, fontsize=13)
    if 'MBPS' in df.columns:
        axs[8].plot(df['TW_Time'], df['MBPS']/3_000_000, label='MBPS Rate %', color='blue')
    axs[8].set_title("MySQL MBPS使用率(%)", fontproperties=zh_font, fontsize=13)
    for ax in axs:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,3)))
        ax.legend(); ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    out_name = os.path.join(day_dir, f"{project['name']}_rds_{date_str}.png")
    plt.savefig(out_name)
    plt.close()
    print(f"✅ [{project['name']}] RDS 圖表已輸出：{out_name}")

def plot_redis_from_csv(project, day_dir, date_str):
    csv_file = os.path.join(day_dir, f"{project['name']}_redis_{date_str}.csv")
    if not os.path.isfile(csv_file):
        return
    df = pd.read_csv(csv_file, parse_dates=['TW_Time'])
    metrics = [
        (['CpuUsage'], "CPU使用率 (%)"),
        (['memoryUsage'], "內存使用率 (%)"),
        (['UsedMemory'], "已使用內存總量 (Byte)"),
        (['TotalQps', 'GetQps', 'PutQps', 'OtherOps'], "請求數 (Counts/s)"),
        (['connectionUsage'], "連線數使用率 (%)"),
        (['ConnCount'], "已使用連線數 (Counts)"),
        (['InFlow', 'OutFlow'], "出/入口流量速率 (KBps)"),
        (['intranetInRatio', 'intranetOutRatio'], "出/入口流量使用率 (%)"),
    ]
    fig, axs = plt.subplots(4, 2, figsize=(32, 12))
    axs = axs.flatten()
    for idx, (cols, title) in enumerate(metrics):
        for col in cols:
            if col in df.columns:
                axs[idx].plot(df['TW_Time'], df[col], label=col)
        axs[idx].set_title(title, fontproperties=zh_font, fontsize=15)
        axs[idx].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[idx].xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,3)))
        axs[idx].legend(); axs[idx].grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    out_name = os.path.join(day_dir, f"{project['name']}_redis_{date_str}.png")
    plt.savefig(out_name)
    plt.close()
    print(f"✅ [{project['name']}] Redis 指標彙總圖表已輸出：{out_name}")
    
# ======================== Telegram 傳圖 ========================
PROJECT_ORDER = ["AI", "醫療"]
TYPE_ORDER = ["_ecs", "_rds", "_redis"]

def _project_of(fname: str) -> str:
    """以檔名第一段(遇到第一個底線前)當作專案名，例如 AI_xxx.png -> 'AI'。"""
    name, _ = os.path.splitext(fname)
    return name.split("_", 1)[0]

async def send_all_images(folder):
    files = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
    files.sort()  # 穩定排序

    # 找出實際存在的專案，組成最終順序：先照 PROJECT_ORDER，再補上其餘
    projects_found = []
    for f in files:
        p = _project_of(f)
        if p not in projects_found:
            projects_found.append(p)
    ordered_projects = [p for p in PROJECT_ORDER if p in projects_found] + \
                       [p for p in projects_found if p not in PROJECT_ORDER]

    async with TelegramClient(TELEGRAM_SESSION, TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
        sent = set()

        for proj in ordered_projects:
            # 依 TYPE_ORDER 傳送該專案底下檔案
            for t in TYPE_ORDER:
                batch = [f for f in files
                         if f not in sent
                         and _project_of(f) == proj
                         and t in f]
                for fname in batch:
                    path = os.path.join(folder, fname)
                    print(f"正在傳送 {fname} ...")
                    await client.send_file(
                        TELEGRAM_GROUP_ID,
                        path,
                        caption=fname,
                        force_document=False
                    )
                    print(f"✅ 傳送完成：{fname}")
                    sent.add(fname)
        # await client.send_message(TELEGRAM_GROUP_CONFIRM_ID, "✅ 每日截圖任務完成")
    print("🎉 所有圖檔都已依專案與類型順序送出 Telegram。")


async def send_all_csvs(folder):
    files = [f for f in os.listdir(folder) if f.lower().endswith(".csv")]
    if not files:
        print("⚠️ 資料夾沒有 .csv 檔")
        return

    # 依檔名前綴找出實際存在的專案，並套用既定順序
    projects_found = []
    for f in sorted(files):
        p = _project_of(f)
        if p not in projects_found:
            projects_found.append(p)
    ordered_projects = [p for p in PROJECT_ORDER if p in projects_found] + \
                       [p for p in projects_found if p not in PROJECT_ORDER]

    async with TelegramClient(TELEGRAM_SESSION, TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
        for proj in ordered_projects:
            for typ in TYPE_ORDER:
                batch = [f for f in files if _project_of(f) == proj and typ in f]
                for fname in sorted(batch):
                    path = os.path.join(folder, fname)
                    print(f"正在傳送 {fname} ...")
                    await client.send_file(
                        TELEGRAM_GROUP_ID2,
                        path,
                        caption=fname,
                        force_document=True  # 以文件形式傳送 .csv
                    )
                    print(f"✅ 傳送完成：{fname}")
        # await client.send_message(TELEGRAM_GROUP_CONFIRM_ID, "✅ 每日截圖任務完成")
    print("🎉 所有 .csv 檔已依專案與類型順序送出。")
    

# ======================== Main 自動排程循環 ========================
def main():
    while True:
        # 等待到指定台灣時間
        while True:
            now = datetime.now(timezone.utc)
            now_tw = now + timedelta(hours=8)
            if now_tw.hour == TARGET_TW_HOUR and now_tw.minute == TARGET_TW_MINUTE:
                break
            print("⏳ 等待到%02d:%02d再開始資料匯出... (台灣時間 %s)" %
                  (TARGET_TW_HOUR, TARGET_TW_MINUTE, now_tw.strftime("%H:%M:%S")))
            time.sleep(30)

        tw_start, tw_end, utc_start, utc_end = get_tw_utc_range_for_yesterday()
        date_str = tw_start.strftime('%Y_%m_%d')
        old_date_str = (tw_start - timedelta(days=1)).strftime('%Y_%m_%d')
        ensure_folder(date_str)
        cleanup_old_folder(old_date_str)

        # 兩組專案都執行
        for project in PROJECTS:
            print(f"\n===== 【{project['name']}】專案：開始抓資料存csv {date_str} ... =====")
            fetch_and_save_ecs_csv(project, date_str, date_str, utc_start, utc_end)
            fetch_and_save_rds_csv(project, date_str, date_str, utc_start, utc_end)
            fetch_and_save_redis_csv(project, date_str, date_str, utc_start, utc_end)
            print(f"===== 【{project['name']}】專案：CSV 全部完成 =====")

            print(f"===== 【{project['name']}】專案：畫圖中 ... =====")
            plot_ecs_from_csv(project, date_str, date_str)
            plot_rds_from_csv(project, date_str, date_str)
            plot_redis_from_csv(project, date_str, date_str)
            print(f"===== 【{project['name']}】專案：圖表全部完成 =====")

        print("⏳ 開始自動傳送所有圖檔到 Telegram 群組 ...")
        asyncio.run(send_all_images(date_str))
        asyncio.run(send_all_csvs(date_str))
        
        print("😴 今日任務完成，準備等到明天繼續 ...")
        # 等到明天新的一輪
        while True:
            now = datetime.now(timezone.utc)
            now_tw = now + timedelta(hours=8)
            if now_tw.hour < TARGET_TW_HOUR or (now_tw.hour == TARGET_TW_HOUR and now_tw.minute < TARGET_TW_MINUTE):
                print("⏳ 等待到%02d:%02d再開始資料匯出... (台灣時間 %s)" %
                      (TARGET_TW_HOUR, TARGET_TW_MINUTE, now_tw.strftime("%H:%M:%S")))
                time.sleep(30)
            else:
                break

if __name__ == "__main__":
    main()
