import httpx
import re
from bs4 import BeautifulSoup
from markdownify import markdownify

class FetchError(Exception):
    """Custom exception for fetching errors."""
    pass

def fetch_press_release(url: str) -> str:
    """
    Fetches the raw HTML of a press release given its URL.
    
    Args:
        url (str): The URL of the press release.
        
    Returns:
        str: Raw HTML content.
        
    Raises:
        FetchError: If a 4xx/5xx error occurs or a timeout happens.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        raise FetchError(f"HTTP error fetching {url}: {e.response.status_code} {e.response.reason_phrase}") from e
    except httpx.TimeoutException as e:
        raise FetchError(f"Timeout while fetching {url}") from e
    except httpx.RequestError as e:
        raise FetchError(f"Request error while fetching {url}: {str(e)}") from e

def html_to_markdown(html: str) -> str:
    """
    Converts raw HTML into normalized Markdown.
    Strips nav bars, footers, cookie banners, and other non-content elements
    to keep only the main article body.
    
    Args:
        html (str): The raw HTML content.
        
    Returns:
        str: Normalized Markdown text.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove standard non-content HTML5 semantic tags and resources
    for element in soup(["nav", "footer", "header", "aside", "script", "style", "noscript", "iframe"]):
        element.decompose()
        
    # Remove elements that are likely cookie banners, popups, or advertisements based on their class or id
    removable_keywords = re.compile(r'cookie|banner|popup|modal|advert|newsletter|consent', re.I)
    
    for element in soup.find_all(class_=removable_keywords):
        element.decompose()
        
    for element in soup.find_all(id=removable_keywords):
        element.decompose()
        
    # Attempt to locate the main content area to avoid parsing sidebars and site-wide wrappers
    main_content = soup.find("main") or soup.find("article") or soup.find(id=re.compile(r'main', re.I)) or soup.body
    
    if not main_content:
        return ""
        
    # Convert the extracted main content to Markdown
    markdown_text = markdownify(str(main_content), heading_style="ATX")
    
    # Normalize excessive newlines to a double newline (standard paragraph break)
    normalized_md = re.sub(r'\n{3,}', '\n\n', markdown_text).strip()
    
    return normalized_md
