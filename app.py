import streamlit as st
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import pandas as pd
import json
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy import Spider
import tempfile
import os

# Initialize AI model
llm = ChatOpenAI(temperature=0.7, model="gpt-4o")

def get_page_content(url):
    """Basic content fetcher with error handling"""
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        return response.text
    except Exception as e:
        return str(e)

def generate_ai_questions(content):
    """AI-powered question suggestion generator"""
    prompt = ChatPromptTemplate.from_template(
        "Based on this webpage content, suggest 5 relevant scraping questions:"
        "\n\n{content}\n\nFormat as numbered list."
    )
    chain = prompt | llm
    return chain.invoke({"content": content[:3000]}).content  # Truncate for token limits

def bs4_scraper(url):
    """BeautifulSoup-based scraper with data extraction"""
    content = get_page_content(url)
    soup = BeautifulSoup(content, 'html.parser')
    
    return {
        'title': soup.title.string if soup.title else 'No title',
        'headers': [h.text for h in soup.find_all(['h1', 'h2', 'h3'])],
        'links': [a['href'] for a in soup.find_all('a', href=True)],
        'text': soup.get_text(separator=' ', strip=True)[:1000] + '...'
    }

def selenium_scraper(url):
    """Selenium-based scraper for JavaScript sites"""
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(url)
        driver.implicitly_wait(5)
        
        return {
            'title': driver.title,
            'text': driver.find_element("tag name", 'body').text[:1000] + '...',
            'scripts': len(driver.find_elements("tag name", 'script'))
        }
    finally:
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
    
    # Cleanup temporary file
    os.unlink(f.name)
    
    return process.spider_loader.load('streamlit_spider').crawler.stats.get_stats()

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
            
            if ai_enabled and content:
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
        st.subheader(f"Results using {tool}")
        
        if tool == "BeautifulSoup":
            df = pd.DataFrame({
                'Headers': st.session_state.scraping_result['headers'],
                'Links': st.session_state.scraping_result['links']
            })
            st.dataframe(df)
            
        elif tool == "Selenium":
            st.json(st.session_state.scraping_result)
            
        elif tool == "Scrapy":
            st.write(st.session_state.scraping_result)
        
        # Export options
        st.download_button(
            label="Download JSON Report",
            data=json.dumps(st.session_state.scraping_result, indent=2),
            file_name="scraping_report.json"
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
st.info("💡 Pro Tips: Start with BeautifulSoup for basic sites, use Selenium for dynamic content, and Scrapy for large-scale projects.")