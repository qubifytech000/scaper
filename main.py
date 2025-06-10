import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from urllib.parse import urljoin, urlparse
from collections import deque
from io import BytesIO, StringIO
import csv

app = FastAPI()

# Ensure URL starts with https
def normalize_url(url):
    if not url.startswith("http://") and not url.startswith("https://"):
        return "https://" + url
    return url

# Check if a URL is internal
def is_internal_link(link, base_netloc):
    parsed = urlparse(link)
    return parsed.netloc == '' or parsed.netloc == base_netloc

# Crawl and extract filtered content
def crawl_and_scrape(url, keywords, max_pages=30):
    visited = set()
    queue = deque([url])
    results = []
    headers = {"User-Agent": "Mozilla/5.0"}
    base_netloc = urlparse(url).netloc
    keyword_list = [kw.strip().lower() for kw in keywords.split(",") if kw.strip()]

    while queue and len(visited) < max_pages:
        current_url = queue.popleft()
        if current_url in visited:
            continue

        visited.add(current_url)
        try:
            resp = requests.get(current_url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.content, "html.parser")
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()

            text = soup.get_text()
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            filtered = [line for line in lines if any(kw in line.lower() for kw in keyword_list)]

            if filtered:
                results.append({
                    "url": current_url,
                    "content": "\n".join(filtered)
                })

            for a in soup.find_all("a", href=True):
                link = urljoin(current_url, a["href"])
                if is_internal_link(link, base_netloc) and link not in visited:
                    queue.append(link)

        except Exception:
            continue

    return results

@app.get("/", response_class=HTMLResponse)
def form(request: Request):
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Domain Scraper</title>
        <style>
            body { font-family: Arial; background: #f4f4f8; padding: 2rem; }
            .container { max-width: 600px; background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); margin: auto; }
            input, button { width: 100%; padding: 12px; margin: 10px 0; border-radius: 6px; border: 1px solid #ccc; }
            button { background: #007bff; color: white; cursor: pointer; }
            button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
    <div class="container">
        <h1>🔍 Domain Scraper</h1>
        <form method="post" action="/scrape">
            <input type="text" name="url" placeholder="Enter domain URL (e.g., https://example.com)" required>
            <input type="text" name="keywords" placeholder="Comma-separated keywords (optional)">
            <button type="submit">Start Scraping</button>
        </form>
    </div>
    </body>
    </html>
    """)

@app.post("/scrape", response_class=HTMLResponse)
def scrape(request: Request, url: str = Form(...), keywords: str = Form(...)):
    try:
        url = normalize_url(url)
        result_list = crawl_and_scrape(url, keywords)
        if not result_list:
            return HTMLResponse("<h2>No matching keywords found across domain.</h2>")

        preview_html = ""
        for item in result_list:
            preview_html += f"<h4>🔗 {item['url']}</h4><pre>{item['content']}</pre><hr>"

        # Prepare buttons for download
        buttons = f"""
            <form method='post' action='/export/txt'>
                <input type='hidden' name='data' value="{urlparse(url).netloc}">
                <button type='submit'>Download as TXT</button>
            </form>
            <form method='post' action='/export/csv'>
                <input type='hidden' name='data' value="{urlparse(url).netloc}">
                <button type='submit'>Download as CSV</button>
            </form>
        """

        # Save result in app memory (simulate session or persist for export)
        request.state.scraped_result = result_list  # (you can use session-based approach for multi-user)

        # Store it in global temp variable for export routes
        global scraped_cache
        scraped_cache = result_list

        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Domain Scrape Result</title>
            <style>
                body {{ font-family: Arial; background: #eef1f7; padding: 2rem; }}
                .preview-container {{ max-width: 900px; background: white; padding: 2rem; margin: auto; border-radius: 10px; box-shadow: 0 6px 16px rgba(0,0,0,0.1); }}
                pre {{ white-space: pre-wrap; background: #f8f8f8; padding: 1rem; border-radius: 6px; max-height: 400px; overflow-y: scroll; }}
                h4 {{ margin-top: 2rem; color: #333; }}
            </style>
        </head>
        <body>
            <div class="preview-container">
                <h2>📄 Scrape Results</h2>
                {preview_html}
                {buttons}
            </div>
        </body>
        </html>
        """)

    except Exception as e:
        return HTMLResponse(content=f"<h1 style='color:red'>Error:</h1><p>{str(e)}</p>")

# Temp global cache (for simplicity)
scraped_cache = []

@app.post("/export/txt")
def export_txt():
    output = "\n\n".join([f"Page: {item['url']}\n{item['content']}" for item in scraped_cache])
    return StreamingResponse(BytesIO(output.encode()), media_type="text/plain", headers={
        "Content-Disposition": "attachment; filename=scrape_output.txt"
    })

@app.post("/export/csv")
def export_csv():
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["URL", "Matched Content"])
    for item in scraped_cache:
        writer.writerow([item["url"], item["content"]])
    buffer.seek(0)
    return StreamingResponse(BytesIO(buffer.getvalue().encode()), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=scrape_output.csv"
    })
