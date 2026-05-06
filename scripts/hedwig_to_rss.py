import requests
from bs4 import BeautifulSoup
import datetime
import os
import re
import urllib3
from xml.etree import ElementTree

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://orangeclk.hedwig.pub"
HEDWIG_URL = f"{BASE_URL}/"
RSS_FILE_PATH = "feeds/orangeclk.xml"

def fetch_html(url, verify_ssl=True):
    """获取网页内容，处理 SSL 错误"""
    try:
        if not verify_ssl:
            response = requests.get(url, timeout=30, verify=False)
        else:
            response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.SSLError:
        return fetch_html(url, verify_ssl=False)
    except Exception as e:
        print(f"获取页面失败 {url}: {e}")
        return None

def extract_articles_from_list(html_content):
    """从 Hedwig 列表页面提取文章链接、标题和日期"""
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = []
    # 针对 orangeclk.hedwig.pub 的 HTML 结构调整选择器
    # 通常每篇文章在包含 class="Issue__IssueSummaryWrap" 的 div 中
    for article_div in soup.find_all('div', class_=re.compile(r'Issue__IssueSummaryWrap')):
        link_tag = article_div.find('a', href=True)
        if not link_tag:
            continue
        link = link_tag['href']
        if not link.startswith('/i/'):
            continue
        full_link = BASE_URL + link
        # 标题
        title_tag = article_div.find('h2')
        title = title_tag.get_text(strip=True) if title_tag else "无标题"
        # 日期（格式如 2026/05/05 10:21）
        date_tag = article_div.find('span', class_=re.compile(r'Issue__IssueMeta'))
        date_str = date_tag.get_text(strip=True) if date_tag else None
        pub_date = parse_date(date_str) if date_str else datetime.datetime.now()
        articles.append({
            'link': full_link,
            'title': title,
            'pubDate': pub_date
        })
    return articles

def parse_date(date_str):
    """尝试解析各种日期格式"""
    # 示例: "2026/05/05 10:21"
    for fmt in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except:
            continue
    return datetime.datetime.now()

def extract_article_content(url):
    """获取单篇文章的正文（纯文本，无图片）"""
    html_content = fetch_html(url)
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    # 尝试多种正文容器选择器
    content_div = (soup.find('div', class_=re.compile(r'Issue__Content')) or
                   soup.find('article') or
                   soup.find('div', class_=re.compile(r'content')))
    if content_div:
        # 移除脚本和样式
        for tag in content_div(["script", "style"]):
            tag.decompose()
        # 移除图片
        for img in content_div.find_all('img'):
            img.decompose()
        text = content_div.get_text(separator='\n', strip=True)
        # 压缩过长的空白行
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text
    return ""

def load_existing_links(rss_path):
    """从现有 RSS 文件中提取已存在的文章链接"""
    links = set()
    if not os.path.exists(rss_path):
        return links
    try:
        tree = ElementTree.parse(rss_path)
        root = tree.getroot()
        for item in root.findall('.//item'):
            link_elem = item.find('link')
            if link_elem is not None and link_elem.text:
                links.add(link_elem.text.strip())
    except Exception as e:
        print(f"加载现有 RSS 失败: {e}")
    return links

def add_articles_to_rss(new_articles, rss_path):
    """将新文章添加到 RSS 文件（不覆盖已有）"""
    existing_links = load_existing_links(rss_path)
    if not os.path.exists(rss_path):
        # 创建全新的 RSS 文件
        from xml.dom import minidom
        root = ElementTree.Element("rss", version="2.0")
        channel = ElementTree.SubElement(root, "channel")
        title = ElementTree.SubElement(channel, "title")
        title.text = "半瓶 (OrangeCLK)"
        link = ElementTree.SubElement(channel, "link")
        link.text = "https://orangeclk.hedwig.pub"
        desc = ElementTree.SubElement(channel, "description")
        desc.text = "OrangeCLK的博客，包含从 Hedwig 发布的文章"
        last_build = ElementTree.SubElement(channel, "lastBuildDate")
        last_build.text = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        tree = ElementTree.ElementTree(root)
    else:
        tree = ElementTree.parse(rss_path)
        root = tree.getroot()
        channel = root.find('channel')
        # 更新 lastBuildDate
        last_build = channel.find('lastBuildDate')
        if last_build is None:
            last_build = ElementTree.SubElement(channel, "lastBuildDate")
        last_build.text = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

    channel = root.find('channel')
    added = 0
    for article in new_articles:
        if article['link'] in existing_links:
            continue
        print(f"正在抓取: {article['title']} ...")
        content = extract_article_content(article['link'])
        if not content:
            content = "内容加载失败，请访问原文链接。"
        item = ElementTree.SubElement(channel, 'item')
        title_elem = ElementTree.SubElement(item, 'title')
        title_elem.text = article['title']
        link_elem = ElementTree.SubElement(item, 'link')
        link_elem.text = article['link']
        desc_elem = ElementTree.SubElement(item, 'description')
        desc_elem.text = content
        guid_elem = ElementTree.SubElement(item, 'guid')
        guid_elem.text = article['link']
        pubdate_elem = ElementTree.SubElement(item, 'pubDate')
        pubdate_elem.text = article['pubDate'].strftime("%a, %d %b %Y %H:%M:%S GMT")
        added += 1
        print(f"  ✅ 已添加: {article['title']}")

    if added > 0:
        # 写入文件
        tree.write(rss_path, encoding='utf-8', xml_declaration=True)
        print(f"成功添加 {added} 篇新文章到 {rss_path}")
    else:
        print("没有发现新文章。")

def main():
    print("正在获取 Hedwig 列表页...")
    list_html = fetch_html(HEDWIG_URL)
    if not list_html:
        print("无法获取 Hedwig 页面，程序退出。")
        return
    articles = extract_articles_from_list(list_html)
    print(f"从 Hedwig 列表中找到 {len(articles)} 篇文章。")
    if not articles:
        return
    # 按发布日期排序（可选）
    articles.sort(key=lambda x: x['pubDate'], reverse=False)
    add_articles_to_rss(articles, RSS_FILE_PATH)

if __name__ == "__main__":
    main()
