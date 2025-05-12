import streamlit as st
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import pandas as pd
import json
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy import Spider
import tempfile
import os

# Initialize AI model
llm = ChatOpenAI(temperature=0.7, model="gpt-4")

def get_page_content(url):
    """Improved content fetcher with headers and Selenium fallback"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            st.warning("Requests blocked, falling back to Selenium...")
            return selenium_fetch(url)
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

def selenium_fetch(url):
    """Headless browser fetch for JS-heavy or protected sites"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        driver.implicitly_wait(5)
        return driver.page_source
    except Exception as e:
        return f"Selenium Error: {str(e)}"
    finally:
        if 'driver' in locals():
            driver.quit()

def generate_ai_questions(content):
    """AI-powered question suggestion generator"""
    if content.startswith("Error:"):
        return "Could not generate questions due to: " + content
    
    prompt = ChatPromptTemplate.from_template(
        "Based on this webpage content, suggest 5 relevant scraping questions:"
        "\n\n{content}\n\nFormat as numbered list."
    )
    chain = prompt | llm
    return chain.invoke({"content": content[:3000]}).content

def bs4_scraper(url):
    """BeautifulSoup-based scraper with structured data extraction"""
    content = get_page_content(url)
    
    if content.startswith("Error:") or content.startswith("Selenium Error:"):
        return {'error': content}
    
    try:
        soup = BeautifulSoup(content, 'html.parser')
        
        # Get headers with their context
        headers = []
        for h in soup.find_all(['h1', 'h2', 'h3']):
            headers.append({
                'text': h.text.strip(),
                'tag': h.name,
                'links': [a['href'] for a in h.find_all_next('a', href=True, limit=3)]
            })
        
        return {
            'title': soup.title.string if soup.title else 'No title',
            'headers': headers,
            'all_links': [a['href'] for a in soup.find_all('a', href=True)],
            'text': soup.get_text(separator=' ', strip=True)[:1000] + '...'
        }
    except Exception as e:
        return {'error': str(e)}

def selenium_scraper(url):
    """Selenium-based scraper for JavaScript sites"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        driver.implicitly_wait(5)
        
        return {
            'title': driver.title,
            'text': driver.find_element("tag name", 'body').text[:1000] + '...',
            'scripts': len(driver.find_elements("tag name", 'script'))
        }
    except Exception as e:
        return {'error': str(e)}
    finally:
        if 'driver' in locals():
            driver.quit()

class CustomSpider(Spider):
    """Scrapy spider for advanced scraping"""
    name = 'streamlit_spider'
    
    def parse(self, response):
        yield {
            'url': response.url,
            'title': response.css('title::text').get(),
            'content': response.css('body::text').get()[:1000] + '...'
        }

def scrapy_scraper(url):
    """Scrapy-based scraper with temp file handling"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(f"""
import scrapy
from scrapy.spiders import Spider

class TempSpider(CustomSpider):
    start_urls = ['{url}']
""")
        
        process = CrawlerProcess(get_project_settings())
        process.crawl(TempSpider)
        process.start()
        
        return process.spider_loader.load('streamlit_spider').crawler.stats.get_stats()
    except Exception as e:
        return {'error': str(e)}
    finally:
        if 'f' in locals() and os.path.exists(f.name):
            os.unlink(f.name)

# Streamlit UI
st.set_page_config(page_title="AI Web Scraping Agent", layout="wide")

# Sidebar controls
with st.sidebar:
    st.header("Configuration")
    url = st.text_input("Enter Target URL", "https://example.com")
    tool = st.selectbox("Select Scraping Tool", 
                       ["BeautifulSoup", "Selenium", "Scrapy"])
    ai_enabled = st.checkbox("Enable AI Suggestions", True)

# Main interface
col1, col2 = st.columns([1, 2])

with col1:
    st.header("Scraping Controls")
    if st.button("Analyze Page"):
        with st.spinner("Processing..."):
            # Get basic content for AI suggestions
            content = get_page_content(url)
            
            if ai_enabled and content and not content.startswith("Error:"):
                with st.expander("AI Suggested Questions"):
                    questions = generate_ai_questions(content)
                    st.write(questions)
                    
            # Tool selection
            if tool == "BeautifulSoup":
                result = bs4_scraper(url)
            elif tool == "Selenium":
                result = selenium_scraper(url)
            elif tool == "Scrapy":
                result = scrapy_scraper(url)
            
            st.session_state.scraping_result = result

with col2:
    st.header("Results")
    if 'scraping_result' in st.session_state:
        if 'error' in st.session_state.scraping_result:
            st.error(f"Scraping failed: {st.session_state.scraping_result['error']}")
            if "403" in st.session_state.scraping_result['error']:
                st.warning("Tip: Try using **Selenium** instead (some sites block automated requests).")
        else:
            st.subheader(f"Results using {tool}")
            
            if tool == "BeautifulSoup":
                st.subheader("Headers with Related Links")
                for header in st.session_state.scraping_result['headers']:
                    with st.expander(f"{header['tag'].upper()}: {header['text']}"):
                        st.write("Related links:")
                        for link in header['links']:
                            st.write(link)
                
                st.subheader("All Links")
                st.write(st.session_state.scraping_result['all_links'])
                
            elif tool == "Selenium":
                st.json(st.session_state.scraping_result)
                
            elif tool == "Scrapy":
                st.write(st.session_state.scraping_result)
            
            # Export options
            st.download_button(
                label="Download JSON Report",
                data=json.dumps(st.session_state.scraping_result, indent=2),
                file_name="scraping_report.json",
                mime="application/json"
            )

# Tool-specific documentation
with st.expander("Tool Documentation"):
    st.markdown("""
    **BeautifulSoup**: Best for static HTML pages
    - Fast parsing
    - CSS selector support
    - Limited JavaScript handling
    
    **Selenium**: Ideal for JavaScript-heavy sites
    - Real browser simulation
    - Interactive element handling
    - Slower performance
    
    **Scrapy**: Professional scraping
    - Built-in asynchronous handling
    - Middleware support
    - Complex setup
    """)

# Usage tips
st.info("""💡 Pro Tips: 
- Start with BeautifulSoup for basic sites
- Use Selenium for dynamic content or if getting 403 errors
- Choose Scrapy for large-scale projects
- Check browser console for errors if scraping fails""")
