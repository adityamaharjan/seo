import httpx
from bs4 import BeautifulSoup
import re
import time
import uuid
import string
from collections import Counter
from urllib.parse import urlparse
from datetime import datetime, timezone
import asyncio

class AsyncSEOAnalyzer:
    def __init__(self, url):
        self.url = url.rstrip('/')
        self.domain = urlparse(url).netloc
        self.headers = {'User-Agent': 'Mozilla/5.0 (Compatible; FlatSEO/4.0; +https://seo.hakezlabs.qzz.io)'}
        self.timeout_seconds = 15
        
        self.stop_words = set([
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
            'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers',
            'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
            'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does',
            'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until',
            'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into',
            'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down',
            'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here',
            'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
            'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now', 'said', 'would', 'could'
        ])

    def _get_grade(self, score):
        if score >= 90: return "A"
        if score >= 80: return "B"
        if score >= 70: return "C"
        return "F"

    def _get_clean_text(self, soup):
        # Extract visible, relevant text content, excluding scripts, styles, etc.
        # Use a copy or modify directly? Modifying is fine since we only use it once for text.
        for script in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'noscript']):
            script.extract()
        return soup.get_text(separator=' ')

    def _tokenize_and_clean(self, text):
        text = text.lower()
        text = re.sub(f'[{re.escape(string.punctuation)}]', ' ', text)
        tokens = text.split()
        return [word for word in tokens if word not in self.stop_words and word.isalpha() and len(word) > 2]

    def _analyze_keywords(self, tokens):
        if not tokens:
            return "", "No content"
            
        word_freq = Counter(tokens)
        bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
        bigram_freq = Counter(bigrams)

        all_freq = word_freq.copy()
        all_freq.update(bigram_freq)
        sorted_items = sorted(all_freq.items(), key=lambda item: item[1], reverse=True)
        
        dominant_keyword = ""
        for term, count in sorted_items:
            if ' ' in term and count >= 3:
                dominant_keyword = term
                break
                
        if not dominant_keyword and sorted_items:
            dominant_keyword = sorted_items[0][0]

        top_bigrams = [f"'{k}' ({v})" for k, v in bigram_freq.most_common(5) if k != dominant_keyword]
        bigrams_str = ", ".join(top_bigrams)
        value = f"DOMINANT TERM: '{dominant_keyword}' | Top 5 Related Phrases: {bigrams_str}"
        
        return dominant_keyword, value

    async def analyze(self):
        try:
            start_time = time.time()
            async with httpx.AsyncClient(http2=True, verify=False, follow_redirects=True) as client:
                response = await client.get(self.url, headers=self.headers, timeout=self.timeout_seconds)
                
            load_time = round(time.time() - start_time, 3)
            html_size_kb = round(len(response.content) / 1024, 2)
            final_url = str(response.url)
            
            # Using lxml for faster parsing
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Extract Meta Data
            title_tag = soup.find('title')
            title = title_tag.string.strip() if title_tag and title_tag.string else ""
            
            meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
            desc_val = meta_desc_tag.get('content', '').strip() if meta_desc_tag else ""
            
            viewport_tag = soup.find('meta', attrs={'name': 'viewport'})
            
            h1s = soup.find_all('h1')
            h1_val = h1s[0].get_text().strip() if h1s else ""
            
            # Extract Text & Keywords
            clean_text = self._get_clean_text(BeautifulSoup(response.content, 'lxml')) # Parse again to keep original soup intact
            tokens = self._tokenize_and_clean(clean_text)
            word_count = len(tokens)
            
            dominant_keyword, keyword_value = self._analyze_keywords(tokens)
            
            # Calculate Stopword density on ORIGINAL text, not clean ones
            original_text = soup.get_text(separator=' ')
            words = re.findall(r'\w+', original_text.lower())
            total_word_count = len(words)
            stops = [w for w in words if w in self.stop_words]
            stop_percent = round((len(stops) / total_word_count) * 100, 1) if total_word_count > 0 else 0
            
            typos_found = [w for w in ["wtih", "everytime", "teh", "recieve"] if w in words]
            
            # Links & Images
            links = soup.find_all('a', href=True)
            internal = [l for l in links if self.domain in l['href'] or l['href'].startswith('/')]
            external = [l for l in links if self.domain not in l['href'] and l['href'].startswith('http')]
            
            imgs = soup.find_all('img')
            missing_alt = [i.get('src') for i in imgs if not i.get('alt')]

            # --- Scoring Logic ---
            meta_s = 100 if (30 < len(title) < 65 and desc_val) else 75
            qual_s = 100 if (word_count > 300 and not typos_found) else 60 # word count of significant tokens
            struc_s = 100 if (len(h1s) == 1 and len(h1_val) > 10) else 70
            perf_s = 100 if load_time < 0.8 else 85
            
            overall_score = round((meta_s * 0.3) + (qual_s * 0.3) + (struc_s * 0.2) + (perf_s * 0.2))

            # --- Generate JSON ---
            checks = {
                "title_tag": {
                    "status": "good" if 30 < len(title) < 65 else "warning",
                    "value": title if title else "Missing",
                    "message": "Title length is optimal." if 30 < len(title) < 65 else "Title is missing or not optimal length."
                },
                "meta_description": {
                    "status": "good" if desc_val else "critical",
                    "value": desc_val if desc_val else "Missing",
                    "message": "Meta description found." if desc_val else "Missing meta description."
                },
                "h1_heading": {
                    "status": "good" if len(h1s) == 1 and len(h1_val) > 10 else "warning" if len(h1s) > 1 else "critical",
                    "value": h1_val if h1_val else "Missing",
                    "message": f"Found {len(h1s)} H1 tag(s)."
                },
                "word_count": {
                    "status": "good" if word_count > 300 else "warning",
                    "value": f"{word_count} significant words",
                    "message": "Content depth is sufficient." if word_count > 300 else "Content might be too thin."
                },
                "keywords": {
                    "status": "good" if dominant_keyword else "warning",
                    "value": keyword_value,
                    "message": f"Dominant keyword is '{dominant_keyword}'" if dominant_keyword else "No dominant keyword found."
                },
                "typo_analysis": {
                    "status": "good" if not typos_found else "warning",
                    "value": ", ".join(typos_found) if typos_found else "None detected",
                    "message": "Potential typos detected." if typos_found else "No common typos detected."
                },
                "stop_word_density": {
                    "status": "good" if stop_percent < 45 else "warning",
                    "value": f"{stop_percent}%",
                    "message": "Stop word density is acceptable."
                },
                "mobile_viewport": {
                    "status": "good" if viewport_tag else "critical",
                    "message": "Viewport meta tag exists." if viewport_tag else "Missing viewport tag."
                },
                "image_alt_check": {
                    "status": "good" if not missing_alt else "warning",
                    "value": f"{len(missing_alt)} missing",
                    "message": f"{len(missing_alt)} images missing alt text."
                },
                "internal_links": {
                    "status": "good",
                    "value": len(internal),
                    "message": f"Found {len(internal)} internal links."
                },
                "external_links": {
                    "status": "good",
                    "value": len(external),
                    "message": f"Found {len(external)} external links."
                },
                "https_status": {
                    "status": "good" if final_url.startswith('https') else "critical",
                    "value": "HTTPS" if final_url.startswith('https') else "HTTP",
                    "message": "Secure connection established." if final_url.startswith('https') else "Insecure connection."
                },
                "page_load_time": {
                    "status": "good" if load_time < 0.8 else "warning",
                    "value": f"{load_time}s",
                    "message": "Excellent speed." if load_time < 0.8 else "Could be faster."
                },
                "page_size_kb": {
                    "status": "good" if html_size_kb < 150 else "warning",
                    "value": f"{html_size_kb} KB",
                    "message": "Page size is optimal." if html_size_kb < 150 else "Page size is slightly large."
                }
            }

            return dominant_keyword, {
                "id": f"report-{uuid.uuid4().hex[:8]}",
                "url": self.url,
                "domain": self.domain,
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "overall_score": overall_score,
                "overall_grade": self._get_grade(overall_score),
                "average_scores": {
                    "meta_data": meta_s,
                    "page_quality": qual_s,
                    "link_structure": struc_s,
                    "server_performance": perf_s
                },
                "checks": checks
            }

        except Exception as e:
            return "Error", {
                "id": f"report-{uuid.uuid4().hex[:8]}",
                "url": self.url,
                "domain": self.domain,
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "overall_score": 0,
                "overall_grade": "F",
                "average_scores": {
                    "meta_data": 0, "page_quality": 0, "link_structure": 0, "server_performance": 0
                },
                "checks": {
                    "error": {
                        "status": "critical",
                        "value": str(e),
                        "message": "Failed to analyze the URL."
                    }
                }
            }
