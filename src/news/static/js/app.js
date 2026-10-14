// Enterprise News Intelligence - Frontend Client Logic

let currentReport = null;
let activeTab = 'all'; // 'all', 'worldwide', 'india'
let searchQuery = '';

// DOM Elements
const elLiveClock = document.getElementById('live-clock');
const elRefreshBtn = document.getElementById('btn-refresh');
const elReportDate = document.getElementById('kpi-date');
const elModelUsed = document.getElementById('kpi-model');
const elLatency = document.getElementById('kpi-latency');
const elFallbackBadge = document.getElementById('kpi-fallback');
const elWorldContainer = document.getElementById('world-news-container');
const elIndiaContainer = document.getElementById('india-news-container');
const elWorldSection = document.getElementById('section-worldwide');
const elIndiaSection = document.getElementById('section-india');
const elSearchInput = document.getElementById('search-input');
const tabButtons = document.querySelectorAll('.tab-btn');
const elTelemetryModel = document.getElementById('telemetry-model');
const elTelemetryTime = document.getElementById('telemetry-time');

// Initialize live UTC clock
function updateClock() {
  const now = new Date();
  const utcString = now.toUTCString().replace('GMT', 'UTC');
  if (elLiveClock) {
    elLiveClock.textContent = utcString;
  }
}
setInterval(updateClock, 1000);
updateClock();

// Calculate relative time string from ISO / published date
function getRelativeTimeString(dateString) {
  if (!dateString) return 'Recent';
  try {
    const pubDate = new Date(dateString);
    if (isNaN(pubDate.getTime())) return dateString;
    const now = new Date();
    const diffMs = now - pubDate;
    const diffMins = Math.max(1, Math.round(diffMs / 60000));

    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.round(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.round(diffHours / 24)}d ago`;
  } catch {
    return dateString;
  }
}

// Render skeleton shimmer cards
function renderSkeletons() {
  const skeletonHtml = Array(3).fill(0).map(() => `
    <div class="skeleton-card">
      <div class="skeleton-line skeleton-meta"></div>
      <div class="skeleton-line skeleton-title"></div>
      <div class="skeleton-line" style="width: 100%"></div>
      <div class="skeleton-line" style="width: 90%"></div>
      <div class="skeleton-line skeleton-box"></div>
    </div>
  `).join('');

  if (elWorldContainer) elWorldContainer.innerHTML = skeletonHtml;
  if (elIndiaContainer) elIndiaContainer.innerHTML = skeletonHtml;
}

// Render a single article card
function renderArticleCard(article, index) {
  const isIndia = article.region === 'INDIA';
  const badgeClass = isIndia ? 'badge-india' : 'badge-world';
  const regionLabel = isIndia ? '🇮🇳 India' : '🌍 Worldwide';
  const relTime = getRelativeTimeString(article.published_at);

  const keyPointsHtml = (article.key_points && article.key_points.length > 0) ? `
    <div class="highlights-box">
      <div class="highlights-title">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
        Key Intelligence Takeaways
      </div>
      <ul class="highlights-list">
        ${article.key_points.map(pt => `<li>${escapeHtml(pt)}</li>`).join('')}
      </ul>
    </div>
  ` : '';

  return `
    <article class="article-card" data-title="${escapeHtml(article.title.toLowerCase())}" data-category="${escapeHtml(article.category.toLowerCase())}">
      <div class="card-meta-row">
        <div class="meta-tags">
          <span class="title-badge ${badgeClass}">${regionLabel}</span>
          <span class="tag-category">${escapeHtml(article.category || 'General')}</span>
        </div>
        <div class="tag-time">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          ${relTime}
        </div>
      </div>

      <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer" class="card-title">
        ${escapeHtml(article.title)}
      </a>

      <p class="card-summary">${escapeHtml(article.summary)}</p>

      ${keyPointsHtml}

      <div class="card-footer">
        <span class="tag-source">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"></path></svg>
          ${escapeHtml(article.source)}
        </span>
        <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer" class="btn-read">
          Original Source
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        </a>
      </div>
    </article>
  `;
}

// Filter and render articles into columns
function applyFiltersAndRender() {
  if (!currentReport) return;

  const filterItem = (article) => {
    if (!searchQuery) return true;
    const text = `${article.title} ${article.summary} ${article.source} ${article.category}`.toLowerCase();
    return text.includes(searchQuery);
  };

  const filteredWorld = (currentReport.worldwide_news || []).filter(filterItem);
  const filteredIndia = (currentReport.india_news || []).filter(filterItem);

  // Tab visibility
  if (activeTab === 'worldwide') {
    elWorldSection.style.display = 'block';
    elIndiaSection.style.display = 'none';
  } else if (activeTab === 'india') {
    elWorldSection.style.display = 'none';
    elIndiaSection.style.display = 'block';
  } else {
    elWorldSection.style.display = 'block';
    elIndiaSection.style.display = 'block';
  }

  // Render cards or empty states
  if (filteredWorld.length === 0) {
    elWorldContainer.innerHTML = `<div class="article-card" style="text-align: center; color: var(--text-muted);">No matching worldwide stories found.</div>`;
  } else {
    elWorldContainer.innerHTML = filteredWorld.map((a, i) => renderArticleCard(a, i)).join('');
  }

  if (filteredIndia.length === 0) {
    elIndiaContainer.innerHTML = `<div class="article-card" style="text-align: center; color: var(--text-muted);">No matching India stories found.</div>`;
  } else {
    elIndiaContainer.innerHTML = filteredIndia.map((a, i) => renderArticleCard(a, i)).join('');
  }
}

// Fetch news report from FastAPI backend
async function fetchNewsReport() {
  if (elRefreshBtn) {
    elRefreshBtn.classList.add('loading');
    elRefreshBtn.disabled = true;
  }
  renderSkeletons();

  try {
    const response = await fetch('/api/v1/news/top');
    if (!response.ok) {
      throw new Error(`API error HTTP ${response.status}`);
    }
    const data = await response.json();
    currentReport = data;

    // Update KPI values
    if (elReportDate) elReportDate.textContent = data.report_date;
    if (elModelUsed) elModelUsed.textContent = data.llm_provider_used;
    if (elLatency) elLatency.textContent = `${data.execution_time_seconds || 24}s`;
    if (elFallbackBadge) {
      elFallbackBadge.textContent = data.fallback_occurred ? 'Groq Failover Active' : 'Primary Gemini Active';
      elFallbackBadge.style.color = data.fallback_occurred ? '#fbbf24' : '#34d399';
    }

    if (elTelemetryModel) elTelemetryModel.textContent = data.llm_provider_used;
    if (elTelemetryTime) elTelemetryTime.textContent = data.generated_at;

    applyFiltersAndRender();
  } catch (error) {
    console.error('Error fetching news intelligence:', error);
    if (elWorldContainer) {
      elWorldContainer.innerHTML = `
        <div class="article-card" style="border-color: rgba(244, 63, 94, 0.4);">
          <strong style="color: #f43f5e;">Failed to load live news report</strong>
          <p style="font-size: 13px; color: var(--text-secondary); margin-top: 6px;">
            ${escapeHtml(error.message)}. Please check server status or terminal output.
          </p>
        </div>
      `;
    }
  } finally {
    if (elRefreshBtn) {
      elRefreshBtn.classList.remove('loading');
      elRefreshBtn.disabled = false;
    }
  }
}

// Helper: Escape HTML to avoid injection
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Event Listeners
if (elRefreshBtn) {
  elRefreshBtn.addEventListener('click', fetchNewsReport);
}

if (elSearchInput) {
  elSearchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    applyFiltersAndRender();
  });
}

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tabButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeTab = btn.getAttribute('data-tab');
    applyFiltersAndRender();
  });
});

// Load immediately on page open
document.addEventListener('DOMContentLoaded', () => {
  fetchNewsReport();
});
