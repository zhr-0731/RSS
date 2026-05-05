import feedparser
import PyRSS2Gen
import datetime
import os
import re
import html

FEEDS = [
    {
        "url": "https://www.orangeclk.com/atom.xml",
        "output": "feeds/orangeclk.xml"
    },
    {
        "url": "https://www.ruanyifeng.com/blog/atom.xml",
        "output": "feeds/ruanyifeng.xml"
    }
]

def parse_date(date_struct):
    """将 feedparser 的日期结构转换为 datetime 对象"""
    if date_struct and hasattr(date_struct, '__len__') and len(date_struct) >= 6:
        return datetime.datetime(*date_struct[:6])
    return datetime.datetime.now()

def clean_html_to_text(html_content):
    """
    将 HTML 内容转换为纯文本，移除图片和所有标签，保留换行。
    """
    if not html_content:
        return ""

    # 1. 移除 <img ...> 标签
    html_content = re.sub(r'<img[^>]*>', '', html_content, flags=re.IGNORECASE)

    # 2. 将块级标签替换为换行符
    html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?p[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?div[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?h[1-6][^>]*>', '\n', html_content, flags=re.IGNORECASE)

    # 3. 移除所有其他 HTML 标签
    html_content = re.sub(r'<[^>]+>', '', html_content)

    # 4. 解码 HTML 实体
    html_content = html.unescape(html_content)

    # 5. 压缩连续的空白行
    html_content = re.sub(r'\n\s*\n', '\n\n', html_content)

    # 6. 去掉首尾空白
    return html_content.strip()

def get_full_content(entry):
    """
    获取完整正文（合并多 CDATA 块），并转换为纯文本。
    """
    full_html = ""
    if "content" in entry and entry.content:
        for part in entry.content:
            if part.get("value"):
                full_html += part.value
    if not full_html.strip():
        full_html = entry.get("summary", "")

    return clean_html_to_text(full_html)

def convert_atom_to_rss(atom_url, output_path):
    """将 Atom 源转换为 RSS 2.0"""
    print(f"正在转换: {atom_url}")

    feed = feedparser.parse(atom_url)

    if feed.bozo:
        print(f"⚠️ 解析 {atom_url} 时出错: {feed.bozo_exception}")

    title = feed.feed.get("title", "No Title")
    link = feed.feed.get("link", "")
    description = feed.feed.get("subtitle") or feed.feed.get("description") or ""

    rss_items = []
    for entry in feed.entries:
        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_date = parse_date(entry.published_parsed)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            pub_date = parse_date(entry.updated_parsed)
        else:
            pub_date = datetime.datetime.now()

        full_content = get_full_content(entry)

        rss_item = PyRSS2Gen.RSSItem(
            title=entry.get("title", "No Title"),
            link=entry.get("link", ""),
            description=full_content,
            guid=PyRSS2Gen.Guid(entry.get("id", entry.get("link", ""))),
            pubDate=pub_date
        )
        rss_items.append(rss_item)

    rss_channel = PyRSS2Gen.RSS2(
        title=title,
        link=link,
        description=description,
        lastBuildDate=datetime.datetime.now(),
        items=rss_items
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rss_channel.to_xml(encoding="utf-8"))

    print(f"✅ 已生成: {output_path} ({len(rss_items)} 篇文章)")

def main():
    """主函数"""
    for feed_config in FEEDS:
        try:
            convert_atom_to_rss(feed_config["url"], feed_config["output"])
        except Exception as e:
            print(f"❌ 转换 {feed_config['url']} 失败: {e}")

if __name__ == "__main__":
    main()
