# AI Product Intelligence Platform
## Multi-Agent System Specification
**Version:** 1.0  
**Status:** Draft  
**Date:** 2026-06-21  
**Author:** Saghar Rabiei

---

## 0. Executive Summary

Two independently sellable AI agents that communicate via MCP protocol.
Neither agent knows the other's internals. Each solves a complete,
standalone business problem. Together they form a full product
intelligence platform for Iranian e-commerce.

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCT 1                                     │
│              SiteCrawler Agent                                   │
│                                                                  │
│  Input:  Any e-commerce site URL                                │
│  Output: Structured, continuously updated product data          │
│  Sells:  To anyone who needs live competitor/supplier data      │
│                                                                  │
│  Exposes: MCP Server                                            │
│    register_site()  get_products()  get_changes()              │
│    get_crawl_status()  subscribe_changes()                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                       MCP Protocol
                    (stdio or HTTP/SSE)
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    PRODUCT 2                                     │
│           Recommendation Agent                                   │
│                                                                  │
│  Input:  Customer query in Farsi (natural language)             │
│  Output: Ranked product recommendations with reasoning          │
│  Sells:  To e-commerce sites wanting AI customer assistants     │
│                                                                  │
│  Connects to: SiteCrawler MCP (or any product data MCP)        │
│  Exposes:     Chat UI + its own MCP Server                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Why Multi-Agent (Not One System)

### The Business Case

```
One Monolith:                        Two Agents:
─────────────────────────────        ──────────────────────────────
Client A needs crawler only          Client A buys crawler only
→ must buy whole system              → pays for crawler only

Client B has product DB already      Client B buys recommendation
→ can't use just the chat            → connects to their own DB

Can't sell parts                     4 revenue models:
Can't upgrade independently            1. Crawler only
Hard to maintain                       2. Recommendation only
One failure kills everything           3. Bundle (discount)
                                       4. White-label API
```

### The Technical Case

```
Separation of concerns:
  Crawler Agent   → knows about HTTP, HTML, JS rendering, sitemaps
  Recommend Agent → knows about NLP, Farsi, semantic search, chat

Neither needs to know what the other knows.
If crawler goes down, chat agent can serve from cached index.
If chat agent changes models, crawler is unaffected.
Each can be scaled independently.
```

---

## 2. How They Communicate

The ONLY interface between the two agents is the MCP protocol.

```
Recommendation Agent (MCP Client)
           │
           │ 1. tools/list → discovers available tools
           │ 2. get_products(site, filters) → initial index build
           │ 3. get_changes(site, since) → hourly sync
           │ 4. subscribe_changes(site, webhook) → real-time updates
           │
           ▼
SiteCrawler Agent (MCP Server)
```

The Recommendation Agent never:
- Knows what database the crawler uses
- Knows how the crawler extracts products
- Knows which sites are being crawled internally
- Needs to be updated when crawler internals change

This is the entire value of the MCP interface boundary.

---

# PRODUCT 1: SITECRAWLER AGENT

---

## 3. Problem Statement (Crawler)

Businesses need structured, continuously updated product data from
e-commerce sites they do not own and have no database access to.
They need this to work on any site without custom code per site,
and to stay updated as prices and inventory change.

---

## 4. Goals — Crawler (v1.0)

- Accept any e-commerce URL, zero site-specific code
- Autonomously choose discovery strategy per site
- Handle server-rendered AND JavaScript-rendered sites
- Extract structured product data using LLM (site-agnostic)
- Detect new products, price changes, deletions within 1 hour
- Expose all data via MCP server (5 tools)
- Store everything in local SQLite — zero external dependencies
- All tools and frameworks free and open source
- Work correctly on: sepantadp.com, parsazh.com, digikala.com,
  divar.ir, and any WooCommerce/Shopify site

---

## 5. Non-Goals — Crawler (v1.0)

- Sites behind login/authentication → v2.0
- CAPTCHA solving → v2.0
- Image content analysis (only URLs extracted) → v2.0
- Full-text search (handled by Recommendation Agent)
- Paying for any cloud rendering service

---

## 6. Target Sites — Crawler Capability Matrix

| Site | Platform | Rendering | Sitemap | Key Challenge |
|------|----------|-----------|---------|---------------|
| sepantadp.com | WooCommerce | Server-rendered | Yes (/sitemap.xml) | Baseline — simplest case |
| parsazh.com | WooCommerce | Server-rendered | Yes (/sitemap.xml) | Same as sepantadp — standard WooCommerce |
| digikala.com | Custom React | SPA (JS-rendered) | Yes (large) | Anti-bot, 1M+ products, needs Playwright |
| divar.ir | Custom React | SPA (JS-rendered) | Partial | Listings not products, infinite scroll, fast expiry |
| Any WooCommerce | WordPress | Server-rendered | Usually | Variable themes but same URL patterns |
| Shopify stores | Shopify | SSR+hydration | Yes (paginated) | Variant products, paginated sitemaps |

### Site-Specific Notes

**sepantadp.com and parsazh.com (primary demo sites):**
- Standard WooCommerce on WordPress
- Server-rendered — raw HTML contains full product data
- Sitemap at /sitemap.xml or /product-sitemap.xml
- URL patterns: /product/ for products, /product-category/ for categories
- No JS rendering needed — requests + BeautifulSoup sufficient
- Price in Iranian Tomans (تومان) — extract as numeric, store currency separately
- These are the easiest sites — use as baseline for testing

**digikala.com:**
- Full React SPA — raw HTML is empty shell
- Playwright required for all product pages
- Sitemap exists but is very large (sitemap index → child sitemaps)
- Has anti-bot measures: rate limiting, User-Agent detection
- Strategy: slower crawl (2s delay), rotate User-Agent, Playwright

**divar.ir:**
- Classified listings, not product catalog
- No product SKU, no fixed price (often negotiable)
- Listings expire — high deletion rate
- Requires separate data model (listing, not product)
- Infinite scroll on category pages — Playwright scroll simulation

---

## 7. Crawler Architecture

### 7.1 Why ReAct Agent (Not a Pipeline)

Real sites are unpredictable. A pipeline crashes on anything unexpected.
A ReAct agent reasons and recovers autonomously:

```
Unexpected situation     Pipeline response    Agent response
──────────────────────   ─────────────────    ──────────────────────────
Sitemap returns 404      Crash                Try /sitemap_index.xml,
                                              then category crawl
Page is JS-rendered      Returns empty data   Switch to Playwright
Rate limited (429)       Skip or crash        Exponential backoff, retry
Extraction fails         Silent skip          Retry with fallback prompt
robots.txt blocks path   ToS violation        Check allowed paths, adapt
Anti-bot redirect        Crash                Rotate User-Agent, delay
Product page is 404      Crash                Mark deleted, continue
```

### 7.2 Internal Architecture

```
┌──────────────────────────────────────────────────────┐
│              SITECRAWLER AGENT INTERNALS              │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │         LangGraph ReAct Agent                │   │
│  │         (crawler_agent.py)                   │   │
│  │                                              │   │
│  │  State machine with conditional edges:       │   │
│  │  RECON → DISCOVER → FETCH → EXTRACT          │   │
│  │       ↓          ↓       ↓        ↓          │   │
│  │   (strategy   (strategy  (render  (fallback  │   │
│  │    choice)     choice)   choice)   prompt)   │   │
│  └──────────────────┬───────────────────────────┘   │
│                     │                                │
│  ┌──────────────────▼───────────────────────────┐   │
│  │           Internal Tools                     │   │
│  │  (not exposed via MCP — implementation IP)   │   │
│  │                                              │   │
│  │  recon_site()         → robots.txt + platform│   │
│  │  discover_sitemap()   → parse XML sitemaps   │   │
│  │  discover_categories()→ crawl category pages │   │
│  │  fetch_html()         → requests (Type A)    │   │
│  │  fetch_rendered()     → Playwright (Type B)  │   │
│  │  extract_product()    → LLM extraction       │   │
│  │  detect_changes()     → diff vs stored       │   │
│  │  update_store()       → write to SQLite      │   │
│  │  report_status()      → structured logging   │   │
│  └──────────────────┬───────────────────────────┘   │
│                     │                                │
│  ┌──────────────────▼───────────────────────────┐   │
│  │           SQLite Database                    │   │
│  │  products / crawl_state / crawl_queue        │   │
│  │  change_log / site_config / webhooks         │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │      APScheduler (Sync Jobs)                 │   │
│  │  Job 1: Sitemap check     → every 1 hour     │   │
│  │  Job 2: Crawl queue       → every 5 minutes  │   │
│  │  Job 3: Deletion check    → every 24 hours   │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │      MCP SERVER (Public Interface)           │   │
│  │      5 tools — what clients pay for          │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

### 7.3 Rendering Strategy (Auto-Detected)

```
Type A: Server-Rendered
  Detection: product name + price found in raw HTML
  Tool: fetch_html() → requests==2.32.3
  Sites: sepantadp.com, parsazh.com, most WooCommerce

Type B: JS-Rendered (SPA)
  Detection: raw HTML is empty shell (<div id="root"> with no content)
  Tool: fetch_rendered() → Playwright==1.47.0 (Chromium, free)
  Sites: digikala.com, divar.ir

Type C: Hybrid (SSR + client hydration)
  Detection: partial content in HTML
  Tool: fetch_html() first, if incomplete → fetch_rendered()
  Sites: Next.js, Nuxt.js sites
```

Detection is automatic per page. No manual configuration needed.

### 7.4 Discovery Strategy (Ordered Fallback)

```
Step 1: Check robots.txt for Sitemap: directive
Step 2: Try /sitemap.xml
Step 3: Try /sitemap_index.xml → find product child sitemaps
Step 4: Try /product-sitemap.xml (WooCommerce Yoast plugin)
Step 5: Try /wp-sitemap-posts-product-1.xml (WordPress 5.5+ built-in)
Step 6: Crawl /product-category/ links from homepage
Step 7: Crawl homepage → follow product-pattern URLs
Step 8: Report failure with reason — never crash silently
```

---

## 8. Crawler Data Model

```sql
-- Core tables

CREATE TABLE products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    site                TEXT NOT NULL,
    url                 TEXT NOT NULL UNIQUE,
    name                TEXT,
    price               REAL,
    currency            TEXT DEFAULT 'IRR',
    availability        BOOLEAN,
    sku                 TEXT,
    category            TEXT,        -- JSON array
    description         TEXT,
    specs               TEXT,        -- JSON object
    images              TEXT,        -- JSON array of URLs
    brand               TEXT,
    -- Listing fields (divar-type)
    listing_type        TEXT DEFAULT 'product',  -- product / listing
    is_negotiable       BOOLEAN,
    location            TEXT,
    -- Metadata
    first_seen_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at     TIMESTAMP,
    last_checked_at     TIMESTAMP,
    is_deleted          BOOLEAN DEFAULT FALSE,
    extraction_confidence REAL
);

CREATE TABLE crawl_state (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    site                TEXT NOT NULL,
    url                 TEXT NOT NULL UNIQUE,
    status              TEXT DEFAULT 'pending',
    -- pending / crawling / done / failed / deleted
    sitemap_lastmod     TEXT,
    etag                TEXT,
    content_hash        TEXT,
    priority            INTEGER DEFAULT 5,
    -- 1=high (new/changed), 5=normal, 10=low
    retry_count         INTEGER DEFAULT 0,
    next_crawl_at       TIMESTAMP,
    error_message       TEXT,
    rendering_type      TEXT   -- html / playwright / hybrid
);

CREATE TABLE change_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    site                TEXT NOT NULL,
    url                 TEXT NOT NULL,
    change_type         TEXT NOT NULL,
    -- new / price_down / price_up / availability / deleted / updated
    old_value           TEXT,   -- JSON
    new_value           TEXT,   -- JSON
    changed_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pct_change          REAL    -- for price changes
);

CREATE TABLE crawl_queue (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    site                TEXT NOT NULL,
    url                 TEXT NOT NULL UNIQUE,
    priority            INTEGER DEFAULT 5,
    status              TEXT DEFAULT 'pending',
    queued_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP
);

CREATE TABLE webhooks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    site                TEXT NOT NULL,
    webhook_url         TEXT NOT NULL,
    subscription_id     TEXT UNIQUE,
    active              BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 9. Crawler MCP Interface (Public — What Clients Pay For)

```yaml
tools:

  register_site:
    description: >
      Register an e-commerce site for automatic crawling and monitoring.
      The crawler will discover all products and begin continuous sync.
      Works on any site without site-specific code — just the URL.
    inputs:
      url: {type: string, required: true, example: "https://sepantadp.com"}
      name: {type: string, required: true, example: "sepantadp"}
      config: {type: object, required: false, description: "optional crawl settings"}
    outputs:
      site_id: string
      status: string         # queued / crawling / done
      estimated_completion: string

  get_products:
    description: >
      Retrieve indexed products from a crawled site.
      Supports filtering by price, category, and availability.
      Use for initial data sync or full product listing.
    inputs:
      site: {type: string, required: true}
      category: {type: string, required: false}
      min_price: {type: number, required: false}
      max_price: {type: number, required: false}
      availability: {type: boolean, required: false}
      limit: {type: integer, default: 100, max: 1000}
      offset: {type: integer, default: 0}
    outputs:
      products: array
      total: integer
      last_updated: string   # ISO timestamp

  get_changes:
    description: >
      Get all product changes since a given timestamp.
      Use this for incremental sync — much cheaper than get_products
      when you only need what changed since your last check.
      Returns new, updated, and deleted products separately.
    inputs:
      site: {type: string, required: true}
      since: {type: string, required: true, format: ISO8601}
    outputs:
      new_products: array
      updated_products: array
      deleted_products: array
      timestamp: string

  get_crawl_status:
    description: >
      Get current crawl health and statistics for a registered site.
      Use to monitor whether the crawler is keeping up with site changes.
    inputs:
      site: {type: string, required: true}
    outputs:
      total_products: integer
      last_crawl: string
      next_crawl: string
      failed_urls: integer
      crawl_health: string   # ok / degraded / failing

  subscribe_changes:
    description: >
      Register a webhook to receive real-time notifications when
      products change. Your endpoint receives POST JSON with
      change_type, old_value, new_value for each changed product.
    inputs:
      site: {type: string, required: true}
      webhook_url: {type: string, required: true}
    outputs:
      subscription_id: string
      status: string
```

---

## 10. Crawler Site Config (YAML per Site)

```yaml
# config/sites/_template.yaml
name: site_identifier
url: https://example.com
language: fa               # fa / en
data_model: product        # product / listing (for divar-type)

sitemap: null              # null = auto-detect

url_patterns:
  products: ["/product/", "/p/"]
  categories: ["/product-category/", "/category/"]
  exclude: ["/cart", "/checkout", "/account", "/my-account"]

rendering: auto            # auto / html / playwright
playwright_wait_for: networkidle

crawl_delay_ms: 1000
max_concurrent: 3
respect_robots: true

sync:
  sitemap_check_hours: 1
  recrawl_changed_hours: 6
  recrawl_unchanged_days: 7
  full_crawl_days: 7
  deletion_check_hours: 24
  max_retries: 3
  retry_backoff_minutes: [5, 30, 120]
```

```yaml
# config/sites/sepantadp.yaml
name: sepantadp
url: https://sepantadp.com
language: fa
data_model: product
rendering: html             # server-rendered WooCommerce
crawl_delay_ms: 800
max_concurrent: 3
url_patterns:
  products: ["/product/"]
  categories: ["/product-category/"]
  exclude: ["/cart", "/checkout", "/my-account", "/wishlist"]
sync:
  sitemap_check_hours: 1
  recrawl_changed_hours: 6
```

```yaml
# config/sites/parsazh.yaml
name: parsazh
url: https://parsazh.com
language: fa
data_model: product
rendering: html             # WooCommerce — same as sepantadp
crawl_delay_ms: 800
max_concurrent: 3
url_patterns:
  products: ["/product/"]
  categories: ["/product-category/"]
  exclude: ["/cart", "/checkout", "/my-account"]
sync:
  sitemap_check_hours: 1
  recrawl_changed_hours: 6
```

```yaml
# config/sites/digikala.yaml
name: digikala
url: https://www.digikala.com
language: fa
data_model: product
rendering: playwright       # full React SPA
playwright_wait_for: networkidle
crawl_delay_ms: 2000        # more polite — large site
max_concurrent: 2
url_patterns:
  products: ["/product/", "/dkp-"]
  categories: ["/search/category-"]
  exclude: ["/cart", "/profile", "/login"]
sync:
  sitemap_check_hours: 2
  recrawl_changed_hours: 4  # prices change frequently
  max_retries: 5
```

```yaml
# config/sites/divar.yaml
name: divar
url: https://divar.ir
language: fa
data_model: listing         # NOT a product catalog
rendering: playwright
playwright_wait_for: networkidle
crawl_delay_ms: 2000
max_concurrent: 2
url_patterns:
  products: ["/v/"]         # listing URLs
  categories: ["/s/"]
  exclude: ["/support", "/blog"]
sync:
  sitemap_check_hours: null # no sitemap — category crawl only
  recrawl_changed_hours: 2  # listings change fast
  deletion_check_hours: 6   # listings expire quickly
```

---

## 11. Crawler Tech Stack (All Free)

```
Agent Framework:
  langgraph==0.2.28          # ReAct agent with state + conditional edges
  langchain==0.3.7           # Tool abstractions
  langchain-anthropic==0.2.4 # LLM provider (primary)

LLM for Extraction:
  Primary:  Claude claude-sonnet-4-6 (Anthropic API)
  Fallback: gpt-4o-mini via OpenRouter
  Local:    ollama + llama3.2 (fully free, lower accuracy)
  → Configurable in config.yaml, system works with any LLM

Web Fetching:
  requests==2.32.3           # Type A: server-rendered (sepantadp, parsazh)
  playwright==1.47.0         # Type B: JS-rendered (digikala, divar)
                             # Uses bundled Chromium — free
  beautifulsoup4==4.12.3     # HTML parsing
  lxml==5.3.0                # Sitemap XML parsing

Database:
  SQLite (stdlib)            # zero dependency, zero infrastructure
  sqlalchemy==2.0.36         # ORM (future PostgreSQL migration)
  alembic==1.13.3            # DB migrations

Scheduling:
  apscheduler==3.10.4        # Lightweight job scheduler, no Redis needed

MCP:
  mcp==1.0.0                 # Official MCP Python SDK

Utilities:
  fake-useragent==1.5.1      # Rotate User-Agents (anti-bot)
  tenacity==9.0.0            # Retry with exponential backoff
  loguru==0.7.2              # Structured logging

Testing:
  pytest==8.3.3
  pytest-asyncio==0.24.0
  respx==0.21.1              # Mock HTTP requests

Why these choices:
  LangGraph > LangChain agents: state machine + conditional edges
    needed for strategy switching (sitemap fail → category crawl)
  Playwright > Selenium: faster, better async, free bundled browser
  SQLite > PostgreSQL: zero infra, clients deploy anywhere
  APScheduler > Celery: no Redis dependency, lightweight
```

---

## 12. Crawler Agent System Prompt

```
You are an autonomous e-commerce crawler agent.
You receive a site URL and must discover and extract all product
data using only public web pages — no database access available.

ALWAYS START WITH RECONNAISSANCE:
1. fetch robots.txt → what paths are allowed?
2. Identify platform: WooCommerce / Shopify / React SPA / custom
3. Test if raw HTML contains product data or is JS-rendered
   → If raw HTML has name + price: use fetch_html()
   → If raw HTML is an empty <div id="root">: use fetch_rendered()

DISCOVERY — try in this order, stop when one works:
1. Check robots.txt for "Sitemap:" directive
2. Fetch /sitemap.xml
3. Fetch /sitemap_index.xml → find product child sitemaps
4. Try /product-sitemap.xml (WooCommerce Yoast)
5. Try /wp-sitemap-posts-product-1.xml (WordPress built-in)
6. Crawl /product-category/ links from homepage
7. Follow product-pattern URLs from homepage links

EXTRACTION RULES:
- Use extract_product() on every product URL found
- If confidence < 0.7: retry with fallback prompt
- For divar-type listing sites: use listing extraction prompt
- Never skip a page silently — always call report_status()

CHANGE DETECTION after each crawl:
- Compare new data hash with stored hash
- If price changed: flag as price_down or price_up
- If availability changed: flag as availability_update
- If URL gone: mark as deleted

FAILURE HANDLING — never crash, always recover:
- 404 on known URL: product deleted → mark_deleted(), continue
- 429 rate limit: backoff [5min, 30min, 120min], then retry
- 403 blocked: try different User-Agent, if still blocked: flag
- Empty extraction: retry with fallback prompt once, then flag
- Playwright timeout: increase wait_for time, retry once
- LLM API error: retry 3x, then use fallback model

REPORTING — always end with report_status() containing:
  pages_crawled, products_found, products_updated,
  products_deleted, errors, time_taken_seconds
```

---

## 13. Crawler Folder Structure

```
sitecrawler-agent/          ← Separate repo, separately deployable
│
├── SPEC.md
├── ARCHITECTURE.md
├── README.md
│
├── config/
│   ├── config.yaml         ← global: LLM choice, log level, DB path
│   └── sites/
│       ├── _template.yaml
│       ├── sepantadp.yaml
│       ├── parsazh.yaml
│       ├── digikala.yaml
│       └── divar.yaml
│
├── src/
│   ├── agent/
│   │   ├── crawler_agent.py    ← LangGraph ReAct agent
│   │   ├── prompts.py          ← system prompt + extraction prompts
│   │   └── state.py            ← LangGraph state definition
│   │
│   ├── tools/
│   │   ├── recon.py            ← fetch_robots, identify_platform
│   │   ├── discovery.py        ← sitemap parser, category crawl
│   │   ├── fetcher.py          ← fetch_html + fetch_rendered
│   │   ├── extractor.py        ← LLM product extraction
│   │   ├── differ.py           ← change detection + hash compare
│   │   ├── store.py            ← SQLite read/write
│   │   └── reporter.py         ← structured logging
│   │
│   ├── scheduler/
│   │   ├── jobs.py             ← 3 APScheduler jobs
│   │   └── queue.py            ← crawl queue management
│   │
│   ├── mcp/
│   │   └── server.py           ← MCP server, 5 public tools
│   │
│   ├── webhooks/
│   │   └── notifier.py         ← POST to subscriber webhooks
│   │
│   └── db/
│       ├── models.py           ← SQLAlchemy models
│       ├── queries.py          ← common query helpers
│       └── migrations/         ← Alembic migration files
│
├── tests/
│   ├── unit/
│   │   ├── test_discovery.py
│   │   ├── test_extractor.py
│   │   ├── test_differ.py
│   │   └── test_store.py
│   ├── integration/
│   │   ├── test_woocommerce.py ← sepantadp + parsazh
│   │   ├── test_spa.py         ← digikala
│   │   └── test_mcp.py         ← MCP interface
│   └── evals/
│       └── extraction_cases.yaml ← ground truth per site
│
├── .claude/
│   ├── CLAUDE.md
│   └── plan/
│       ├── phase1_crawl_core.md
│       ├── phase2_agent.md
│       ├── phase3_sync.md
│       └── phase4_mcp.md
│
├── requirements.txt        ← pinned versions
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 14. Crawler Success Criteria

```
Discovery:
  □ Finds 95%+ product URLs on WooCommerce sites with sitemap
  □ Falls back to category crawl within 30s of sitemap failure
  □ Correctly identifies JS-rendered vs server-rendered

Extraction (sepantadp + parsazh baseline):
  □ Product name: 99% accuracy
  □ Price: 98% accuracy (correct numeric value, no symbol)
  □ Availability: 97% accuracy
  □ Zero unhandled exceptions on any page type

Sync:
  □ New product detected within 1 hour of appearing on site
  □ Price change detected within 1 hour
  □ Deleted product detected within 24 hours

MCP Interface:
  □ tools/list returns 5 tools with correct schemas
  □ get_products() returns correctly filtered results
  □ get_changes() returns only changes since timestamp
  □ Webhook fires within 30 seconds of change detection

Performance:
  □ WooCommerce (1000 products): full crawl < 2 hours
  □ Memory: < 512MB during crawl
```

---

---

# PRODUCT 2: RECOMMENDATION AGENT

---

## 15. Problem Statement (Recommendation)

Customers visiting Iranian e-commerce sites describe what they need
in Farsi natural language. Current sites only support keyword search
which fails when customers don't know the exact product name, want
advice, or need products compared. Businesses lose sales because
customers can't find what they need.

---

## 16. Goals — Recommendation Agent (v1.0)

- Accept customer queries in Farsi (natural language)
- Understand intent: budget, category, use case, implicit needs
- Connect to SiteCrawler MCP to get product data
- Semantically search products beyond keyword matching
- Return ranked recommendations with Persian reasoning
- Remember context across conversation turns
- Track corrections to identify failure modes
- Expose chat as both UI and MCP server

---

## 17. Non-Goals — Recommendation Agent (v1.0)

- Placing orders or checkout (v2.0)
- Image-based product search (v2.0)
- Price negotiation (v2.0)
- Multi-site comparison in one query (v2.0)
- Voice interface (v2.0)

---

## 18. Recommendation Architecture

```
┌──────────────────────────────────────────────────────────┐
│         RECOMMENDATION AGENT INTERNALS                   │
│                                                          │
│  Customer (Farsi) ──────────────────────────────────┐   │
│                                                      │   │
│  ┌──────────────────────────────────────────────┐   │   │
│  │         LangGraph ReAct Agent                │   │   │
│  │                                              │   │   │
│  │  1. Parse intent from Farsi query            │   │   │
│  │  2. Extract: budget, category, use case      │   │   │
│  │  3. Plan search strategy                     │   │   │
│  │  4. Call search + filter tools               │   │   │
│  │  5. Rank + reason in Farsi                   │   │   │
│  │  6. Return with explanation                  │   │   │
│  └──────────────────┬───────────────────────────┘   │   │
│                     │                                │   │
│  ┌──────────────────▼───────────────────────────┐   │   │
│  │           Agent Tools                        │   │   │
│  │                                              │   │   │
│  │  semantic_search(query, site)                │   │   │
│  │    → ChromaDB vector search                  │   │   │
│  │                                              │   │   │
│  │  filter_products(price, category,            │   │   │
│  │                  availability, site)         │   │   │
│  │    → Metadata filter on ChromaDB             │   │   │
│  │                                              │   │   │
│  │  get_product_details(product_id)             │   │   │
│  │    → Full product from SQLite cache          │   │   │
│  │                                              │   │   │
│  │  get_crawler_products(site, filters)         │   │   │
│  │    → MCP call to SiteCrawler                 │   │   │
│  │                                              │   │   │
│  │  sync_from_crawler(site, since)              │   │   │
│  │    → get_changes() from SiteCrawler MCP      │   │   │
│  └──────────────────┬───────────────────────────┘   │   │
│                     │                                │   │
│  ┌──────────────────▼───────────────────────────┐   │   │
│  │   Local Index (ChromaDB)                     │   │   │
│  │   + Product Cache (SQLite)                   │   │   │
│  │                                              │   │   │
│  │  Synced hourly from SiteCrawler via MCP      │   │   │
│  │  One collection per registered site          │   │   │
│  └──────────────────────────────────────────────┘   │   │
│                                                      │   │
│  ┌──────────────────────────────────────────────┐   │   │
│  │   Session Memory (SQLite)                    │   │   │
│  │   + Correction Tracker                       │   │   │
│  │   + K-Means Failure Clustering               │   │   │
│  └──────────────────────────────────────────────┘   │   │
│                                                      │   │
│  ┌──────────────────────────────────────────────┐   │   │
│  │   Chat Interface (Streamlit)                 │◄──┘   │
│  └──────────────────────────────────────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │   MCP Server (expose chat as MCP for others)     │   │
│  │   get_recommendations(query, site, session_id)   │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
          │
          │ MCP Client
          ▼
  SiteCrawler Agent MCP Server
```

---

## 19. How the Recommendation Agent Uses the Crawler

```python
# On startup — build local index
products = crawler_mcp.get_products(site="sepantadp", limit=1000)
chroma.add_products(products, collection="sepantadp")

# Every hour — sync changes only (cheap)
changes = crawler_mcp.get_changes(
    site="sepantadp",
    since=last_sync_timestamp
)
chroma.add_products(changes.new_products, collection="sepantadp")
chroma.update_products(changes.updated_products, collection="sepantadp")
chroma.delete_products(changes.deleted_products, collection="sepantadp")

# On customer query — use local index (fast, no MCP call)
results = chroma.query(
    query_embeddings=[embed(farsi_query)],
    collection="sepantadp",
    where={"price": {"$lte": budget}, "availability": True}
)
```

The Recommendation Agent never directly queries the crawler's SQLite.
It only uses the MCP interface. This is the clean separation.

---

## 20. Session Memory and Convergence Tracking

```python
# Every session is tracked
session = {
    "session_id": "uuid",
    "site": "sepantadp",
    "turns": [
        {
            "turn": 1,
            "user_message": "دنبال لپ تاپ برای برنامه نویسی هستم",
            "agent_response": [...products...],
            "is_correction": False,
            "tools_called": ["semantic_search", "filter_products"],
            "timestamp": "..."
        },
        {
            "turn": 2,
            "user_message": "نه، منظورم لپ تاپ سبک تر بود",
            "agent_response": [...products...],
            "is_correction": True,   # ← labeled failure
            "correction_text": "نه، منظورم ... بود",
            "timestamp": "..."
        }
    ],
    "converged": False,   # True when user says yes/selects product
    "turns_to_converge": None
}
```

Corrections (turns where is_correction=True) are clustered weekly:

```python
# Failure analysis pipeline
corrections = db.get_all_corrections()
embeddings = embed_model.encode(corrections)
clusters = KMeans(n_clusters=8).fit(embeddings)

# Output: labeled failure modes
# Cluster 0: "agent misunderstands budget (تومان vs ریال)"
# Cluster 3: "agent ignores weight/portability requirements"
# Cluster 6: "agent recommends unavailable products"
```

---

## 21. Recommendation Agent System Prompt

```
You are a Persian-language product recommendation assistant.
Your job is to understand what the customer needs and find
the best matching products from the available catalog.

LANGUAGE: Always respond in Farsi (Persian). The customer
speaks Farsi. Product names may be in English or Farsi — use
both when helpful.

INTENT PARSING: Before searching, extract from the query:
- Explicit needs: stated category, budget, brand preference
- Implicit needs: "for programming" → needs fast CPU, good RAM
                  "for a student" → budget-conscious, portable
                  "as a gift" → focus on presentation/packaging
- Budget: convert any price mention to numeric (IRR)
          "۵ میلیون تومان" → 50,000,000 IRR

SEARCH STRATEGY:
- Always try semantic search first (captures intent)
- Add filter for availability=True unless user asks otherwise
- Add budget filter if mentioned
- If first search returns <3 results: broaden query
- If user says "something lighter/cheaper/better": keep all
  filters from previous turn, add new constraint

RESPONSE FORMAT:
- Lead with brief empathy / understanding
- Show 2-4 products maximum (not a list dump)
- For each: name, price in تومان, why it matches their need
- End with: "آیا این گزینه‌ها مناسب بودن؟" or a follow-up question
- If nothing matches: say so honestly, suggest alternatives

MEMORY ACROSS TURNS:
- Remember: budget, category, stated preferences
- If user says "نه" (no): treat previous response as correction
- Adjust strategy — don't repeat the same results

NEVER:
- Recommend unavailable products
- Invent product details not in the catalog
- Show more than 5 products without asking to narrow down
```

---

## 22. Recommendation Data Flow

```
Customer: "یه لپ تاپ برای برنامه نویسی با بودجه ۵۰ میلیون میخوام"

Step 1 — Intent extraction (agent reasoning):
  explicit: category=laptop, budget=500,000,000 IRR
  implicit: needs good CPU, RAM ≥ 16GB, likely Linux compat

Step 2 — Search planning:
  query_fa: "لپ تاپ برنامه نویسی"
  query_en: "programming laptop developer"
  filters: price <= 500000000, availability = true

Step 3 — Semantic search (ChromaDB):
  embed both queries
  query local ChromaDB collection "sepantadp"
  get top 20 candidates

Step 4 — Filter:
  apply price filter
  apply availability filter
  deduplicate

Step 5 — Rank + reason:
  LLM: "given programming use case + 50M budget,
        rank these by: CPU speed, RAM, value for money"

Step 6 — Respond in Farsi:
  "برای برنامه‌نویسی با بودجه ۵۰ میلیون، این گزینه‌ها رو پیشنهاد میدم:

  ۱. لپ‌تاپ ایسوس VivoBook i7 — ۴۵ میلیون تومان
     رم ۱۶ گیگ، پردازنده i7 نسل ۱۲، مناسب برنامه‌نویسی و چند وظیفگی

  ۲. ..."

Step 7 — Log session turn
  is_correction = False (first turn, no correction yet)
```

---

## 23. Recommendation Tech Stack (All Free)

```
Agent Framework:
  langgraph==0.2.28          # same as crawler (consistency)
  langchain==0.3.7
  langchain-anthropic==0.2.4

LLM for Reasoning + Responses:
  Primary:  Claude claude-sonnet-4-6 (best Farsi, best reasoning)
  Fallback: gpt-4o-mini via OpenRouter

Embedding (Farsi-capable):
  sentence-transformers==3.1.1
  Model: paraphrase-multilingual-MiniLM-L12-v2
  → Free, runs locally, supports Farsi
  → You already use this in your Tax Assistant

Vector Store:
  chromadb==0.5.0            # free, local, no cloud needed
  → One collection per site

Product Cache:
  SQLite (stdlib)            # local copy of crawler data
  sqlalchemy==2.0.36

MCP Client (connect to crawler):
  mcp==1.0.0
  langchain-mcp-adapters==0.1.0

Failure Analysis:
  scikit-learn==1.5.0        # K-Means clustering
  numpy==1.26.4

Chat UI:
  streamlit==1.39.0          # free, fast to build, runs locally

Scheduling (sync jobs):
  apscheduler==3.10.4

Logging:
  loguru==0.7.2

Testing:
  pytest==8.3.3
  pytest-asyncio==0.24.0

Why these choices:
  paraphrase-multilingual-MiniLM-L12-v2:
    → You already use it in Tax Assistant — zero learning curve
    → Handles Farsi natively — no translation step needed
    → Free, runs locally — no API cost for embeddings

  ChromaDB:
    → Same as Tax Assistant — zero learning curve
    → Local, fast, free

  Streamlit over FastAPI+React:
    → v1.0 is for demo and validation
    → FastAPI backend added in v2.0 when deploying for real clients
```

---

## 24. Recommendation Folder Structure

```
recommendation-agent/       ← Separate repo, separately deployable
│
├── SPEC.md
├── ARCHITECTURE.md
├── README.md
│
├── config/
│   ├── config.yaml         ← LLM, embedding model, crawler MCP URL
│   └── sites/
│       └── sepantadp.yaml  ← per-site config: language, currency
│
├── src/
│   ├── agent/
│   │   ├── recommend_agent.py  ← LangGraph ReAct agent
│   │   ├── prompts.py          ← system prompt (Farsi)
│   │   ├── intent.py           ← Farsi intent parser
│   │   └── state.py            ← agent state
│   │
│   ├── tools/
│   │   ├── search.py           ← semantic_search (ChromaDB)
│   │   ├── filter.py           ← filter_products (metadata)
│   │   ├── details.py          ← get_product_details
│   │   └── crawler_sync.py     ← MCP client tools
│   │
│   ├── index/
│   │   ├── embedder.py         ← paraphrase-multilingual embed
│   │   ├── store.py            ← ChromaDB operations
│   │   └── sync.py             ← hourly sync from crawler MCP
│   │
│   ├── memory/
│   │   ├── session.py          ← conversation history per session
│   │   └── tracker.py          ← correction detection + logging
│   │
│   ├── analysis/
│   │   └── clustering.py       ← K-Means failure mode clustering
│   │
│   ├── chat/
│   │   └── ui.py               ← Streamlit chat interface
│   │
│   └── mcp/
│       └── server.py           ← expose recommendations as MCP
│
├── tests/
│   ├── unit/
│   │   ├── test_intent.py
│   │   ├── test_search.py
│   │   └── test_session.py
│   ├── integration/
│   │   └── test_full_conversation.py
│   └── evals/
│       └── recommendation_cases.yaml
│
├── analysis/
│   └── failure_clusters.json   ← output of weekly clustering
│
├── .claude/
│   ├── CLAUDE.md
│   └── plan/
│       ├── phase1_index.md
│       ├── phase2_agent.md
│       ├── phase3_chat.md
│       └── phase4_eval.md
│
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

## 25. Recommendation Success Criteria

```
Intent Understanding:
  □ Correctly identifies budget from Farsi: 95% of test cases
  □ Correctly identifies category: 97% of test cases
  □ Extracts implicit needs (programming → RAM/CPU): 85%

Search Quality:
  □ Returns availability=True products only
  □ Returns products within stated budget
  □ Top result matches intent: 80% of eval cases
  □ Latency: response in < 4 seconds

Session Quality:
  □ Remembers budget across turns
  □ Detects correction ("نه، منظورم...") correctly: 95%
  □ Does not repeat same results after correction

Failure Analysis:
  □ Corrections logged with session_id and turn number
  □ Weekly cluster job runs successfully
  □ Cluster labels visible in analysis/failure_clusters.json
```

---

## 26. Eval Cases (Written Before Coding)

```yaml
# tests/evals/recommendation_cases.yaml

cases:
  - id: budget_explicit
    input: "لپ تاپ زیر ۵۰ میلیون تومان میخوام"
    expected_tool: filter_products
    expected_filters:
      max_price: 500000000
      availability: true
    must_not_contain: "ناموجود"

  - id: implicit_use_case
    input: "لپ تاپ برای برنامه نویسی"
    expected_tool: semantic_search
    expected_query_contains: ["لپ تاپ", "برنامه نویسی"]
    expected_reasoning_contains: ["رم", "پردازنده"]

  - id: correction_handling
    input_turn_1: "گوشی اندروید میخوام"
    response_turn_1: [...products...]
    input_turn_2: "نه، منظورم گوشی با دوربین خوب بود"
    expected: is_correction=True, new search includes camera

  - id: nothing_found
    input: "لپ تاپ گیمینگ ۱۰ میلیون تومانی"   # unrealistic budget
    expected: honest response that no match found
    must_not_contain: fictitious product data

  - id: farsi_response
    input: "چه تبلتی پیشنهاد میدی؟"
    expected_language: fa
    must_contain_farsi: true
```

---

## 27. Multi-Agent Communication Contract

This is the formal contract between the two products.
Any change to this contract requires updating both agents.

```yaml
# MCP Contract v1.0
# SiteCrawler → Recommendation Agent

protocol: MCP 2024-11-05
transport: stdio (local) OR http (remote)

tools_consumed_by_recommendation_agent:
  - name: get_products
    called_when: initial index build or full refresh
    max_calls_per_day: 5 (expensive)

  - name: get_changes
    called_when: hourly sync
    expected_latency_ms: < 500

  - name: get_crawl_status
    called_when: health check on startup
    expected_latency_ms: < 100

  - name: subscribe_changes
    called_when: startup (register webhook for real-time updates)
    called_once: true

data_format:
  price: numeric (float), always in IRR
  availability: boolean
  category: JSON array of strings in Farsi or English
  specs: JSON object, keys in English, values may be Farsi

versioning:
  breaking_changes: bump contract version, notify both agents
  additive_changes: new optional fields, backward compatible
```

---

## 28. Build Order (Both Products)

```
MONTH 1 — SiteCrawler Core
  Week 1:
    □ SQLite schema + SQLAlchemy models
    □ recon.py (robots.txt + platform detection)
    □ discovery.py (sitemap parser)
    □ fetcher.py (requests, no Playwright yet)
    □ TEST: discover all product URLs on sepantadp.com

  Week 2:
    □ extractor.py (LLM extraction)
    □ differ.py (change detection)
    □ store.py (write to SQLite)
    □ EVAL: extraction accuracy on 50 sepantadp + 50 parsazh pages

  Week 3:
    □ fetcher.py Playwright extension (digikala support)
    □ crawler_agent.py (LangGraph ReAct)
    □ TEST: agent handles sitemap failure gracefully
    □ TEST: agent switches to Playwright on JS-rendered page

  Week 4:
    □ scheduler/jobs.py (3 APScheduler jobs)
    □ webhooks/notifier.py
    □ mcp/server.py (5 public tools)
    □ TEST: MCP tools/list returns correct schemas
    □ Docker + README

MONTH 2 — Recommendation Agent
  Week 5:
    □ ChromaDB setup + paraphrase-multilingual embedder
    □ crawler_sync.py (MCP client connecting to crawler)
    □ index/sync.py (hourly sync from crawler)
    □ TEST: products indexed correctly from sepantadp

  Week 6:
    □ search.py + filter.py tools
    □ intent.py (Farsi intent parser)
    □ recommend_agent.py (LangGraph ReAct)
    □ EVAL: 10 test queries, correct tool called each time

  Week 7:
    □ session.py + tracker.py (memory + correction logging)
    □ chat/ui.py (Streamlit interface)
    □ TEST: session memory across 5-turn conversation

  Week 8:
    □ analysis/clustering.py (K-Means failure analysis)
    □ mcp/server.py (expose recommendations as MCP)
    □ End-to-end test: full customer conversation
    □ Docker + README
    □ DEMO: sepantadp + parsazh working end-to-end
```

---

## 29. How to Sell Each Product

### SiteCrawler Agent — Pitch

```
"Give me any Iranian e-commerce site URL.
 Within 2 hours I give you:
 - All their products, structured, in JSON
 - Live price monitoring — updates within 1 hour
 - Webhook alerts when prices change
 - A standardized API any system can connect to
 
 No database access needed. No custom code per site.
 Add a new site by filling one YAML file."
```

Target buyers: price comparison sites, dropshippers,
competitor intelligence tools, ERP systems, any business
needing external product data.

### Recommendation Agent — Pitch

```
"Your customers describe what they need in Farsi.
 My agent understands them — budget, use case, preferences —
 and shows them the right products with reasoning.
 
 Integrates with any product data source via MCP.
 Works out of the box with SiteCrawler Agent.
 Chat interface ready in days, not months."
```

Target buyers: e-commerce sites wanting AI customer service,
B2B product catalogs with complex selection criteria,
any business with Iranian customers.

### Bundle Pitch

```
"Complete AI product intelligence platform:
 Crawler monitors your competitors' prices 24/7.
 Recommendation engine helps your customers find products.
 Both connect via industry-standard MCP protocol.
 Each upgradeable independently."
```

---

## 30. Decisions Log

| Decision | Alternatives | Chosen | Reason |
|----------|-------------|--------|--------|
| Agent framework | LangChain, AutoGen, CrewAI | LangGraph | State machines + conditional edges for strategy switching |
| JS rendering | Selenium, Splash, paid services | Playwright | Free bundled Chromium, better async, modern API |
| Crawler DB | PostgreSQL, MongoDB | SQLite | Zero infra, client deploys anywhere, no credentials |
| Recommendation DB | Pinecone, Weaviate | ChromaDB | Free, local, already in Tax Assistant stack |
| Embedding model | OpenAI ada, Cohere | paraphrase-multilingual-MiniLM-L12-v2 | Free, local, Farsi-native, already in Tax Assistant |
| Chat UI | FastAPI+React, Gradio | Streamlit | Fast to build for v1, switch to FastAPI in v2 |
| Inter-agent protocol | REST API, gRPC, message queue | MCP | Standard protocol, agent discovers tools automatically |
| Scheduling | Celery+Redis, Dramatiq | APScheduler | No Redis dependency, lightweight |
| Logging | Python logging, structlog | loguru | Cleaner API, structured output, free |
