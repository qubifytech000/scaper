import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
import os

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def form():
    return """
    <html>
        <head>
            <title>Scraper Tool</title>
        </head>
        <body>
            <h1>Enter URL to Scrape</h1>
            <form action="/scrape" method="post">
                <input type="text" name="url" style="width: 400px" placeholder="https://example.com" required>
                <button type="submit">Scrape</button>
            </form>
        </body>
    </html>
    """

@app.post("/scrape")
def scrape(url: str = Form(...)):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Decapping visible text (excluding script/style)
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        text = soup.get_text()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        decapped_data = "\n".join(lines)

        output_file = "scraped_data.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(decapped_data)

        return FileResponse(output_file, media_type='text/plain', filename=output_file)

    except Exception as e:
        return {"error": str(e)}
