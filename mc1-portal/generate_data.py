#!/usr/bin/env python3
"""一次性生成 mc1-portal 前端所需的 manifest 与派生统计（基于仓库内真实文件与 JSON）。"""
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
PRE = os.path.normpath(os.path.join(ROOT, ".."))
OUT = os.path.join(ROOT, "data")
MC1 = os.path.join(PRE, "MC1", "News Articles")
RES = os.path.join(PRE, "MC1", "resumes")

if not os.path.isdir(OUT):
    os.makedirs(OUT)


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "outlet"


# --- manifest: 简历 + 新闻（新闻不写入 manifest，按媒体拆小文件）---

def name_from_resume(fn: str) -> str:
    base = fn.replace("Resume-", "").replace("Bio-", "").replace(".docx", "")
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", base)


resumes = []
for fn in sorted(os.listdir(RES)):
    if not fn.endswith(".docx"):
        continue
    resumes.append(
        {
            "file": fn,
            "name": name_from_resume(fn),
            "path": f"../MC1/resumes/{fn}",
        }
    )

news = []
if os.path.isdir(MC1):
    for dirpath, _, files in os.walk(MC1):
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), PRE)
            outlet = os.path.basename(dirpath)
            news.append(
                {
                    "outlet": outlet,
                    "file": fn,
                    "path": "../" + rel.replace(os.sep, "/"),
                }
            )
news.sort(key=lambda x: (x["outlet"], x["file"]))

outlet_counts = Counter(n["outlet"] for n in news)
outlets = [
    {"outlet": o, "count": outlet_counts[o]}
    for o in sorted(outlet_counts.keys(), key=lambda x: -outlet_counts[x])
]

# 首页只拉 ~10KB manifest；845 篇拆到 data/outlet_news/*.json，列表页只拉一个分片
OUT_NEWS = os.path.join(OUT, "outlet_news")
if not os.path.isdir(OUT_NEWS):
    os.makedirs(OUT_NEWS)

by_outlet = defaultdict(list)
for n in news:
    by_outlet[n["outlet"]].append({"file": n["file"], "path": n["path"]})

outlet_slug = {}
used_slugs = set()
for o in sorted(by_outlet.keys()):
    base = slugify(o)
    slug = base
    n = 2
    while slug in used_slugs:
        slug = "%s-%s" % (base, n)
        n += 1
    used_slugs.add(slug)
    outlet_slug[o] = slug
    rel = os.path.join("outlet_news", slug + ".json")
    with open(os.path.join(OUT, rel), "w", encoding="utf-8") as f:
        json.dump(
            {"outlet": o, "articles": by_outlet[o]},
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )

with open(os.path.join(OUT_NEWS, "_index.json"), "w", encoding="utf-8") as f:
    json.dump(outlet_slug, f, ensure_ascii=False, separators=(",", ":"))

with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(
        {
            "resumes": resumes,
            "outlets": outlets,
            "stats": {
                "resumeCount": len(resumes),
                "newsCount": len(news),
            },
        },
        f,
        ensure_ascii=False,
        separators=(",", ":"),
    )

# --- Task A: 原始新闻文本 -> 同题组 -> 首发占比/延迟/有向 lead-follow ---


def norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


DATE_RE = re.compile(r"\b(19|20)\d{2}[/-]\d{1,2}[/-]\d{1,2}\b")


def parse_date(s: str):
    if not s:
        return None
    v = s.strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m", "%Y-%m"):
        try:
            d = datetime.strptime(v, fmt)
            if fmt in ("%Y/%m", "%Y-%m"):
                return datetime(d.year, d.month, 1)
            return d
        except ValueError:
            continue
    return None


def extract_field(lines, key):
    pref = key.upper() + ":"
    for line in lines:
        s = line.strip()
        if s.upper().startswith(pref):
            return s[len(pref) :].strip()
    return ""


def extract_date(lines):
    # 1) 优先取 PUBLISHED 行内日期
    pub = extract_field(lines, "PUBLISHED")
    m = DATE_RE.search(pub)
    if m:
        return m.group(0)
    # 2) 兼容脏格式：日期在下一行或其他行
    for line in lines:
        m = DATE_RE.search(line)
        if m:
            return m.group(0)
    return ""


raw_records = []
for dirpath, _, files in os.walk(MC1):
    for fn in files:
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(dirpath, fn)
        try:
            text = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        lines = text.splitlines()
        src = extract_field(lines, "SOURCE") or os.path.basename(dirpath)
        ttl = extract_field(lines, "TITLE")
        ds = extract_date(lines)
        dt = parse_date(ds)
        if not src or not ttl or dt is None:
            continue
        raw_records.append({"source": src.strip(), "title": ttl.strip(), "date": dt})

by_title = defaultdict(list)
for r in raw_records:
    t = norm_title(r["title"])
    if t and len(t) >= 4:
        by_title[t].append({"source": r["source"], "date": r["date"]})

first_pub = Counter()
topic_count = Counter()
lag_sum = Counter()
lag_n = Counter()
lead_follow = Counter()
co_topics = 0

for _, items in by_title.items():
    if len(items) < 2:
        continue
    src_first = {}
    for it in items:
        s = it["source"]
        d = it["date"]
        if s not in src_first or d < src_first[s]:
            src_first[s] = d
    if len(src_first) < 2:
        continue

    co_topics += 1
    earliest = min(src_first.values())
    earliest_src = [s for s, d in src_first.items() if d == earliest]

    for s in src_first:
        topic_count[s] += 1
        lag_sum[s] += (src_first[s] - earliest).days
        lag_n[s] += 1
    for s in earliest_src:
        first_pub[s] += 1

    srcs = sorted(src_first.keys())
    for i in range(len(srcs)):
        for j in range(i + 1, len(srcs)):
            a, b = srcs[i], srcs[j]
            da, db = src_first[a], src_first[b]
            if da < db:
                lead_follow[(a, b)] += 1
            elif db < da:
                lead_follow[(b, a)] += 1

first_share = []
avg_lag = []
for s, tc in topic_count.items():
    if tc <= 0:
        continue
    first_share.append(
        {
            "source": s,
            "share": first_pub[s] / tc,
            "firstCount": first_pub[s],
            "topicCount": tc,
        }
    )
    avg_lag.append(
        {
            "source": s,
            "avgLag": (lag_sum[s] / lag_n[s]) if lag_n[s] else 0.0,
            "topicCount": tc,
        }
    )

first_share.sort(key=lambda x: (-x["share"], -x["firstCount"], x["source"]))
avg_lag.sort(key=lambda x: (-x["avgLag"], x["source"]))

node_set = set()
for (a, b), _ in lead_follow.items():
    node_set.add(a)
    node_set.add(b)
for s in topic_count:
    node_set.add(s)

nodes_a = []
for s in sorted(node_set):
    tc = topic_count.get(s, 0)
    fc = first_pub.get(s, 0)
    nodes_a.append(
        {
            "id": s,
            "firstCount": fc,
            "topicCount": tc,
            "firstShare": (fc / tc) if tc else 0.0,
            "avgLag": (lag_sum[s] / lag_n[s]) if lag_n[s] else 0.0,
        }
    )

links_a = []
for (a, b), w in lead_follow.items():
    links_a.append({"source": a, "target": b, "weight": w})
links_a.sort(key=lambda x: -x["weight"])

with open(os.path.join(OUT, "task_a.json"), "w", encoding="utf-8") as f:
    json.dump(
        {
            "firstPublishShare": first_share,
            "avgLagDays": avg_lag,
            "directedLeadFollow": {"nodes": nodes_a, "links": links_a},
            "stats": {
                "rawArticlesUsable": len(raw_records),
                "coTopicGroups": co_topics,
            },
            "methodNote": "Task A 基于 MC1/News Articles 原始 .txt 自动提取 SOURCE/TITLE/PUBLISHED；以归一化标题形成同题组，在组内按最早日期统计首发占比、平均跟发延迟及 A→B（A 早于 B）方向边。该方法提供传播线索，不等同显式转载证明。",
        },
        f,
        ensure_ascii=False,
        separators=(",", ":"),
    )

# --- Task B: heatmap 来自 entity_mentions_fixed; 词云来自新闻全文（去元数据行）---
with open(os.path.join(PRE, "entity_mentions_fixed.json"), encoding="utf-8") as f:
    em = json.load(f)

# order outlets by total
rows = []
for outlet, ent in em.items():
    tot = sum(ent.values()) or 1
    rows.append(
        {
            "outlet": outlet,
            "POK": ent.get("POK", 0) / tot,
            "GAStech": ent.get("GAStech", 0) / tot,
            "Government": ent.get("Government", 0) / tot,
            "People": ent.get("People", 0) / tot,
        }
    )
rows.sort(key=lambda x: -sum([x["POK"], x["GAStech"], x["Government"], x["People"]]))

stop = set(
    "the a an and or for of in to is was are on at be by as with from that this it we he she they them his her its their but not if which our has have had can will would could been than then so such who what when which were into out about up over all any each some more most other source title published location center paper news today"
    .split()
)

wc = Counter()
if os.path.isdir(MC1):
    for dirpath, _, files in os.walk(MC1):
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            lines = text.splitlines()
            body = []
            loc_i = -1
            for i, line in enumerate(lines):
                if line.strip().upper().startswith("LOCATION:"):
                    loc_i = i
                    break
            if loc_i >= 0:
                for line in lines[loc_i + 1 :]:
                    t = line.strip()
                    if not t:
                        continue
                    u = t.upper()
                    if u.startswith("SOURCE:") or u.startswith("TITLE:"):
                        break
                    body.append(line)
            if not body:
                body = lines[10:]
            blob = " ".join(body)
            for w in re.findall(r"[A-Za-z]+", blob.lower()):
                if len(w) < 4 or w in stop:
                    continue
                wc[w] += 1

wordcloud = [{"text": t, "size": c} for t, c in wc.most_common(60)]

with open(os.path.join(OUT, "task_b.json"), "w", encoding="utf-8") as f:
    json.dump(
        {
            "normalizedHeatmap": rows,
            "wordcloud": wordcloud,
        },
        f,
        ensure_ascii=False,
        separators=(",", ":"),
    )

# --- Task C: relationship_data + 邮件网（全量 54 点）---
with open(os.path.join(PRE, "relationship_data.json"), encoding="utf-8") as f:
    rel = json.load(f)

with open(os.path.join(PRE, "email_network.json"), encoding="utf-8") as f:
    eml = json.load(f)

email_nodes = set()
for e in eml:
    email_nodes.add(e["source"])
    email_nodes.add(e["target"])
# 可视化：取权重前 300 条边，避免 1266 条边完全糊在一起；全量见 email_network.json
eml_sorted = sorted(eml, key=lambda x: -x["weight"])
email_display = eml_sorted[:300]

with open(os.path.join(OUT, "task_c.json"), "w", encoding="utf-8") as f:
    json.dump(
        {
            "analystGraph": rel,
            "emailNetwork": {
                "nodes": sorted(email_nodes),
                "links": email_display,
                "linksTotal": len(eml),
                "displayNote": "为可读性仅绘制权重前 300 条边，节点仍覆盖全量 54 人。原始边表见 ../email_network.json。",
            },
        },
        f,
        ensure_ascii=False,
        separators=(",", ":"),
    )

# --- 邮件: 与简历人物名对齐，按 @ 前本地名匹配 (first.last ∈ local-part) ---


def person_match_needle(display_name: str):
    parts = re.findall(r"[A-Za-z][a-zA-Z\-\']*|Jr\.?", display_name)
    parts = [p.rstrip(".") for p in parts]
    parts = [p for p in parts if p.lower() not in ("jr", "sr", "ii", "iii", "iv", "v")]
    if len(parts) < 2:
        return None
    return (parts[0] + "." + parts[1]).lower()


EMAIL_CSV = os.path.join(PRE, "MC1", "email headers.csv")
emails_by_person: dict = {}
email_rows: list = []
if os.path.isfile(EMAIL_CSV):
    with open(EMAIL_CSV, encoding="utf-8", errors="replace", newline="") as ef:
        for row in csv.DictReader(ef):
            email_rows.append(
                {
                    "from": (row.get("From") or "").strip(),
                    "to": (row.get("To") or "").strip(),
                    "date": (row.get("Date") or "").strip(),
                    "subject": (row.get("Subject") or "").strip(),
                }
            )
for d in resumes:
    nm = d["name"]
    needle = person_match_needle(nm)
    acc = []
    if needle:
        for idx, er in enumerate(email_rows):
            block = (er["from"] + " " + er["to"] + " " + er["subject"]).lower()
            if needle in block:
                acc.append(idx)
    emails_by_person[nm] = acc

with open(os.path.join(OUT, "emails_by_person.json"), "w", encoding="utf-8") as f:
    json.dump(
        {
            "totalHeaderRows": len(email_rows),
            "rows": email_rows,
            "indexByName": emails_by_person,
        },
        f,
        ensure_ascii=False,
        separators=(",", ":"),
    )

print("Wrote", OUT, "manifest + task_*.json + emails_by_person.json")
