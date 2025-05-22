import scrapy
from urllib.parse import quote
from scrapy import Request
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class GrSpider(scrapy.Spider):
    name = "gr"
    allowed_domains = ["google.com"]
 
    def __init__(self, urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not urls:
            raise ValueError("You must pass -a urls=url1,url2,...")
        
        if ',' in urls:
            self.targets = [url.strip() for url in urls.split(",") if url.strip()]
        else:
            self.targets = [url.strip() for url in urls.split("\n") if url.strip()]
        
        logger.info(f"Spider initialized with {len(self.targets)} URLs")

    def start_requests(self):
        """Generate requests for each URL to check"""
        for idx, site in enumerate(self.targets):
            if not site.startswith(('http://', 'https://')):
                site = 'https://' + site
            
            q = quote(site, safe="")
            search_url = f"https://www.google.com/search?q=site:{q}"

            yield Request(
                url=search_url,
                callback=self.parse,
                meta={
                    "zyte_api_automap": {
                        "serp": True,
                        "serpOptions": {"extractFrom": "httpResponseBody"},
                        "geolocation": "US"
                    },
                    "index": idx,
                    "keyword": site,
                    "original_url": self.targets[idx]  
                },
                dont_filter=True,
                errback=self.handle_error
            )

    def parse(self, response):
        """Parse Google search results to determine if URL is indexed"""
        idx = response.meta["index"]
        site = response.meta["keyword"]
        original_url = response.meta["original_url"]
        
        try:
            serp_data = response.raw_api_response.get("serp", {})
            organic_results = serp_data.get("organicResults", [])
            
            indexed = False
            result_url = None
            
            for result in organic_results:
                result_link = result.get("url", "")
                if result_link and (original_url in result_link or site in result_link):
                    indexed = True
                    result_url = result_link
                    break
            
            if not indexed and organic_results:
                for result in organic_results:
                    result_link = result.get("url", "")
                    if result_link:
                        from urllib.parse import urlparse
                        try:
                            original_domain = urlparse(original_url).netloc
                            result_domain = urlparse(result_link).netloc
                            if original_domain == result_domain:
                                indexed = True
                                result_url = result_link
                                break
                        except:
                            pass
            
            logger.info(f"URL {idx + 1}/{len(self.targets)}: {original_url} - {'Indexed' if indexed else 'Not Indexed'}")
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            yield {
                "index": idx,
                "url": original_url,
                "indexed": indexed,
                "search_link": response.url,
                "result_url": result_url,
                "total_results": len(organic_results),
                "checked_at": current_time
            }
            
        except Exception as e:
            logger.error(f"Error parsing response for {original_url}: {str(e)}")
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            yield {
                "index": idx,
                "url": original_url,
                "indexed": False,
                "search_link": response.url,
                "error": str(e),
                "checked_at": current_time
            }

    def handle_error(self, failure):
        """Handle request errors"""
        request = failure.request
        idx = request.meta.get("index", 0)
        original_url = request.meta.get("original_url", "")
        
        logger.error(f"Request failed for {original_url}: {failure.value}")
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        yield {
            "index": idx,
            "url": original_url,
            "indexed": False,
            "search_link": request.url,
            "error": str(failure.value),
            "checked_at": current_time
        }

    def closed(self, reason):
        """Called when spider closes"""
        logger.info(f"Spider closed: {reason}")
        logger.info(f"Total URLs processed: {len(self.targets)}")