import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import string
from collections import Counter
import time

# --- Configuration ---
# Only the target URL needs to be set now.
TARGET_URL = "https://google.com"
TIMEOUT_SECONDS = 15

# Simple stop words list (for content cleaning and tokenization)
STOP_WORDS = set([
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

# --- Helper Functions (Content Prep) ---

def get_clean_text(soup):
    """Extracts visible, relevant text content, excluding scripts, styles, and navigation."""
    for script in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
        script.extract()
    return soup.get_text()

def tokenize_and_clean(text):
    """Converts text to lowercased words, removes punctuation, and filters stop words."""
    text = text.lower()
    text = re.sub(f'[{re.escape(string.punctuation)}]', '', text)
    tokens = text.split()
    return [word for word in tokens if word not in STOP_WORDS and word.isalpha() and len(word) > 2]

# --- 1. Performance & Security Checks ---

def check_response_time(response):
    """Measures and evaluates the network response time (Performance)."""
    response_time = response.elapsed.total_seconds()
    
    if response_time <= 0.5:
        status = "PASS"
        recommendation = "Excellent speed. Aim for sub 0.5s response time."
    elif response_time <= 1.5:
        status = "WARNING"
        recommendation = "Acceptable speed, but could be faster. Consider server optimization."
    else:
        status = "FAIL"
        recommendation = "Slow response time. This severely hurts UX and SEO ranking."
        
    return {"name": "Network Response Time", "status": status, "value": f"{response_time:.2f} seconds", "recommendation": recommendation}

def check_https_status(response):
    """Checks if the final URL after redirects is secure (Security)."""
    final_url = response.url
    
    if final_url.startswith('https://'):
        if len(response.history) > 0 and response.history[0].url.startswith('http://'):
            status = "PASS"
            recommendation = "Secure **HTTPS** connection established with a good **HTTP to HTTPS redirect**."
            value = "HTTPS (Redirected)"
        else:
            status = "PASS"
            recommendation = "Secure **HTTPS** connection established."
            value = "HTTPS"
    else:
        status = "FAIL"
        recommendation = "**The final connection is HTTP**, which is insecure, harms trust, and negatively impacts SEO ranking."
        value = "HTTP (Insecure)"
        
    return {"name": "HTTPS Security Check", "status": status, "value": value, "recommendation": recommendation}

# --- 2. Traditional On-Page Checks ---

def check_title_tag(soup):
    """Checks for title presence and length."""
    title_tag = soup.find('title')
    title_text = title_tag.text if title_tag else None
    
    if not title_text:
        status = "FAIL"
        recommendation = "Title tag is missing or empty. This is critical for search ranking and display."
        length = 0
    else:
        length = len(title_text)
        if 30 <= length <= 60:
            status = "PASS"
            recommendation = "Title length is optimal (30-60 chars)."
        elif length < 30:
            status = "WARNING"
            recommendation = "Title is too short. Use the extra space to include more keywords."
        else:
            status = "WARNING"
            recommendation = "Title is too long. It risks being truncated in search results."

    return {"name": "Title Tag Analysis", "status": status, "value": f"Length: {length} chars ('{title_text[:50]}...')" if title_text else "Missing", "recommendation": recommendation}

def check_meta_description(soup):
    """Checks for meta description presence and length."""
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_content = meta_desc.get('content', '').strip() if meta_desc else None
    
    if not desc_content:
        status = "FAIL"
        recommendation = "Meta Description is missing or empty. This is crucial for click-through rate (CTR)."
        length = 0
    else:
        length = len(desc_content)
        if 100 <= length <= 160:
            status = "PASS"
            recommendation = "Meta Description length is optimal (100-160 chars)."
        elif length < 100:
            status = "WARNING"
            recommendation = "Description is too short. Add more detail to entice clicks."
        else:
            status = "WARNING"
            recommendation = "Description is too long. It risks being truncated in search results."

    return {"name": "Meta Description Check", "status": status, "value": f"Length: {length} chars ('{desc_content[:50]}...')" if desc_content else "Missing", "recommendation": recommendation}

def check_h1_tag(soup):
    """Checks for H1 presence and count."""
    h1_tags = soup.find_all('h1')
    count = len(h1_tags)
    
    if count == 1:
        status = "PASS"
        recommendation = "Exactly one H1 tag found. This is the best practice for page structure."
        value = f"1 H1 found ('{h1_tags[0].text.strip()[:50]}...')"
    elif count == 0:
        status = "FAIL"
        recommendation = "No H1 tag found. This removes the main signal for your page's topic."
        value = "0 H1 tags found"
    else:
        status = "WARNING"
        recommendation = f"{count} H1 tags found. While technically allowed, it can dilute topical focus. Aim for one."
        value = f"{count} H1 tags found"

    return {"name": "H1 Structure Check", "status": status, "value": value, "recommendation": recommendation}

def check_viewport(soup):
    """Checks for the mobile viewport meta tag (Technical SEO)."""
    viewport_tag = soup.find('meta', attrs={'name': 'viewport'})
    
    if viewport_tag and 'content' in viewport_tag.attrs:
        content = viewport_tag['content'].lower()
        if 'width=device-width' in content and 'initial-scale' in content:
            status = "PASS"
            recommendation = "Mobile viewport tag is correctly configured."
        else:
            status = "WARNING"
            recommendation = "Viewport tag found but content settings might be suboptimal for responsiveness."
    else:
        status = "FAIL"
        recommendation = "Missing viewport meta tag. Page is not optimized for mobile devices."
        
    return {"name": "Mobile Viewport Check", "status": status, "value": "Present" if viewport_tag else "Missing", "recommendation": recommendation}


# --- 3. Dynamic Content & Keyword Analysis ---

def analyze_content_length(tokens):
    """Checks the overall word count of the page (Content Depth)."""
    word_count = len(tokens)
    
    if word_count >= 1500:
        status = "PASS"
        recommendation = "Excellent content depth. High word counts often correlate with comprehensive coverage."
    elif word_count >= 500:
        status = "WARNING"
        recommendation = "Decent length, but could be more comprehensive. Aim for content over 1000 words for competitive topics."
    else:
        status = "FAIL"
        recommendation = "Low word count. The content is likely too thin for competitive search terms."
        
    return {"name": "Content Word Count", "status": status, "value": f"{word_count} words", "recommendation": recommendation}


def analyze_and_suggest_keywords(tokens):
    """
    Identifies the most dominant term (unigram or bigram) and suggests top
    related terms.
    Returns: Dict containing analysis result AND the dominant keyword string.
    """
    
    if not tokens:
        return {
            "name": "Keyword Suggestion & Dominance", "status": "N/A", "value": "No clean text available",
            "recommendation": "Cannot generate keyword suggestions without visible content.",
            "dominant_keyword": ""
        }
    
    word_freq = Counter(tokens)
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    bigram_freq = Counter(bigrams)

    all_freq = word_freq.copy()
    all_freq.update(bigram_freq)
    
    sorted_items = sorted(all_freq.items(), key=lambda item: item[1], reverse=True)
    
    dominant_keyword = ""
    # Try to find a meaningful bigram first
    for term, count in sorted_items:
        if ' ' in term and count >= 3:
            dominant_keyword = term
            break
    
    # Fallback to the most frequent unigram
    if not dominant_keyword and sorted_items:
        dominant_keyword = sorted_items[0][0]

    # Format related suggestions
    top_unigrams = [f"'{k}' ({v})" for k, v in word_freq.most_common(5) if k != dominant_keyword]
    top_bigrams = [f"'{k}' ({v})" for k, v in bigram_freq.most_common(5) if k != dominant_keyword]

    bigrams_str = ", ".join(top_bigrams)

    value = f"DOMINANT TERM: '{dominant_keyword}' | Top 5 Related Phrases: {bigrams_str}"
    
    return {
        "name": "Keyword Suggestion & Dominance", 
        "status": "PASS" if dominant_keyword else "N/A", 
        "value": value, 
        "recommendation": f"The page is primarily focused on **'{dominant_keyword}'**. Use related phrases to capture long-tail traffic.",
        "dominant_keyword": dominant_keyword
    }

def analyze_keyword_density(soup, tokens, primary_keyword):
    """Calculates keyword density for the identified primary keyword."""
    
    if not primary_keyword:
        return {"name": "Dynamic Keyword Density", "status": "N/A", "value": "No dominant keyword identified", "recommendation": "Content is too sparse for meaningful keyword analysis."}
        
    keyword_tokens = primary_keyword.lower().split()
    keyword_count = sum(tokens.count(kw) for kw in keyword_tokens)
    total_words = len(tokens)
    
    density = (keyword_count / total_words) * 100 if total_words > 0 else 0
    
    # Check if the primary keyword is in the Title or H1
    title_text = soup.find('title').text.lower() if soup.find('title') else ""
    h1_tag = soup.find('h1')
    h1_text = h1_tag.text.lower() if h1_tag else ""
    
    critical_presence = primary_keyword.lower() in title_text or primary_keyword.lower() in h1_text
    
    if 2 <= density <= 5 and critical_presence:
        status = "PASS"
        recommendation = f"Density for '{primary_keyword}' is optimal (2-5%) and present in critical tags."
    elif density < 2:
        status = "WARNING"
        recommendation = f"Density for '{primary_keyword}' is low ({density:.2f}%). Use it more naturally to reinforce topic."
    elif density > 5:
        status = "WARNING"
        recommendation = f"Density for '{primary_keyword}' is high ({density:.2f}%). Risk of keyword stuffing. Reduce usage."
    else:
        status = "FAIL"
        recommendation = f"Dominant keyword '{primary_keyword}' not found in Title or H1. This mismatch weakens SEO targeting."

    return {"name": "Dynamic Keyword Density", "status": status, "value": f"{density:.2f}% ({keyword_count} uses)", "recommendation": recommendation}


def run_analysis(url):
    """Main function to fetch the page and run all analysis checks."""
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        
        # Check 1 & 2: Network Performance and Security (requires the raw response object)
        time_check = check_response_time(response)
        https_check = check_https_status(response)
        
        response.raise_for_status() 
        
        # Proceed with content analysis only if request was successful
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Prepare content for in-depth analysis
        clean_text = get_clean_text(soup)
        tokens = tokenize_and_clean(clean_text)
        
        # Step 1: Dynamic Keyword Analysis (generates the primary keyword)
        keyword_result = analyze_and_suggest_keywords(tokens)
        dominant_keyword = keyword_result.get("dominant_keyword", "")
        
        # Run all subsequent checks
        results = [
            time_check,
            https_check,
            check_title_tag(soup),
            check_meta_description(soup),
            check_h1_tag(soup),
            check_viewport(soup),
            analyze_content_length(tokens),
            keyword_result, # The suggestion/dominance result
            analyze_keyword_density(soup, tokens, dominant_keyword), # Uses the dominant keyword
        ]
        
        return results, dominant_keyword

    except requests.exceptions.RequestException as e:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        time_check = check_response_time(response)
        https_check = check_https_status(response)
        
        # Handle connection and request errors gracefully
        # NOTE: Still return performance/security checks even if the full page fails to load
        return [time_check, https_check, {
            "name": "Content Analysis Failure",
            "status": "ERROR",
            "value": f"Request failed: {e.__class__.__name__}",
            "recommendation": f"Could not connect, URL is broken, or timed out after {TIMEOUT_SECONDS} seconds."
        }], "N/A"
    except Exception as e:
        # Handle other unexpected errors
        return [{
            "name": "Unexpected Script Error",
            "status": "ERROR",
            "value": f"An unexpected error occurred: {e}",
            "recommendation": "Review the URL and ensure the script dependencies are installed."
        }], "N/A"

# --- Reporting ---

def print_report(results, url, primary_keyword):
    """Prints the final, formatted analysis report."""
    print("=" * 70)
    print(f"       COMPREHENSIVE DYNAMIC SEO AUDIT REPORT")
    print("=" * 70)
    print(f"Target URL: {url}")
    print(f"Dynamically Identified Primary Keyword: {primary_keyword}\n")
    
    # Calculate simple score - only count PASS/WARNING/FAIL, exclude ERROR/N/A
    scored_results = [r for r in results if r['status'] in ['PASS', 'WARNING', 'FAIL']]
    passed = sum(1 for r in scored_results if r['status'] == 'PASS')
    warnings = sum(1 for r in scored_results if r['status'] == 'WARNING')
    total_checks = len(scored_results)
    
    # Calculate score (PASS = 100%, WARNING = 50%, FAIL = 0%)
    score = ((passed * 1) + (warnings * 0.5)) / total_checks * 100 if total_checks > 0 else 0
    
    print(f"Overall Completion Status: {'COMPLETE' if 'ERROR' not in [r['status'] for r in results] else 'FAILED'}")
    print(f"Simplified Score: {score:.0f}/100\n")
    
    for i, result in enumerate(results):
        # ANSI escape codes for coloring terminal output
        status_color = "\033[94m" # Default Blue/N/A
        if result['status'] == 'PASS':
            status_color = "\033[92m" # Green
        elif result['status'] == 'WARNING':
            status_color = "\033[93m" # Yellow
        elif result['status'] == 'FAIL' or result['status'] == 'ERROR':
            status_color = "\033[91m" # Red
            
        reset_color = "\033[0m"
        
        print(f"--- Check {i + 1}: {result['name'].ljust(30)} ---")
        print(f"  Status:       {status_color}{result['status'].ljust(8)}{reset_color}")
        print(f"  Value Found:  {result['value']}")
        print(f"  Recommendation: {result['recommendation']}\n")
        
    print("=" * 70)
    
    
def map_status_to_json(status):
    mapping = {
        "PASS": "good",
        "WARNING": "warning",
        "FAIL": "critical",
        "ERROR": "critical",
        "N/A": "na"
    }
    return mapping.get(status, "na")

# --- Convert raw results into JSON format ---
def generate_json_response(results):
    """
    Converts the list of SEO check results into standardized JSON format.
    Calculates an overall score based on PASS/WARNING/FAIL checks.
    """
    checks_mapping = {
        "Title Tag Analysis": "title",
        "Meta Description Check": "meta_description",
        "H1 Structure Check": "h1",
        "Mobile Viewport Check": "viewport",
        "Content Word Count": "content_word_count",
        "Keyword Suggestion & Dominance": "keywords",
        "Dynamic Keyword Density": "keyword_density",
        "Network Response Time": "response_time",
        "HTTPS Security Check": "https_status"
    }
    
    json_checks = {}
    scored_results = [r for r in results if r['status'] in ['PASS', 'WARNING', 'FAIL']]
    passed = sum(1 for r in scored_results if r['status'] == 'PASS')
    warnings = sum(1 for r in scored_results if r['status'] == 'WARNING')
    total_checks = len(scored_results)
    
    score = ((passed * 1) + (warnings * 0.5)) / total_checks * 100 if total_checks > 0 else 0

    for r in results:
        key = checks_mapping.get(r['name'], r['name'].replace(" ", "_").lower())
        json_checks[key] = {
            "status": map_status_to_json(r['status']),
            "message": r.get("recommendation", "")
        }
    
    return {
        "score": round(score),
        "checks": json_checks
    }

if __name__ == "__main__":
    report_results, dominant_keyword = run_analysis(TARGET_URL)
    
    json_output = generate_json_response(report_results)
    
    import json
    print(json.dumps(json_output, indent=2))
