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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Google Index Checker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_status = {}

class URLBatch(BaseModel):
    urls: List[str]
    batch_size: Optional[int] = 100

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Index Checker Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #2563eb;
            --primary-dark: #1d4ed8;
            --secondary-color: #64748b;
            --success-color: #059669;
            --warning-color: #d97706;
            --error-color: #dc2626;
            --background: #f8fafc;
            --card-background: #ffffff;
            --border-color: #e2e8f0;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--background);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        .header {
            text-align: center;
            margin-bottom: 3rem;
        }

        .header h1 {
            font-size: 3rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 0.5rem;
            letter-spacing: -0.025em;
        }

        .header p {
            font-size: 1.25rem;
            color: var(--text-secondary);
            font-weight: 400;
        }

        .main-card {
            background: var(--card-background);
            border-radius: 16px;
            box-shadow: var(--shadow-lg);
            overflow: hidden;
            border: 1px solid var(--border-color);
        }

        .card-header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
            padding: 2rem;
            color: white;
        }

        .card-header h2 {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .card-header p {
            opacity: 0.9;
            font-weight: 400;
        }

        .card-body {
            padding: 2rem;
        }

        .form-group {
            margin-bottom: 2rem;
        }

        .form-label {
            display: block;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.75rem;
            font-size: 0.95rem;
        }

        .form-textarea {
            width: 100%;
            min-height: 200px;
            padding: 1rem;
            border: 2px solid var(--border-color);
            border-radius: 12px;
            font-size: 0.95rem;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            resize: vertical;
            transition: all 0.2s ease;
            background: #fafbfc;
        }

        .form-textarea:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
            background: white;
        }

        .form-textarea::placeholder {
            color: var(--text-secondary);
            font-family: 'Inter', sans-serif;
        }

        .settings-grid {
            display: grid;
            grid-template-columns: 1fr 200px;
            gap: 1.5rem;
            align-items: end;
            margin-top: 1.5rem;
        }

        .batch-input {
            padding: 0.75rem 1rem;
            border: 2px solid var(--border-color);
            border-radius: 8px;
            font-size: 0.95rem;
            text-align: center;
            transition: all 0.2s ease;
            background: white;
        }

        .batch-input:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }

        .submit-btn {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
            color: white;
            border: none;
            padding: 1rem 2rem;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            box-shadow: var(--shadow);
        }

        .submit-btn:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 15px 30px -5px rgba(37, 99, 235, 0.3);
        }

        .submit-btn:active {
            transform: translateY(0);
        }

        .submit-btn:disabled {
            background: var(--text-secondary);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .info-card {
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 1.5rem;
        }

        .info-card h4 {
            color: var(--primary-color);
            font-weight: 600;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .info-list {
            list-style: none;
            space-y: 0.5rem;
        }

        .info-list li {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }

        .info-list li i {
            color: var(--success-color);
            width: 16px;
        }

        .status-section {
            margin-top: 2rem;
            background: var(--card-background);
            border-radius: 16px;
            box-shadow: var(--shadow);
            border: 1px solid var(--border-color);
            overflow: hidden;
            display: none;
        }

        .status-section.show {
            display: block;
        }

        .status-header {
            background: #f8fafc;
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--border-color);
        }

        .status-header h3 {
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .status-body {
            padding: 2rem;
        }

        .status-message {
            padding: 1rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .status-pending {
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fcd34d;
        }

        .status-running {
            background: #dbeafe;
            color: #1e40af;
            border: 1px solid #93c5fd;
        }

        .status-completed {
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #6ee7b7;
        }

        .status-error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }

        .progress-container {
            margin-bottom: 1.5rem;
        }

        .progress-bar {
            width: 100%;
            height: 12px;
            background: #e5e7eb;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--primary-dark));
            width: 0%;
            transition: width 0.3s ease;
            border-radius: 6px;
        }

        .progress-text {
            text-align: center;
            margin-top: 0.75rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .download-btn {
            background: var(--success-color);
            color: white;
            border: none;
            padding: 0.875rem 1.5rem;
            font-size: 0.95rem;
            font-weight: 600;
            border-radius: 10px;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s ease;
            box-shadow: var(--shadow);
        }

        .download-btn:hover {
            background: #047857;
            transform: translateY(-1px);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .stat-card {
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }

        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-color);
        }

        .stat-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }

        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }

            .header h1 {
                font-size: 2rem;
            }

            .settings-grid {
                grid-template-columns: 1fr;
            }

            .card-body {
                padding: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-search"></i> Index Analyzer Pro</h1>
            <p>Professional Google indexing analysis with comprehensive reporting</p>
        </div>

        <div class="main-card">
            <div class="card-header">
                <h2><i class="fas fa-link"></i> URL Analysis</h2>
                <p>Submit your URLs for comprehensive Google indexing verification</p>
            </div>
            
            <div class="card-body">
                <div class="form-group">
                    <label for="urls-textarea" class="form-label">
                        <i class="fas fa-list"></i> URL List
                    </label>
                    <textarea 
                        id="urls-textarea" 
                        class="form-textarea"
                        placeholder="https://example.com/page1
https://example.com/page2
https://example.com/page3

Enter your URLs here, one per line
Supports bulk processing of thousands of URLs"></textarea>
                </div>

                <div class="settings-grid">
                    <div class="info-card">
                        <h4><i class="fas fa-info-circle"></i> Processing Guidelines</h4>
                        <ul class="info-list">
                            <li><i class="fas fa-check"></i> One URL per line</li>
                            <li><i class="fas fa-check"></i> Must include http:// or https://</li>
                            <li><i class="fas fa-check"></i> Supports bulk processing</li>
                            <li><i class="fas fa-check"></i> Results exported to Excel</li>
                        </ul>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">
                            <i class="fas fa-cogs"></i> Batch Size
                        </label>
                        <input type="number" id="batch-size" class="batch-input" value="100" min="1" max="500">
                    </div>
                </div>

                <button class="submit-btn" id="submit-btn" onclick="startChecking()">
                    <i class="fas fa-rocket"></i>
                    <span>Start Analysis</span>
                </button>
            </div>
        </div>
        
        <div class="status-section" id="status-section">
            <div class="status-header">
                <h3><i class="fas fa-chart-line"></i> Analysis Progress</h3>
            </div>
            <div class="status-body">
                <div id="status-message" class="status-message"></div>
                
                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>
                    <div class="progress-text" id="progress-text">0 / 0 URLs processed</div>
                </div>

                <div class="stats-grid" id="stats-grid" style="display: none;">
                    <div class="stat-card">
                        <div class="stat-value" id="total-urls">0</div>
                        <div class="stat-label">Total URLs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="processed-urls">0</div>
                        <div class="stat-label">Processed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="completion-rate">0%</div>
                        <div class="stat-label">Completion</div>
                    </div>
                </div>
                
                <a id="download-btn" class="download-btn" style="display: none;">
                    <i class="fas fa-download"></i>
                    Download Excel Report
                </a>
            </div>
        </div>
    </div>

    <script>
        let currentJobId = null;
        let statusInterval = null;

        async function startChecking() {
            const urlsText = document.getElementById('urls-textarea').value.trim();
            if (!urlsText) {
                alert('Please enter URLs to analyze');
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
                const submitIcon = submitBtn.querySelector('i');
                const submitText = submitBtn.querySelector('span');
                
                submitBtn.disabled = true;
                submitIcon.className = 'fas fa-spinner fa-spin';
                submitText.textContent = 'Initializing...';
                
                document.getElementById('status-section').classList.add('show');
                document.getElementById('stats-grid').style.display = 'grid';
                document.getElementById('total-urls').textContent = urls.length;
                
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
                console.error('Error starting analysis:', error);
                showStatus('error', `<i class="fas fa-exclamation-triangle"></i> Error: ${error.message}`);
                resetSubmitButton();
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
                        resetSubmitButton();
                    }
                } catch (error) {
                    console.error('Error fetching status:', error);
                    clearInterval(statusInterval);
                    statusInterval = null;
                    resetSubmitButton();
                }
            }, 2000);
        }

        function updateStatus(status) {
            const progress = Math.round((status.progress / status.total) * 100);
            
            document.getElementById('progress-fill').style.width = `${progress}%`;
            document.getElementById('progress-text').textContent = 
                `${status.progress} / ${status.total} URLs processed`;
            
            document.getElementById('processed-urls').textContent = status.progress;
            document.getElementById('completion-rate').textContent = `${progress}%`;
            
            let statusText = '';
            let statusIcon = '';
            
            switch (status.status) {
                case 'pending':
                    statusText = 'Analysis queued and waiting to start';
                    statusIcon = '<i class="fas fa-clock"></i>';
                    break;
                case 'running':
                    statusText = 'Processing URLs and checking index status';
                    statusIcon = '<i class="fas fa-cog fa-spin"></i>';
                    break;
                case 'completed':
                    statusText = 'Analysis completed successfully! Download your report below.';
                    statusIcon = '<i class="fas fa-check-circle"></i>';
                    document.getElementById('download-btn').style.display = 'inline-flex';
                    document.getElementById('download-btn').href = `/download-results/${currentJobId}`;
                    break;
                case 'failed':
                    statusText = `Analysis failed: ${status.error || 'Unknown error occurred'}`;
                    statusIcon = '<i class="fas fa-times-circle"></i>';
                    break;
            }
            
            showStatus(status.status, `${statusIcon} ${statusText}`);
        }

        function showStatus(type, message) {
            const statusMessage = document.getElementById('status-message');
            statusMessage.className = `status-message status-${type}`;
            statusMessage.innerHTML = message;
        }

        function resetSubmitButton() {
            const submitBtn = document.getElementById('submit-btn');
            const submitIcon = submitBtn.querySelector('i');
            const submitText = submitBtn.querySelector('span');
            
            submitBtn.disabled = false;
            submitIcon.className = 'fas fa-rocket';
            submitText.textContent = 'Start Analysis';
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
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]

@app.get("/download-results/{job_id}")
async def download_results(job_id: str):
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
    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
            temp_output = temp_file.name
        
        urls_string = ','.join(urls)
        
        current_dir = os.getcwd()
        possible_paths = [
            os.path.join(current_dir, 'GoogleIndexSpider'),
            os.path.join(current_dir, 'google-index-checker', 'GoogleIndexSpider'),
            os.path.join(os.path.dirname(current_dir), 'GoogleIndexSpider'),
            '/app/GoogleIndexSpider',
            './GoogleIndexSpider',
            'GoogleIndexSpider',
            os.path.join(os.path.dirname(__file__), 'GoogleIndexSpider'),
        ]
        
        spider_path = None
        for path in possible_paths:
            logger.info(f"Checking path: {path}")
            if os.path.exists(path):
                scrapy_cfg = os.path.join(path, 'scrapy.cfg')
                logger.info(f"Path exists, checking for scrapy.cfg: {scrapy_cfg}")
                if os.path.exists(scrapy_cfg):
                    spider_path = path
                    logger.info(f"Found valid spider path: {spider_path}")
                    break
                else:
                    logger.info(f"scrapy.cfg not found in {path}")
            else:
                logger.info(f"Path does not exist: {path}")
        
        if not spider_path:
            logger.error(f"Could not find GoogleIndexSpider directory.")
            logger.error(f"Current directory: {current_dir}")
            logger.error(f"__file__ location: {os.path.dirname(__file__) if '__file__' in globals() else 'Not available'}")
            logger.error(f"Checked paths: {possible_paths}")
            
            try:
                contents = os.listdir(current_dir)
                logger.error(f"Current directory contents: {contents}")
            except Exception as e:
                logger.error(f"Could not list directory contents: {e}")
            
            if 'google-index-checker' in current_dir:
                project_spider_path = os.path.join(current_dir, 'GoogleIndexSpider')
            else:
                project_spider_path = os.path.join(current_dir, 'google-index-checker', 'GoogleIndexSpider')
            
            logger.error(f"Expected spider path: {project_spider_path}")
            return []
        
        cmd = [
            sys.executable, '-m', 'scrapy', 'crawl', 'gr',
            '-a', f'urls={urls_string}',
            '-o', temp_output,
            '-s', 'LOG_LEVEL=ERROR'
        ]
        
        logger.info(f"Running Scrapy for {len(urls)} URLs...")
        logger.info(f"Using spider path: {spider_path}")
        logger.info(f"Command: {' '.join(cmd)}")
        logger.info(f"Output file: {temp_output}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=spider_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        logger.info(f"Scrapy return code: {process.returncode}")
        if stdout:
            logger.info(f"Scrapy stdout: {stdout.decode()[:500]}...")
        if stderr:
            logger.info(f"Scrapy stderr: {stderr.decode()[:500]}...")
        
        if process.returncode != 0:
            logger.error(f"Scrapy process failed with return code {process.returncode}")
            logger.error(f"Full stderr: {stderr.decode()}")
            return []
        
        results = []
        if os.path.exists(temp_output):
            try:
                with open(temp_output, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    logger.info(f"Raw file content length: {len(content)}")
                    if content:
                        logger.info(f"Content preview: {content[:200]}...")
                    
                    if content:
                        if content.startswith('['):
                            results = json.loads(content)
                            logger.info(f"Parsed as JSON array: {len(results)} items")
                        else:
                            lines = [line.strip() for line in content.split('\n') if line.strip()]
                            logger.info(f"Processing {len(lines)} JSON lines")
                            
                            for line_num, line in enumerate(lines):
                                try:
                                    item = json.loads(line)
                                    results.append(item)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Error parsing line {line_num}: {e}")
                    else:
                        logger.warning("Output file is empty")
                        
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON results: {e}")
                results = []
            except Exception as e:
                logger.error(f"Unexpected error reading results file: {e}")
                results = []
            finally:
                try:
                    if os.path.exists(temp_output):
                        os.unlink(temp_output)
                except Exception as e:
                    logger.warning(f"Could not clean up temp file: {e}")
        else:
            logger.error(f"Output file does not exist: {temp_output}")
        
        logger.info(f"Scrapy completed with {len(results)} results")
        if results:
            logger.info(f"Sample result: {results[0]}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error running Scrapy spider: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return []

async def process_urls_batch(job_id: str, urls: List[str], batch_size: int):
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
    try:
        logger.info(f"Creating Excel report with {len(results)} results")
        logger.info(f"Sample result: {results[0] if results else 'No results'}")
        
        if not results:
            df = pd.DataFrame(columns=['index', 'url', 'indexed', 'status', 'search_link', 'checked_at'])
        else:
            df = pd.DataFrame(results)
            logger.info(f"DataFrame columns: {df.columns.tolist()}")
            logger.info(f"DataFrame shape: {df.shape}")
        
        if len(df) > 0 and 'indexed' in df.columns:
            df['status'] = df['indexed'].apply(lambda x: 'Indexed' if x else 'Not Indexed')
        else:
            df['status'] = 'Unknown'
        
        if 'checked_at' not in df.columns or df['checked_at'].isna().all():
            df['checked_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        desired_columns = ['index', 'url', 'indexed', 'status', 'search_link', 'result_url', 'total_results', 'checked_at', 'error']
        available_columns = [col for col in desired_columns if col in df.columns]
        df = df[available_columns]
        
        os.makedirs('results', exist_ok=True)
        excel_file = f'results/google_index_results_{job_id}.xlsx'
        
        with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Index Results', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Index Results']
            
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            indexed_format = workbook.add_format({
                'bg_color': '#C6EFCE',
                'font_color': '#006100'
            })
            
            not_indexed_format = workbook.add_format({
                'bg_color': '#FFC7CE',
                'font_color': '#9C0006'
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            if 'status' in df.columns and len(df) > 0:
                status_col = df.columns.get_loc('status')
                
                worksheet.conditional_format(1, status_col, len(df), status_col, {
                    'type': 'text',
                    'criteria': 'containing',
                    'value': 'Indexed',
                    'format': indexed_format
                })
                
                worksheet.conditional_format(1, status_col, len(df), status_col, {
                    'type': 'text',
                    'criteria': 'containing',
                    'value': 'Not Indexed',
                    'format': not_indexed_format
                })
            
            for i, col in enumerate(df.columns):
                if len(df) > 0:
                    max_length = max(
                        df[col].astype(str).str.len().max() if not df[col].isna().all() else 0,
                        len(col)
                    ) + 2
                else:
                    max_length = len(col) + 2
                
                worksheet.set_column(i, i, min(max_length, 50))
        
        logger.info(f"Excel report created successfully: {excel_file}")
        logger.info(f"Final DataFrame info - Rows: {len(df)}, Columns: {len(df.columns)}")
        
        return excel_file
        
    except Exception as e:
        logger.error(f"Error creating Excel report: {str(e)}")
        raise Exception(f"Failed to create Excel report: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print(" Starting Google Index Checker API...")
    print(" API will be available on port 8877")
    print(" Frontend will be available at the root URL")
    print("-" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8877)