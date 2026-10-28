# -*- coding: utf-8 -*-
"""京津冀医院招标信息采集器（政府采购公开信息）
来源：河北省政府采购网 / 天津市政府采购网 / 北京市政府采购网 / 中国政府采购网
"""
import json, os, re, sys, time, hashlib
import urllib.request
from urllib.parse import urljoin
from datetime import datetime, timedelta, timezone
from lxml import html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE, "data.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CN_TZ = timezone(timedelta(hours=8))
FOCUS_CATEGORIES = ["检验科"]

def now_cn():
    return datetime.now(CN_TZ)

def fetch(url, timeout=25, retries=2, referer=None):
    last = None
    for i in range(retries + 1):
        try:
            headers = {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            raw = urllib.request.urlopen(req, timeout=timeout).read()
            s = None
            for enc in ("utf-8", "gb18030"):
                try:
                    cand = raw.decode(enc)
                    if "\ufffd" not in cand[:4000]:
                        s = cand
                        break
                except Exception:
                    pass
            if s is None:
                s = raw.decode("gb18030", "ignore")
            # 河北站点偶发返回 JS 反爬挑战页，退避后重试
            if "Please enable JavaScript" in s[:2000]:
                last = Exception("anti-bot challenge")
                time.sleep(4 + i * 4)
                continue
            return s
        except Exception as e:
            last = e
            time.sleep(1 + i)
    raise last

def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def absolute(base, href):
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        return "http:" + href
    return urljoin(base, href)

# ---------------- 品类 ----------------
CATS = [
    ("检验科", ["试剂", "检验", "生化", "免疫", "分子诊断", "分子检测", "微生物", "临检", "POCT", "质谱", "流式", "血凝", "凝血", "血气", "培养", "药敏", "核酸", "抗原", "抗体", "体外诊断", "IVD", "采血", "输血", "血库", "LIS", "分析仪", "血球", "尿液分析", "化学发光", "酶标", "洗板", "加样", "移液", "离心机", "生物安全柜", "培养箱", "质控", "校准"]),
    ("影像设备", ["CT", "MR", "磁共振", "DR", "X射线", "X光", "超声", "彩超", "B超", "内镜", "胃肠镜", "核医学", "PET", "DSA", "造影", "钼靶", "放射"]),
    ("手术麻醉ICU", ["麻醉", "监护", "呼吸机", "输注泵", "手术床", "无影灯", "吊塔", "电刀", "超声刀", "手术室", "ICU", "重症", "除颤"]),
    ("骨科", ["骨科", "关节", "脊柱", "创伤", "人工骨"]),
    ("口腔", ["口腔", "牙科", "种植", "正畸"]),
    ("眼科", ["眼科", "眼底", "验光", "角膜"]),
    ("康复", ["康复", "理疗", "支具"]),
    ("透析", ["透析", "血滤", "水处理"]),
    ("消毒供应", ["消毒", "灭菌", "清洗", "供应室"]),
    ("病理", ["病理", "切片", "染色", "包埋"]),
    ("高值耗材", ["支架", "导管", "球囊", "起搏器", "人工晶体", "吻合器", "介入"]),
    ("低值耗材", ["耗材", "敷料", "注射器", "输液器", "口罩", "手套"]),
    ("医疗信息化", ["HIS", "PACS", "LIS", "电子病历", "信息系统", "信息化", "数据平台"]),
    ("医疗服务", ["医疗服务", "能力提升", "中心建设", "学科建设", "医共体", "公立医院改革", "健康管理"]),
    ("设备维保", ["维保", "维修", "保修", "保养"]),
    ("后勤服务", ["物业", "保洁", "安保", "食堂", "绿化", "运输", "被服", "洗涤"]),
    ("医疗设备", ["医疗设备", "医用设备", "器械", "仪器", "设备"]),
]
MED_PURCHASER = ["医院", "卫生院", "妇幼", "疾控", "血站", "保健院", "医学中心", "医科大学", "药监", "医疗器械", "卫生健康", "中药", "医药", "医保"]
MED_TITLE = ["医疗", "医用", "医院", "器械", "试剂", "耗材", "影像", "超声", "内镜", "手术", "监护", "麻醉", "病理", "口腔", "眼科", "骨科", "康复", "透析", "消毒", "输血", "血液", "疫苗", "药品", "诊断", "治疗", "病床", "护理", "献血"]

# 检验科二级细分（越靠前越具体）
LAB_SUBS = [
    ("分子诊断", ["分子诊断", "分子检测", "PCR", "核酸", "基因检测", "测序", "扩增"]),
    ("质谱检测", ["质谱"]),
    ("流式细胞", ["流式"]),
    ("治疗药物监测", ["血药浓度", "药物浓度", "TDM"]),
    ("凝血与血栓", ["凝血", "血凝", "血栓", "D-二聚体", "血小板"]),
    ("血气与电解质", ["血气", "电解质"]),
    ("POCT即时检验", ["POCT", "即时检验", "床旁"]),
    ("微生物检验", ["微生物", "培养", "药敏", "鉴定", "血培养"]),
    ("采供血与配型", ["采供血", "血站", "配型", "血液筛查"]),
    ("输血与血库", ["输血", "血库", "配血", "血浆", "血液制品"]),
    ("免疫检验", ["化学发光", "免疫", "酶免", "酶标", "洗板", "荧光", "胶体金", "肿瘤标志", "激素", "传染病", "抗原", "抗体", "特定蛋白"]),
    ("生化检验", ["生化", "干化学", "肝功", "肾功", "血糖", "血脂", "酶"]),
    ("临检", ["血常规", "尿常规", "尿沉渣", "便常规", "血沉", "血型", "体液", "血球", "尿液分析"]),
    ("质控与校准", ["质控", "校准", "标准品", "参考品"]),
    ("检验服务外送", ["外送", "委托检验", "第三方检验"]),
    ("样本前处理与流水线", ["流水线", "分拣", "采血", "样本", "冷链", "前处理", "离心机", "移液", "加样"]),
    ("实验室耗材", ["采血管", "培养皿", "吸头", "离心管", "玻片"]),
    ("实验室信息化", ["LIS", "实验室信息", "检验信息"]),
]

def classify(title):
    tags = []
    low = title.lower()
    for cat, kws in CATS:
        if any(k.lower() in low for k in kws):
            tags.append(cat)
    cat = tags[0] if tags else "其他"
    sub = ""
    if cat == "检验科":
        for s, kws in LAB_SUBS:
            if any(k.lower() in low for k in kws):
                sub = s
                break
        if not sub:
            sub = "检验试剂（通用）"
    return cat, tags, sub

def is_medical(title, purchaser):
    if any(k in purchaser for k in MED_PURCHASER):
        return True
    return any(k in title for k in MED_TITLE)

HEBEI_CITY = {
    "sjz": "石家庄", "ts": "唐山", "qhd": "秦皇岛", "hd": "邯郸", "xt": "邢台",
    "bd": "保定", "zjk": "张家口", "cd": "承德", "cz": "沧州", "lf": "廊坊",
    "hs": "衡水", "xa": "雄安",
}

def infer_city(region, url, text):
    if region == "北京":
        return "北京"
    if region == "天津":
        return "天津"
    m = re.search(r"ccgp-hebei\.gov\.cn/([a-z]{2,4})/", url)
    if m and m.group(1) in HEBEI_CITY:
        return HEBEI_CITY[m.group(1)]
    for c in HEBEI_CITY.values():
        if c in text:
            return c
    return region

# ---------------- 来源解析 ----------------
def parse_hebei(page_url):
    s = fetch(page_url, referer="http://www.ccgp-hebei.gov.cn/")
    doc = html.fromstring(s)
    out = []
    for div in doc.xpath('//div[@class="list-item"]'):
        a = div.xpath('.//a[@title]')
        if not a:
            continue
        a = a[0]
        title = clean(a.get("title"))
        if not title:
            continue
        pub = purchaser = addr = ""
        for sp in div.xpath('.//span[@data-label]'):
            label = sp.get("data-label") or ""
            val = clean(sp.text_content())
            if "发布时间" in label:
                pub = val
            elif "采购人" in label:
                purchaser = val
            elif "地域" in label:
                addr = val
        out.append({
            "title": title, "url": absolute(page_url, a.get("href")),
            "source": "河北省政府采购网", "region": "河北",
            "purchaser": purchaser, "publish_date": pub[:10],
            "address": addr, "enrich": False,
        })
    return out

def parse_tianjin(page_url):
    s = fetch(page_url, referer="http://www.ccgp-tianjin.gov.cn/")
    doc = html.fromstring(s)
    out = []
    for li in doc.xpath('//li'):
        a = li.xpath('.//a[contains(@href,"viewer.do")]')
        if not a:
            continue
        a = a[0]
        title = clean(a.get("title") or a.text_content())
        if not title:
            continue
        t = li.xpath('.//span[contains(@class,"time")]')
        pub = clean(t[0].text_content())[:10] if t else ""
        purchaser = ""
        m = re.match(r"^([^\s（(]+?(?:医院|中心|局|委|大学|学院|研究院|卫生院|保健院|疾控中心|血站))", title)
        if m:
            purchaser = m.group(1)
        out.append({
            "title": title, "url": absolute(page_url, a.get("href")),
            "source": "天津市政府采购网", "region": "天津",
            "purchaser": purchaser, "publish_date": pub, "address": "天津",
            "enrich": False,
        })
    return out

def parse_beijing(page_url):
    s = fetch(page_url, referer="http://www.ccgp-beijing.gov.cn/")
    doc = html.fromstring(s)
    out = []
    for li in doc.xpath('//li'):
        a = li.xpath('.//a')
        if not a:
            continue
        a = a[0]
        href = a.get("href") or ""
        if "/zbgg/" not in href and "/qjzbgg/" not in href:
            continue
        title = clean(a.text_content())
        if len(title) < 8:
            continue
        t = li.xpath('.//span[contains(@class,"datetime")]')
        pub = clean(t[0].text_content())[:10] if t else ""
        if not pub:
            m = re.search(r"/(\d{4})/(\d{2})/", href)
            if m:
                pub = f"{m.group(1)}-{m.group(2)}-01"
        out.append({
            "title": title, "url": absolute(page_url, href),
            "source": "北京市政府采购网", "region": "北京",
            "purchaser": "", "publish_date": pub, "address": "北京",
            "enrich": True,
        })
    return out

CN_REGION_OK = ("北京", "天津", "河北")

JUN_API = ("https://www.plap.mil.cn/freecms-glht/rest/v1/notice/selectInfoMoreChannel.do"
           "?siteId=404bb030-5be9-4070-85bd-c94b1473e8de"
           "&channel=e0172398-23dd-47be-a092-14c67a92bd4f"
           "&currPage={page}&pageSize=50&regionCode=110000")

def parse_jun(page):
    """军队采购网（北京）公开公告"""
    s = fetch(JUN_API.format(page=page), referer="https://www.plap.mil.cn/", timeout=30)
    d = json.loads(s)
    out = []
    for x in d.get("data", []):
        title = clean(x.get("title"))
        if not title:
            continue
        if any(k in title for k in ["结果公示", "中标", "成交", "合同", "废标", "终止"]):
            continue
        t = x.get("noticeTime") or ""
        out.append({
            "title": title,
            "url": "https://www.plap.mil.cn" + (x.get("pageurl") or ""),
            "source": "军队采购网", "region": "北京",
            "purchaser": "军队采购单位", "publish_date": t[:10],
            "address": "北京", "enrich": False,
        })
    return out

def parse_301(page_url):
    """解放军总医院（301）招标采购系统公开公告"""
    s = fetch(page_url, timeout=25, referer="https://zbcg.301hospital.com.cn/")
    doc = html.fromstring(s)
    out = []
    for tr in doc.xpath('//tr[@onclick]'):
        onclick = tr.get('onclick') or ''
        m = re.search(r"location='([^']+)'", onclick)
        if not m:
            continue
        url = absolute(page_url, m.group(1))
        ps = tr.xpath('.//p[@title]')
        title = clean(ps[0].get('title')) if ps else ''
        tds = tr.xpath('./td')
        if not title and len(tds) > 2:
            title = clean(tds[2].text_content())
        if not title:
            continue
        date = ''
        for td in tds:
            mm = re.search(r"20\d\d-\d\d-\d\d", td.text_content())
            if mm:
                date = mm.group(0)
                break
        notice = clean(tds[1].text_content()) if len(tds) > 1 else ''
        out.append({
            "title": title, "url": url,
            "source": "301医院招标采购网", "region": "北京",
            "purchaser": "解放军总医院", "publish_date": date,
            "address": "北京", "enrich": False, "notice_type": notice,
        })
    return out

def parse_national(page_url):
    s = fetch(page_url, referer="http://www.ccgp.gov.cn/")
    doc = html.fromstring(s)
    out = []
    for li in doc.xpath('//li'):
        a = li.xpath('.//a[@title]')
        if not a:
            continue
        a = a[0]
        title = clean(a.get("title"))
        txt = clean(li.text_content())
        m1 = re.search(r"发布时间：\s*(\d{4}-\d{2}-\d{2})", txt)
        m2 = re.search(r"地域：\s*([^\s]+)", txt)
        m3 = re.search(r"采购人：\s*([^\s]+)", txt)
        region = m2.group(1) if m2 else ""
        if region not in CN_REGION_OK:
            continue
        out.append({
            "title": title, "url": absolute(page_url, a.get("href")),
            "source": "中国政府采购网", "region": region,
            "purchaser": m3.group(1) if m3 else "",
            "publish_date": m1.group(1) if m1 else "",
            "address": region, "enrich": True,
        })
    return out

# ---------------- 详情补充 ----------------
DATE_RE = r"(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?(?:\s*\d{1,2}[:：]\d{2})?)"

def norm_date(s):
    return (s.replace("年", "-").replace("月", "-").replace("日", "")
             .replace("：", ":").strip())

def enrich(item):
    try:
        s = fetch(item["url"], timeout=20, referer="http://www.ccgp.gov.cn/")
    except Exception:
        return item
    try:
        doc = html.fromstring(s)
    except Exception:
        return item
    text = clean(doc.text_content())
    if not text:
        return item
    # 检验科：标题太笼统时，用详情页关键词细化二级分类
    if item.get("category") == "检验科" and item.get("subcat") in (None, "", "检验试剂（通用）"):
        low = text.lower()
        best, bestn = "", 0
        for s, kws in LAB_SUBS:
            n = sum(1 for k in kws if k.lower() in low)
            if n > bestn:
                best, bestn = s, n
        if best and bestn >= 2:
            item["subcat"] = best
    # 完整标题（北京列表标题被截断）
    titles = doc.xpath("//title")
    if titles:
        t = clean(titles[0].text_content())
        t = re.sub(r"[_-]中国政府采购网.*$", "", t).strip()
        if t and len(t) > len(item["title"]):
            item["title"] = t
    if not item.get("budget"):
        m = re.search(r"预算金额[^0-9￥¥]{0,12}[￥¥]?\s*([\d,\.]+)\s*(万元|元)", text)
        if m:
            item["budget"] = m.group(1).replace(",", "") + m.group(2)
    if not item.get("deadline"):
        m = re.search(r"截止时间[^0-9]{0,30}" + DATE_RE, text)
        if not m:
            m = re.search(r"开标时间[^0-9]{0,20}" + DATE_RE, text)
        if m:
            item["deadline"] = norm_date(m.group(1))
    if not item.get("purchaser"):
        m = re.search(r"(?:采购人|采购单位)(?:信息)?\s*名\s*称\s*[：:]\s*([^\s，,。；;]{2,40})", text)
        if not m:
            m = re.search(r"(?:采购人|采购单位)(?:信息)?[：:]\s*([^\s，,。；;]{2,40})", text)
        if m:
            item["purchaser"] = m.group(1)
    return item

def status_of(item):
    d = item.get("deadline")
    if d:
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", d)
        if m:
            try:
                hh = int(m.group(4)) if m.group(4) else 23
                mm = int(m.group(5)) if m.group(5) else 59
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), hh, mm, tzinfo=CN_TZ)
                return "进行中" if dt >= now_cn() else "已截止"
            except Exception:
                pass
    pd = item.get("publish_date") or ""
    try:
        dt = datetime.strptime(pd[:10], "%Y-%m-%d").replace(tzinfo=CN_TZ)
        return "进行中" if (now_cn() - dt).days <= 30 else "已截止"
    except Exception:
        return "进行中"

# ---------------- 主流程 ----------------
def build_tasks():
    tasks = []
    # 301 医院：公开公告 12 页
    for i in range(1, 13):
        u = "https://zbcg.301hospital.com.cn/Admin-Portal-proclamation-type-1.html" if i == 1 else f"https://zbcg.301hospital.com.cn/Admin-Portal-proclamation-type-1-page_num-20-p-{i}.html"
        tasks.append((parse_301, u))
    # 北京市政府采购网：市级 6 页 + 区级 4 页
    for i in range(6):
        tasks.append((parse_beijing, f"http://www.ccgp-beijing.gov.cn/xxgg/sjxxgg/zbgg/A002004001001index_{i+1}.htm"))
    for i in range(4):
        tasks.append((parse_beijing, f"http://www.ccgp-beijing.gov.cn/xxgg/qjxxgg/qjzbgg/A002004002001index_{i+1}.htm"))
    # 中国政府采购网：公开招标 + 竞争性磋商，各 4 页
    for path in ["gkzb", "jzxcs"]:
        for i in range(4):
            u = f"http://www.ccgp.gov.cn/cggg/dfgg/{path}/" if i == 0 else f"http://www.ccgp.gov.cn/cggg/dfgg/{path}/index_{i}.htm"
            tasks.append((parse_national, u))
    return tasks

def collect():
    items, errs = [], []
    for fn, u in build_tasks():
        try:
            got = fn(u)
            items.extend(got)
            print(f"[OK] {u} -> {len(got)}")
        except Exception as e:
            errs.append(f"{u}: {type(e).__name__} {e}")
            print(f"[ERR] {u}: {type(e).__name__} {e}")
        time.sleep(0.3)

    out, seen = [], set()
    for it in items:
        if not it["url"] or it["url"] in seen:
            continue
        if not is_medical(it["title"], it["purchaser"]):
            continue
        seen.add(it["url"])
        cat, tags, sub = classify(it["title"])
        it["category"], it["tags"], it["subcat"] = cat, tags, sub
        it["city"] = infer_city(it["region"], it["url"], it["purchaser"] + " " + it.get("address", "") + " " + it["title"])
        it["id"] = hashlib.sha1(it["url"].encode()).hexdigest()[:12]
        it["status"] = status_of(it)
        it["fetched_at"] = now_cn().isoformat(timespec="seconds")
        out.append(it)
    return out, errs

def merge(old, new):
    by_url = {x["url"]: x for x in old}
    added = 0
    for it in new:
        if it["url"] in by_url:
            o = by_url[it["url"]]
            for k in ("budget", "deadline", "purchaser", "category", "tags", "city"):
                if not o.get(k) and it.get(k):
                    o[k] = it[k]
            if it.get("title") and len(it["title"]) > len(o.get("title") or ""):
                o["title"] = it["title"]
            o["status"] = status_of(o)
        else:
            by_url[it["url"]] = it
            added += 1
    cutoff = now_cn() - timedelta(days=90)
    items = []
    for x in by_url.values():
        try:
            pd = datetime.strptime((x.get("publish_date") or "")[:10], "%Y-%m-%d").replace(tzinfo=CN_TZ)
            if pd < cutoff:
                continue
        except Exception:
            pass
        if not is_medical(x["title"], x.get("purchaser") or ""):
            continue
        cat, tags, sub = classify(x["title"])
        x["category"], x["tags"], x["subcat"] = cat, tags, sub
        x["city"] = infer_city(x["region"], x["url"], (x.get("purchaser") or "") + " " + (x.get("address") or "") + " " + x["title"])
        x["status"] = status_of(x)
        items.append(x)
    items.sort(key=lambda x: (x.get("publish_date") or "", x.get("fetched_at") or ""), reverse=True)
    # 跨源去重：同标题 + 同发布日期只保留一条，优先更具体的来源
    prio = {"301医院招标采购网": 0, "北京市政府采购网": 1, "中国政府采购网": 2,
            "军队采购网": 3, "天津市政府采购网": 4, "河北省政府采购网": 5}
    items.sort(key=lambda x: prio.get(x.get("source"), 9))
    dedup, seen_t = [], set()
    for x in items:
        k = re.sub(r"[\s\-—（）()【】\[\]0-9]", "", x["title"])[:40] + "|" + (x.get("publish_date") or "")
        if not k.strip("|") or k in seen_t:
            continue
        seen_t.add(k)
        dedup.append(x)
    items = dedup
    items.sort(key=lambda x: (x.get("publish_date") or "", x.get("fetched_at") or ""), reverse=True)
    return items, added

def main():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    old = []
    if os.path.exists(DATA_FILE):
        try:
            old = json.load(open(DATA_FILE, encoding="utf-8")).get("items", [])
        except Exception:
            old = []
    old_urls = {x["url"] for x in old}
    new, errs = collect()
    to_enrich = [x for x in new if x.get("enrich") and (
        x["url"] not in old_urls or not x.get("purchaser") or not x.get("deadline")
    )][:80]
    print(f"[enrich] {len(to_enrich)} items")
    for i, it in enumerate(to_enrich):
        enrich(it)
        it["status"] = status_of(it)
        if (i + 1) % 10 == 0:
            print(f"  enriched {i+1}/{len(to_enrich)}")
        time.sleep(0.25)
    items, added = merge(old, new)
    data = {
        "updated_at": now_cn().isoformat(timespec="seconds"),
        "count": len(items),
        "added": added,
        "focus_categories": FOCUS_CATEGORIES,
        "errors": errs,
        "items": items,
    }
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATA_FILE)
    print(f"[DONE] total={len(items)} new={added} errors={len(errs)}")

if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
