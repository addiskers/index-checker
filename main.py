from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import asyncio
import uuid
import os
import json
import tempfile
import subprocess
import sys
from datetime import datetime
import logging
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Google Index Checker", version="1.0.0")

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for job status
job_status = {}

class URLBatch(BaseModel):
    urls: List[str]
    batch_size: Optional[int] = 100

# Serve the frontend directly at root
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend HTML directly"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Index Checker</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }
        .container {
            max-width: 1200px; margin: 0 auto; background: white;
            border-radius: 15px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; padding: 30px; text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .main-content { padding: 40px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #333; }
        textarea {
            width: 100%; min-height: 150px; padding: 15px; border: 2px solid #ddd;
            border-radius: 8px; font-size: 14px; resize: vertical; transition: border-color 0.3s ease;
        }
        textarea:focus { outline: none; border-color: #4facfe; }
        .batch-size-group {
            display: flex; align-items: center; gap: 10px; margin-top: 15px;
        }
        .batch-size-group input {
            width: 100px; padding: 8px; border: 2px solid #ddd; border-radius: 4px; text-align: center;
        }
        .submit-btn {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; border: none; padding: 15px 40px; font-size: 16px; font-weight: 600;
            border-radius: 8px; cursor: pointer; transition: transform 0.2s ease; width: 100%; margin-top: 20px;
        }
        .submit-btn:hover { transform: translateY(-2px); }
        .submit-btn:disabled { background: #ccc; cursor: not-allowed; transform: none; }
        .status-section {
            margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px; display: none;
        }
        .status-section.show { display: block; }
        .progress-bar {
            width: 100%; height: 20px; background: #e0e0e0; border-radius: 10px; overflow: hidden;
        }
        .progress-fill {
            height: 100%; background: linear-gradient(90deg, #4facfe, #00f2fe); width: 0%; transition: width 0.3s ease;
        }
        .progress-text { text-align: center; margin-top: 10px; font-weight: 600; }
        .status-message { padding: 15px; border-radius: 8px; margin: 10px 0; font-weight: 600; }
        .status-pending { background: #fff3cd; border-left: 4px solid #ffc107; color: #856404; }
        .status-running { background: #d1ecf1; border-left: 4px solid #17a2b8; color: #0c5460; }
        .status-completed { background: #d4edda; border-left: 4px solid #28a745; color: #155724; }
        .status-error { background: #f8d7da; border-left: 4px solid #dc3545; color: #721c24; }
        .download-btn {
            background: #28a745; color: white; border: none; padding: 12px 30px; font-size: 16px;
            font-weight: 600; border-radius: 8px; cursor: pointer; text-decoration: none;
            display: inline-block; margin-top: 15px; transition: background-color 0.3s ease;
        }
        .download-btn:hover { background: #218838; }
        .example-urls {
            background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 15px;
            font-size: 14px; color: #666;
        }
        .example-urls h4 { margin-bottom: 10px; color: #333; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Google Index Checker</h1>
            <p>Check if your URLs are indexed by Google and export results to Excel</p>
        </div>
        <div class="main-content">
            <div class="form-group">
                <label for="urls-textarea">Enter URLs (one per line):</label>
                <textarea id="urls-textarea" placeholder="https://example.com/page1
https://example.com/page2
https://example.com/page3

Paste your URLs here, one per line. You can paste thousands of URLs!"></textarea>
            </div>
            <div class="example-urls">
                <h4>💡 Tips:</h4>
                • Paste one URL per line<br>
                • URLs should start with http:// or https://<br>
                • You can check thousands of URLs at once<br>
                • Processing time depends on the number of URLs
            </div>
            <div class="batch-size-group">
                <label>Batch Size:</label>
                <input type="number" id="batch-size" value="100" min="1" max="500">
                <span>URLs per batch (recommended: 50-100)</span>
            </div>
            <button class="submit-btn" id="submit-btn" onclick="startChecking()">🚀 Start Checking URLs</button>
            
            <div class="status-section" id="status-section">
                <h3>📊 Processing Status</h3>
                <div id="status-message" class="status-message"></div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill"></div>
                </div>
                <div class="progress-text" id="progress-text">0 / 0 URLs processed</div>
                <a id="download-btn" class="download-btn" style="display: none;">📥 Download Excel Report</a>
            </div>
        </div>
    </div>

    <script>
        let currentJobId = null;
        let statusInterval = null;

        async function startChecking() {
            const urlsText = document.getElementById('urls-textarea').value.trim();
            if (!urlsText) {
                alert('Please enter some URLs to check');
                return;
            }
            
            const urls = urlsText.split('\\n').map(url => url.trim()).filter(url => url && url.startsWith('http'));
            if (urls.length === 0) {
                alert('Please enter valid URLs starting with http:// or https://');
                return;
            }

            const batchSize = parseInt(document.getElementById('batch-size').value) || 100;
            
            try {
                const submitBtn = document.getElementById('submit-btn');
                submitBtn.disabled = true;
                submitBtn.textContent = '🚀 Starting...';
                
                document.getElementById('status-section').classList.add('show');
                
                const response = await fetch('/check-urls', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ urls: urls, batch_size: batchSize })
                });
                
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                
                const result = await response.json();
                currentJobId = result.job_id;
                startStatusPolling();
                
            } catch (error) {
                console.error('Error starting URL check:', error);
                showStatus('error', `Error: ${error.message}`);
                
                const submitBtn = document.getElementById('submit-btn');
                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 Start Checking URLs';
            }
        }

        function startStatusPolling() {
            if (statusInterval) clearInterval(statusInterval);
            
            statusInterval = setInterval(async () => {
                if (!currentJobId) return;
                
                try {
                    const response = await fetch(`/job-status/${currentJobId}`);
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    
                    const status = await response.json();
                    updateStatus(status);
                    
                    if (status.status === 'completed' || status.status === 'failed') {
                        clearInterval(statusInterval);
                        statusInterval = null;
                        
                        const submitBtn = document.getElementById('submit-btn');
                        submitBtn.disabled = false;
                        submitBtn.textContent = '🚀 Start Checking URLs';
                    }
                } catch (error) {
                    console.error('Error fetching status:', error);
                    clearInterval(statusInterval);
                    statusInterval = null;
                }
            }, 2000);
        }

        function updateStatus(status) {
            const progress = Math.round((status.progress / status.total) * 100);
            
            document.getElementById('progress-fill').style.width = `${progress}%`;
            document.getElementById('progress-text').textContent = 
                `${status.progress} / ${status.total} URLs processed (${progress}%)`;
            
            let statusText = '';
            switch (status.status) {
                case 'pending': statusText = '⏳ Job is pending...'; break;
                case 'running': statusText = '🚀 Processing URLs...'; break;
                case 'completed':
                    statusText = '✅ Processing completed! You can now download the results.';
                    document.getElementById('download-btn').style.display = 'inline-block';
                    document.getElementById('download-btn').href = `/download-results/${currentJobId}`;
                    break;
                case 'failed': statusText = `❌ Processing failed: ${status.error || 'Unknown error'}`; break;
            }
            
            showStatus(status.status, statusText);
        }

        function showStatus(type, message) {
            const statusMessage = document.getElementById('status-message');
            statusMessage.className = `status-message status-${type}`;
            statusMessage.textContent = message;
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api")
async def api_info():
    return {"message": "Google Index Checker API", "status": "running"}

@app.post("/check-urls")
async def check_urls(url_batch: URLBatch, background_tasks: BackgroundTasks):
    """Start checking URLs for Google indexing status"""
    job_id = str(uuid.uuid4())
    
    job_status[job_id] = {
        "status": "pending",
        "progress": 0,
        "total": len(url_batch.urls),
        "results_file": None,
        "error": None,
        "created_at": datetime.now()
    }
    
    background_tasks.add_task(process_urls_batch, job_id, url_batch.urls, url_batch.batch_size)
    
    return {"job_id": job_id, "message": "URL checking started"}

@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a job"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]

@app.get("/download-results/{job_id}")
async def download_results(job_id: str):
    """Download the results Excel file"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    if job["status"] != "completed" or not job["results_file"]:
        raise HTTPException(status_code=400, detail="Results not ready")
    
    if not os.path.exists(job["results_file"]):
        raise HTTPException(status_code=404, detail="Results file not found")
    
    return FileResponse(
        job["results_file"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"google_index_results_{job_id}.xlsx"
    )

async def run_scrapy_spider(urls: List[str]) -> List[dict]:
    """Run Scrapy spider with given URLs and return results"""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
            temp_output = temp_file.name
        
        urls_string = ','.join(urls)
        spider_path = os.path.join(os.getcwd(), 'GoogleIndexSpider')
        
        cmd = [
            sys.executable, '-m', 'scrapy', 'crawl', 'gr',
            '-a', f'urls={urls_string}',
            '-o', temp_output,
            '-s', 'LOG_LEVEL=ERROR'
        ]
        
        logger.info(f"Running Scrapy for {len(urls)} URLs...")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=spider_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Scrapy process failed: {stderr.decode()}")
            return []
        
        results = []
        if os.path.exists(temp_output):
            try:
                with open(temp_output, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        if content.startswith('['):
                            results = json.loads(content)
                        else:
                            for line in content.split('\n'):
                                if line.strip():
                                    results.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON results: {e}")
                results = []
            finally:
                if os.path.exists(temp_output):
                    os.unlink(temp_output)
        
        logger.info(f"Scrapy completed with {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Error running Scrapy: {str(e)}")
        return []

async def process_urls_batch(job_id: str, urls: List[str], batch_size: int):
    """Process URLs in batches using Scrapy"""
    try:
        job_status[job_id]["status"] = "running"
        logger.info(f"Starting job {job_id} with {len(urls)} URLs")
        
        all_results = []
        total_urls = len(urls)
        
        for i in range(0, total_urls, batch_size):
            batch_urls = urls[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_urls + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            try:
                batch_results = await run_scrapy_spider(batch_urls)
                all_results.extend(batch_results)
                job_status[job_id]["progress"] = min(i + batch_size, total_urls)
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}")
                continue
        
        excel_file = await create_excel_report(job_id, all_results)
        
        job_status[job_id].update({
            "status": "completed",
            "progress": total_urls,
            "results_file": excel_file
        })
        
        logger.info(f"Job {job_id} completed with {len(all_results)} results")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        job_status[job_id].update({
            "status": "failed",
            "error": str(e)
        })

async def create_excel_report(job_id: str, results: List[dict]) -> str:
    """Create Excel report from results"""
    try:
        if not results:
            df = pd.DataFrame(columns=['index', 'url', 'indexed', 'status', 'search_link', 'checked_at'])
        else:
            df = pd.DataFrame(results)
        
        df['checked_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if 'indexed' in df.columns:
            df['status'] = df['indexed'].apply(lambda x: 'Indexed' if x else 'Not Indexed')
        else:
            df['status'] = 'Unknown'
        
        columns_order = ['index', 'url', 'indexed', 'status', 'search_link', 'checked_at']
        df = df.reindex(columns=[col for col in columns_order if col in df.columns])
        
        os.makedirs('results', exist_ok=True)
        excel_file = f'results/google_index_results_{job_id}.xlsx'
        
        with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Index Results', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Index Results']
            
            header_format = workbook.add_format({
                'bold': True, 'text_wrap': True, 'valign': 'top',
                'fg_color': '#D7E4BC', 'border': 1
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
        
        logger.info(f"Excel report created: {excel_file}")
        return excel_file
        
    except Exception as e:
        logger.error(f"Error creating Excel report: {str(e)}")
        raise

if __name__ == "__main__":
    import uvicorn
    print(" Starting Google Index Checker API...")
    print(" API will be available on port 8877")
    print(" Frontend will be available at the root URL")
    print("-" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8877)