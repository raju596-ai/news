/**
 * NewsIntel // Client Application Logic
 * Autonomous AI News Video Generation System
 */

(() => {
  // Determine API base dynamically
  const API_BASE = window.location.origin;

  // Application State
  const state = {
    isRunning: false,
    activePhase: 'IDLE',
    overallProgress: 0,
    worldStories: [],
    indiaStories: [],
    activeTab: 'all',
    activeStoryForModal: null,
    activeYoutubeMetadata: null,
    eventSource: null,
  };

  // DOM Elements
  const el = {
    startBtn: document.getElementById('start-pipeline-btn'),
    startBtnText: document.getElementById('start-btn-text'),
    realGenBtn: document.getElementById('start-real-gen-btn'),
    realGenBtnText: document.getElementById('real-gen-btn-text'),
    refreshBtn: document.getElementById('refresh-status-btn'),
    systemStatusText: document.getElementById('system-status-text'),
    systemStatusPill: document.getElementById('system-status-pill'),
    utcClock: document.getElementById('utc-clock'),

    // Slides Modal
    slidesModal: document.getElementById('slides-modal'),
    slidesModalTitle: document.getElementById('slides-modal-title'),
    slidesModalCloseBtn: document.getElementById('slides-modal-close-btn'),
    slidesGridContainer: document.getElementById('slides-grid-container'),

    // Telemetry & Progress
    activeStageLabel: document.getElementById('active-stage-label'),
    overallProgressFill: document.getElementById('overall-progress-fill'),
    overallProgressText: document.getElementById('overall-progress-text'),
    pipelineStatusDetail: document.getElementById('pipeline-status-detail'),
    consoleLogOutput: document.getElementById('console-log-output'),
    consoleClearBtn: document.getElementById('console-clear-btn'),

    // Nodes
    nodeOrchestrator: document.getElementById('node-orchestrator'),
    nodeCollector: document.getElementById('node-collector'),
    nodeScriptImage: document.getElementById('node-script-image'),
    nodeImageToVideo: document.getElementById('node-image-to-video'),
    nodeVoice: document.getElementById('node-voice'),
    nodeAssembly: document.getElementById('node-assembly'),
    nodeQC: document.getElementById('node-qc'),


    // Story Grids
    worldBlock: document.getElementById('world-news-block'),
    indiaBlock: document.getElementById('india-news-block'),
    worldGrid: document.getElementById('world-stories-grid'),
    indiaGrid: document.getElementById('india-stories-grid'),
    badgeAll: document.getElementById('badge-all'),
    badgeWorld: document.getElementById('badge-world'),
    badgeIndia: document.getElementById('badge-india'),
    navTabs: document.querySelectorAll('.nav-tab'),

    // Video Modal
    videoModal: document.getElementById('video-modal'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    modalVideoPlayer: document.getElementById('modal-video-player'),
    modalVideoTitle: document.getElementById('modal-video-title'),
    modalRegionBadge: document.getElementById('modal-region-badge'),
    modalQCPill: document.getElementById('modal-qc-pill'),
    modalDuration: document.getElementById('modal-duration'),
    modalSource: document.getElementById('modal-source'),
    modalDownloadBtn: document.getElementById('modal-download-btn'),
    drawerToggleBtn: document.getElementById('drawer-toggle-btn'),
    drawerScriptContent: document.getElementById('drawer-script-content'),

    // YouTube Upload Details Modal
    ytDetailsModal: document.getElementById('youtube-details-modal'),
    ytDetailsCloseBtn: document.getElementById('yt-details-close-btn'),
    ytModalTitle: document.getElementById('yt-modal-title'),
    ytFileBlock: document.getElementById('yt-file-block'),
    btnCopyFile: document.getElementById('btn-copy-file'),
    btnDownloadMetaFile: document.getElementById('btn-download-meta-file'),
    ytJsonBlock: document.getElementById('yt-json-block'),
    btnCopyJson: document.getElementById('btn-copy-json'),
    ytInputTitle: document.getElementById('yt-input-title'),
    ytTextareaDesc: document.getElementById('yt-textarea-desc'),
    ytInputTags: document.getElementById('yt-input-tags'),
    ytTagsCount: document.getElementById('yt-tags-count'),
    ytTagChips: document.getElementById('yt-tag-chips'),
    ytMetaKids: document.getElementById('yt-meta-kids'),
    ytMetaCategory: document.getElementById('yt-meta-category'),
    ytMetaVisibility: document.getElementById('yt-meta-visibility'),
    ytMetaSchedDate: document.getElementById('yt-meta-sched-date'),
    ytMetaSchedTime: document.getElementById('yt-meta-sched-time'),
    btnCopySchedDate: document.getElementById('btn-copy-sched-date'),
    btnCopySchedTime: document.getElementById('btn-copy-sched-time'),
    ytMetaLanguage: document.getElementById('yt-meta-language'),
    btnCopyAll: document.getElementById('btn-copy-all'),
    btnCopyLang: document.getElementById('btn-copy-lang'),
    btnUploadYtModal: document.getElementById('btn-upload-yt-modal'),
    btnUploadFbModal: document.getElementById('btn-upload-fb-modal'),
    btnUploadIgModal: document.getElementById('btn-upload-ig-modal'),

    // Config Dropdowns
    configModelSelect: document.getElementById('config-model-select'),
    configLangSelect: document.getElementById('config-lang-select'),
    configFormatSelect: document.getElementById('config-format-select'),

    // A/B Thumbnails Modal
    thumbnailsModal: document.getElementById('thumbnails-modal'),
    thumbnailsModalCloseBtn: document.getElementById('thumbnails-modal-close-btn'),
    thumbnailsModalTitle: document.getElementById('thumbnails-modal-title'),
    thumbAImg: document.getElementById('thumb-a-img'),
    thumbADownload: document.getElementById('thumb-a-download'),
    thumbBImg: document.getElementById('thumb-b-img'),
    thumbBDownload: document.getElementById('thumb-b-download'),

    // 9:16 Vertical Video Modal
    verticalModal: document.getElementById('vertical-modal'),
    verticalModalCloseBtn: document.getElementById('vertical-modal-close-btn'),
    verticalModalTitle: document.getElementById('vertical-modal-title'),
    verticalVideoPlayer: document.getElementById('vertical-video-player'),
    verticalDownloadBtn: document.getElementById('vertical-download-btn'),

    // Community Post Modal
    communityModal: document.getElementById('community-modal'),
    communityModalCloseBtn: document.getElementById('community-modal-close-btn'),
    communityModalTitle: document.getElementById('community-modal-title'),
    communityPostText: document.getElementById('community-post-text'),
    copyCommunityPostBtn: document.getElementById('copy-community-post-btn'),
    pinnedCommentText: document.getElementById('pinned-comment-text'),
    copyPinnedCommentBtn: document.getElementById('copy-pinned-comment-btn'),
  };

  // ============================================================================
  // Initialization & Clock
  // ============================================================================

  function init() {
    startUtcClock();
    setupEventListeners();
    connectSSE();
    fetchCurrentStatus();
    loadConfigOptions();
  }

  function startUtcClock() {
    function updateClock() {
      const now = new Date();
      if (el.utcClock) {
        el.utcClock.textContent = now.toUTCString().split(' ')[4] + ' UTC';
      }
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  // ============================================================================
  // Server-Sent Events (SSE) Stream
  // ============================================================================

  function connectSSE() {
    if (state.eventSource) {
      state.eventSource.close();
    }

    try {
      state.eventSource = new EventSource(`${API_BASE}/api/v1/workflow/stream`);

      state.eventSource.onopen = () => {
        appendLog('[NET] Connected to real-time agent telemetry stream', 'log-system');
      };

      state.eventSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          handlePipelineEvent(data);
        } catch (err) {
          // heartbeat or unparseable
        }
      };

      state.eventSource.onerror = () => {
        setTimeout(connectSSE, 5000);
      };
    } catch (e) {
      console.warn('SSE connection failed:', e);
    }
  }

  function handlePipelineEvent(event) {
    if (event.stage) {
      state.activePhase = event.stage;
      if (el.activeStageLabel) el.activeStageLabel.textContent = event.stage;
      highlightActiveNode(event.stage);
    }

    if (typeof event.progress === 'number' && event.progress > 0) {
      updateProgress(event.progress);
    }

    if (event.message) {
      if (el.pipelineStatusDetail) el.pipelineStatusDetail.textContent = event.message;
      appendLog(`[${event.stage || 'AGENT'}] ${event.message}`);
    }

    // Refresh state when major milestones occur
    if (event.stage === 'NEWS_COLLECTION' || event.stage === 'VIDEO_ASSEMBLY' || event.stage === 'QUALITY_CONTROL' || event.stage === 'COMPLETED') {
      fetchCurrentStatus();
    }
  }

  function appendLog(text, className = '') {
    if (!el.consoleLogOutput) return;
    const line = document.createElement('div');
    line.className = `log-line ${className}`;
    const timestamp = new Date().toISOString().substring(11, 19);
    line.textContent = `[${timestamp}] ${text}`;
    el.consoleLogOutput.appendChild(line);
    el.consoleLogOutput.scrollTop = el.consoleLogOutput.scrollHeight;
  }

  function highlightActiveNode(stage) {
    const nodes = [
      el.nodeOrchestrator,
      el.nodeCollector,
      el.nodeScriptImage,
      el.nodeImageToVideo,
      el.nodeVoice,
      el.nodeAssembly,
      el.nodeQC,
    ];
    nodes.forEach((n) => {
      if (n) n.classList.remove('active');
    });

    if (stage === 'ORCHESTRATOR' && el.nodeOrchestrator) el.nodeOrchestrator.classList.add('active');
    else if (stage === 'NEWS_COLLECTION' && el.nodeCollector) el.nodeCollector.classList.add('active');
    else if ((stage === 'SCRIPT_GENERATION' || stage === 'IMAGE_RESEARCH') && el.nodeScriptImage) el.nodeScriptImage.classList.add('active');
    else if (stage === 'IMAGE_TO_VIDEO' && el.nodeImageToVideo) el.nodeImageToVideo.classList.add('active');
    else if (stage === 'VOICE_GENERATION' && el.nodeVoice) el.nodeVoice.classList.add('active');
    else if (stage === 'VIDEO_ASSEMBLY' && el.nodeAssembly) el.nodeAssembly.classList.add('active');
    else if (stage === 'QUALITY_CONTROL' && el.nodeQC) el.nodeQC.classList.add('active');
  }


  function updateProgress(pct) {
    state.overallProgress = pct;
    if (el.overallProgressFill) el.overallProgressFill.style.width = `${pct}%`;
    if (el.overallProgressText) el.overallProgressText.textContent = `${pct}%`;
  }

  // ============================================================================
  // API Calls & Actions
  // ============================================================================

  async function fetchCurrentStatus() {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/workflow/status`);
      if (!resp.ok) return;
      const data = await resp.json();

      state.isRunning = data.is_running;
      state.worldStories = data.world_stories || [];
      state.indiaStories = data.india_stories || [];
      state.overallProgress = data.overall_progress || 0;

      updateProgress(state.overallProgress);
      if (el.activeStageLabel) el.activeStageLabel.textContent = data.active_phase || 'IDLE';

      if (state.isRunning) {
        if (el.startBtn) el.startBtn.disabled = true;
        if (el.startBtnText) el.startBtnText.textContent = 'Pipeline Running...';
        if (el.systemStatusText) el.systemStatusText.textContent = 'Generating Videos';
      } else {
        if (el.startBtn) el.startBtn.disabled = false;
        if (el.startBtnText) el.startBtnText.textContent = 'Start AI Video Workflow';
        if (el.systemStatusText) el.systemStatusText.textContent = 'Network Ready';
      }

      renderStories();
    } catch (e) {
      console.error('Failed to fetch status:', e);
    }
  }

  async function startWorkflow() {
    try {
      if (el.startBtn) el.startBtn.disabled = true;
      if (el.startBtnText) el.startBtnText.textContent = 'Initiating Agents...';
      appendLog('[ORCHESTRATOR] 1-Click trigger received. Launching workflow...', 'log-system');

      const resp = await fetch(`${API_BASE}/api/v1/workflow/start?auto_render=true`, {
        method: 'POST',
      });
      const data = await resp.json();
      appendLog(`[ORCHESTRATOR] ${data.message}`, 'log-system');
      fetchCurrentStatus();
    } catch (e) {
      appendLog(`[ERROR] Failed to start workflow: ${e.message}`);
      if (el.startBtn) el.startBtn.disabled = false;
      if (el.startBtnText) el.startBtnText.textContent = 'Start Pipeline';
    }
  }

  async function startRealGenerationWorkflow() {
    try {
      if (el.realGenBtn) el.realGenBtn.disabled = true;
      if (el.realGenBtnText) el.realGenBtnText.textContent = 'Generating with NVIDIA AI...';
      appendLog('[ORCHESTRATOR] 🎬 Real Broadcast Generation initiated with NVIDIA FLUX.2-klein-4b & Llama 3.2 Vision verification...', 'log-system');

      const resp = await fetch(`${API_BASE}/api/v1/workflow/real-generation?auto_render=true`, {
        method: 'POST',
      });
      const data = await resp.json();
      appendLog(`[ORCHESTRATOR] ${data.message || 'Real generation initiated'}`, 'log-system');
      fetchCurrentStatus();
    } catch (e) {
      appendLog(`[ERROR] Failed to start real generation: ${e.message}`);
      if (el.realGenBtn) el.realGenBtn.disabled = false;
      if (el.realGenBtnText) el.realGenBtnText.textContent = 'Real Broadcast Generation';
    }
  }

  async function generateSingleStory(storyId) {
    try {
      appendLog(`[TRIGGER] On-demand video generation requested for story ${storyId}...`);
      const resp = await fetch(`${API_BASE}/api/v1/story/${storyId}/generate`, {
        method: 'POST',
      });
      if (resp.ok) {
        appendLog(`[AGENT] Rendering initiated for story ${storyId}`);
        fetchCurrentStatus();
      }
    } catch (e) {
      appendLog(`[ERROR] Failed to trigger render for ${storyId}: ${e.message}`);
    }
  }

  async function loadConfigOptions() {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/config/options`);
      if (resp.ok) {
        const data = await resp.json();
        if (el.configModelSelect && data.current_model) el.configModelSelect.value = data.current_model;
        if (el.configLangSelect && data.current_language) el.configLangSelect.value = data.current_language;
        if (el.configFormatSelect && data.current_format) el.configFormatSelect.value = data.current_format;
      }
    } catch (e) {
      console.warn('Failed to load config options:', e);
    }
  }

  async function updateConfig() {
    try {
      const payload = {
        model_name: el.configModelSelect ? el.configModelSelect.value : undefined,
        language: el.configLangSelect ? el.configLangSelect.value : undefined,
        aspect_ratio: el.configFormatSelect ? el.configFormatSelect.value : undefined,
      };
      const resp = await fetch(`${API_BASE}/api/v1/config/set`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (resp.ok) {
        const res = await resp.json();
        appendLog(`[CONFIG] Settings updated: Model=${res.current_model?.split('/').pop()}, Lang=${res.current_language}, Format=${res.current_format}`, 'log-system');
      }
    } catch (e) {
      appendLog(`[CONFIG ERROR] Failed to update settings: ${e.message}`, 'log-system');
    }
  }

  // ============================================================================
  // UI Rendering
  // ============================================================================

  function renderStories() {
    // Update badge counts
    if (el.badgeAll) el.badgeAll.textContent = state.worldStories.length + state.indiaStories.length;
    if (el.badgeWorld) el.badgeWorld.textContent = state.worldStories.length;
    if (el.badgeIndia) el.badgeIndia.textContent = state.indiaStories.length;

    // Render World News Grid
    renderGrid(el.worldGrid, state.worldStories, 'WORLDWIDE');

    // Render India News Grid
    renderGrid(el.indiaGrid, state.indiaStories, 'INDIA');
  }

  function renderGrid(container, stories, regionType) {
    if (!container) return;
    if (!stories || stories.length === 0) {
      container.innerHTML = `<div class="empty-state">No ${regionType === 'INDIA' ? 'India' : 'World'} stories available. Click "Start AI Video Workflow".</div>`;
      return;
    }

    container.innerHTML = '';
    stories.forEach((story) => {
      const card = createStoryCard(story);
      container.appendChild(card);
    });
  }

  function createStoryCard(story) {
    const card = document.createElement('div');
    card.className = 'story-card';

    const hasVideo = story.media && story.media.video_path;
    const isCompleted = story.status === 'COMPLETED' || hasVideo;
    const firstImage = (story.media && story.media.image_paths && story.media.image_paths.length > 0)
      ? story.media.image_paths[0].replace(/\\/g, '/')
      : null;

    // Build thumbnail url
    let thumbUrl = '';
    if (firstImage) {
      // Map absolute media path to /media URL
      const mediaIdx = firstImage.indexOf('/storage/media/');
      if (mediaIdx !== -1) {
        thumbUrl = `${API_BASE}${firstImage.substring(mediaIdx + 9)}`;
      } else {
        thumbUrl = `${API_BASE}/media/${story.id}/images/slide_0_hook.jpg`;
      }
    }

    const rankText = `#${story.rank || 1}`;
    const qcBadgeHtml = isCompleted
      ? `<div class="card-qc-badge"><span>✓</span> QC PASSED</div>`
      : `<div class="card-qc-badge" style="background: rgba(245, 158, 11, 0.9);"><span>●</span> ${story.status_message || 'Processing'}</div>`;

    const cleanTitle = (story.title || story.id)
      .replace(/[^a-zA-Z0-9\s_-]/g, '')
      .trim()
      .replace(/\s+/g, '_')
      .substring(0, 60);
    const baseName = cleanTitle || `news_${story.id}`;
    const videoFileName = `${baseName}.mp4`;
    const metaFileName = `${baseName}.txt`;

    const actionsHtml = hasVideo
      ? `
        <button class="btn-preview" data-id="${story.id}">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="6 4 18 12 6 20 6 4"></polygon></svg>
          <span>Preview</span>
        </button>
        <a class="btn-download" href="${API_BASE}/api/v1/videos/${story.id}/download" download="${videoFileName}" title="Download ${videoFileName}">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          <span>Download MP4</span>
        </a>
        <button class="btn-vertical-video" data-id="${story.id}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.4);border-radius:6px;color:#34d399;font-size:0.75rem;font-weight:600;cursor:pointer;" title="Preview & Download 9:16 Vertical Video for YouTube Shorts & Reels">
          <span>📱 9:16 Shorts</span>
        </button>
        <button class="btn-ab-thumbnails" data-id="${story.id}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.4);border-radius:6px;color:#fbbf24;font-size:0.75rem;font-weight:600;cursor:pointer;" title="View high-CTR A/B Thumbnails (Option A & B)">
          <span>🎨 A/B Thumbnails</span>
        </button>
        <button class="btn-community-post" data-id="${story.id}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.4);border-radius:6px;color:#38bdf8;font-size:0.75rem;font-weight:600;cursor:pointer;" title="View YouTube Community Post & Pinned Comment">
          <span>📢 Community</span>
        </button>
        <a class="btn-meta-file" href="${API_BASE}/api/v1/story/${story.id}/metadata-file/download" download="${metaFileName}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.4);border-radius:6px;color:#34d399;font-size:0.75rem;font-weight:600;text-decoration:none;" title="Download ${metaFileName}">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          <span>📄 .txt</span>
        </a>
        <button class="btn-yt-details" data-id="${story.id}">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          <span>📋 YouTube</span>
        </button>
        <button class="btn-upload-yt" data-id="${story.id}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);border-radius:6px;color:#f87171;font-size:0.75rem;font-weight:600;cursor:pointer;" title="Upload directly to YouTube">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
          <span>🚀 YT</span>
        </button>
        <button class="btn-upload-ig" data-id="${story.id}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(225,48,108,0.15);border:1px solid rgba(225,48,108,0.4);border-radius:6px;color:#f472b6;font-size:0.75rem;font-weight:600;cursor:pointer;" title="Upload directly to Instagram">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
          <span>📸 IG</span>
        </button>
        <button class="btn-inspect-slides" data-id="${story.id}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);border-radius:6px;color:#60a5fa;font-size:0.75rem;font-weight:600;cursor:pointer;" title="Inspect generated slides & verified news imagery">
          <span>🖼️ Inspect Slides</span>
        </button>
      `
      : `
        <button class="btn-generate-single" data-id="${story.id}">
          <span>🎬 Generate Video (FFmpeg)</span>
        </button>
        <button class="btn-inspect-slides" data-id="${story.id}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);border-radius:6px;color:#60a5fa;font-size:0.75rem;font-weight:600;cursor:pointer;" title="Inspect generated slides">
          <span>🖼️ Inspect Slides</span>
        </button>
      `;

    card.innerHTML = `
      <div class="card-thumbnail-box">
        ${thumbUrl
          ? `<img class="card-thumbnail-img" src="${thumbUrl}" alt="${story.title}" onerror="this.style.display='none'">`
          : `<div style="display:flex;height:100%;align-items:center;justify-content:center;background:#090e1c;color:#64748b;font-size:0.8rem;">NewsIntel AI Broadcast</div>`
        }
        <div class="card-rank-badge">${rankText}</div>
        ${qcBadgeHtml}
      </div>

      <div class="card-content">
        <div class="card-category-row">
          <span class="card-category-pill">${story.category || 'General'}</span>
          <span class="card-source-tag">${story.source}</span>
          ${story.language && story.language !== 'en' ? `<span style="background:rgba(56,189,248,0.2);color:#38bdf8;font-size:0.7rem;font-weight:700;padding:2px 6px;border-radius:4px;border:1px solid rgba(56,189,248,0.4);">🌐 ${story.language.toUpperCase()}</span>` : ''}
          ${story.sources_clustered && story.sources_clustered.length > 1 ? `<span title="${story.sources_clustered.join(', ')}" style="background:rgba(16,185,129,0.2);color:#34d399;font-size:0.7rem;font-weight:700;padding:2px 6px;border-radius:4px;border:1px solid rgba(16,185,129,0.4);">🔗 ${story.sources_clustered.length} Clustered Sources</span>` : ''}
        </div>

        <h3 class="card-headline">${story.title}</h3>
        <p class="card-hook">${story.script ? story.script.hook : story.summary}</p>

        <div class="card-actions">
          ${actionsHtml}
        </div>
      </div>
    `;

    // Hook preview button
    const previewBtn = card.querySelector('.btn-preview');
    if (previewBtn) {
      previewBtn.addEventListener('click', () => openVideoModal(story));
    }

    // Hook inspect slides button
    const inspectSlidesBtn = card.querySelector('.btn-inspect-slides');
    if (inspectSlidesBtn) {
      inspectSlidesBtn.addEventListener('click', () => openSlidesModal(story));
    }

    // Hook YouTube details button
    const ytDetailsBtn = card.querySelector('.btn-yt-details');
    if (ytDetailsBtn) {
      ytDetailsBtn.addEventListener('click', () => openYouTubeDetailsModal(story));
    }

    // Hook YouTube upload button
    const uploadYtBtn = card.querySelector('.btn-upload-yt');
    if (uploadYtBtn) {
      uploadYtBtn.addEventListener('click', () => uploadStoryToYouTube(story.id, uploadYtBtn, story.rank || 1));
    }

    // Hook Instagram upload button
    const uploadIgBtn = card.querySelector('.btn-upload-ig');
    if (uploadIgBtn) {
      uploadIgBtn.addEventListener('click', () => uploadStoryToInstagram(story.id, uploadIgBtn));
    }

    // Hook A/B Thumbnails button
    const abThumbBtn = card.querySelector('.btn-ab-thumbnails');
    if (abThumbBtn) {
      abThumbBtn.addEventListener('click', () => openThumbnailsModal(story));
    }

    // Hook 9:16 Shorts button
    const verticalBtn = card.querySelector('.btn-vertical-video');
    if (verticalBtn) {
      verticalBtn.addEventListener('click', () => openVerticalVideoModal(story));
    }

    // Hook Community Post button
    const commBtn = card.querySelector('.btn-community-post');
    if (commBtn) {
      commBtn.addEventListener('click', () => openCommunityModal(story));
    }

    // Hook generate button
    const genBtn = card.querySelector('.btn-generate-single');
    if (genBtn) {
      genBtn.addEventListener('click', () => {
        genBtn.disabled = true;
        genBtn.textContent = 'Rendering...';
        generateSingleStory(story.id);
      });
    }

    return card;
  }

  // ============================================================================
  // Video Modal Player
  // ============================================================================

  function openVideoModal(story) {
    state.activeStoryForModal = story;
    if (!el.videoModal) return;

    el.modalVideoTitle.textContent = story.title;
    el.modalRegionBadge.textContent = `${story.region} // RANK #${story.rank}`;
    el.modalSource.textContent = `Source: ${story.source}`;
    el.modalDuration.textContent = story.media.audio_duration_sec
      ? `Duration: ${Math.round(story.media.audio_duration_sec)}s`
      : '--s';

    const cleanTitle = (story.title || story.id)
      .replace(/[^a-zA-Z0-9\s_-]/g, '')
      .trim()
      .replace(/\s+/g, '_')
      .substring(0, 60);
    const baseName = cleanTitle || `news_${story.id}`;
    const videoFileName = `${baseName}.mp4`;

    el.modalDownloadBtn.href = `${API_BASE}/api/v1/videos/${story.id}/download`;
    el.modalDownloadBtn.download = videoFileName;

    // Set video src and load
    el.modalVideoPlayer.src = `${API_BASE}/api/v1/videos/${story.id}/preview`;
    el.modalVideoPlayer.load();
    el.modalVideoPlayer.play().catch(() => {});

    // Render script beats drawer
    // Render 3-minute script sections with timing & word count badges
    if (story.script) {
      const s = story.script;
      const sections = [
        { icon: "🎯", name: "Hook", timing: "10–15 sec", words: "25–35 words", text: s.hook },
        { icon: "📰", name: "What Happened", timing: "30–40 sec", words: "60–75 words", text: s.what_happened },
        { icon: "🔎", name: "Key Details", timing: "60 sec", words: "120–130 words", text: s.key_details },
        { icon: "🌍", name: "Why It Matters", timing: "30–35 sec", words: "60–70 words", text: s.why_it_matters },
        { icon: "📌", name: "Latest Update", timing: "25–30 sec", words: "50–60 words", text: s.latest_update || s.current_status },
        { icon: "🎬", name: "Closing", timing: "10 sec", words: "20–25 words", text: s.closing },
      ];

      el.drawerScriptContent.innerHTML = `
        <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent-cyan); margin-bottom: 10px; display: flex; justify-content: space-between;">
          <span>FORMAT: 3-MINUTE BROADCAST (~330–390 WORDS)</span>
          <span>TOTAL: ${s.total_words || '~350'} WORDS &bull; ~${Math.round(s.estimated_seconds || 180)}s</span>
        </div>
        ${sections
          .filter((sec) => sec.text)
          .map(
            (sec) => `
            <div class="script-beat-row" style="flex-direction: column; gap: 6px; margin-bottom: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="beat-name-badge">${sec.icon} ${sec.name.toUpperCase()}</span>
                <span style="font-size: 0.7rem; color: var(--accent-amber); font-family: var(--font-mono);">${sec.timing} &bull; ${sec.words}</span>
              </div>
              <div class="beat-text" style="line-height: 1.45;">${sec.text}</div>
            </div>
          `
          )
          .join('')}
      `;
    } else {
      el.drawerScriptContent.innerHTML = `<div style="color: #64748b;">No detailed script available.</div>`;
    }

    el.videoModal.style.display = 'flex';
  }

  function closeVideoModal() {
    if (!el.videoModal) return;
    el.modalVideoPlayer.pause();
    el.modalVideoPlayer.src = '';
    el.videoModal.style.display = 'none';
  }

  // ============================================================================
  // Slide Inspector Modal (10-15s Slide Visual & Script Quality Control)
  // ============================================================================

  async function openSlidesModal(story) {
    if (!el.slidesModal) return;
    if (el.slidesModalTitle) el.slidesModalTitle.textContent = `Slide Inspection: ${story.title}`;
    if (el.slidesGridContainer) {
      el.slidesGridContainer.innerHTML = `<div style="color: #94a3b8; padding: 30px; font-size: 0.95rem; grid-column: 1/-1; text-align: center;">Loading 1080p verified broadcast slides...</div>`;
    }
    el.slidesModal.style.display = 'block';

    try {
      const resp = await fetch(`${API_BASE}/api/v1/story/${story.id}/slides`);
      if (!resp.ok) {
        if (el.slidesGridContainer) {
          el.slidesGridContainer.innerHTML = `<div style="color: #f87171; padding: 30px; grid-column: 1/-1;">Could not load slides. Slides appear once the image generation agent processes the story.</div>`;
        }
        return;
      }
      const data = await resp.json();
      const slides = data.slides || [];
      if (slides.length === 0) {
        if (el.slidesGridContainer) {
          el.slidesGridContainer.innerHTML = `<div style="color: #94a3b8; padding: 30px; grid-column: 1/-1; text-align: center;">No slides rendered yet for this story. Click "Generate Video" or "Real Broadcast Generation" to build them.</div>`;
        }
        return;
      }

      if (el.slidesGridContainer) {
        el.slidesGridContainer.innerHTML = slides.map(s => `
          <div style="background: #0f172a; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; transition: transform 0.2s, box-shadow 0.2s;" onmouseenter="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 10px 25px rgba(0,0,0,0.5)'" onmouseleave="this.style.transform='none'; this.style.boxShadow='none'">
            <div style="position: relative; aspect-ratio: 16/9; background: #020617; overflow: hidden;">
              ${s.image_url 
                ? `<img id="slide-img-${s.slide_index}" src="${API_BASE}${s.image_url}" alt="${s.beat}" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.parentElement.innerHTML='<div style=\\'display:flex;height:100%;align-items:center;justify-content:center;color:#64748b;font-size:0.8rem;\\'>Visual Processing</div>'">`
                : `<div style="display:flex;height:100%;align-items:center;justify-content:center;color:#64748b;font-size:0.8rem;">Visual Pending</div>`
              }
              <div style="position: absolute; top: 10px; left: 10px; background: rgba(15,23,42,0.85); backdrop-filter: blur(4px); border: 1px solid #00f0ff; color: #00f0ff; font-family: monospace; font-size: 0.75rem; font-weight: 700; padding: 3px 8px; border-radius: 4px;">
                SCENE ${s.slide_index}
              </div>
              <div style="position: absolute; bottom: 10px; right: 10px; background: rgba(16,185,129,0.85); backdrop-filter: blur(4px); color: #fff; font-size: 0.7rem; font-weight: 600; padding: 2px 7px; border-radius: 4px;" id="slide-badge-${s.slide_index}">
                ✓ NVIDIA / Studio Verified
              </div>
            </div>
            <div style="padding: 14px; display: flex; flex-direction: column; gap: 8px; flex: 1;">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="font-size: 0.8rem; font-weight: 700; color: #38bdf8; text-transform: uppercase;">${s.beat}</span>
                <span style="font-size: 0.7rem; color: #64748b;">10-15s beat</span>
              </div>
              <p style="font-size: 0.8rem; color: #cbd5e1; line-height: 1.45; margin: 0; flex: 1;">${s.narration}</p>
              <div style="margin-top: 6px; display: flex; justify-content: flex-end; align-items: center; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;">
                <button class="btn-reroll-slide" data-story-id="${story.id}" data-slide-idx="${s.slide_index}" style="padding: 5px 10px; background: rgba(118,185,0,0.15); border: 1px solid #76b900; border-radius: 6px; color: #a3e635; font-size: 0.72rem; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 4px;" title="Regenerate this single scene using NVIDIA FLUX and verify with Llama 3.2 Vision">
                  <span>🔄 Re-roll Slide (NVIDIA AI)</span>
                </button>
              </div>
            </div>
          </div>
        `).join('');

        // Wire re-roll slide buttons
        el.slidesGridContainer.querySelectorAll('.btn-reroll-slide').forEach((btn) => {
          btn.addEventListener('click', async (e) => {
            const sid = btn.getAttribute('data-story-id');
            const sidx = btn.getAttribute('data-slide-idx');
            btn.disabled = true;
            const originalText = btn.innerHTML;
            btn.innerHTML = `<span>⏳ Re-rolling...</span>`;
            appendLog(`[RE-ROLL] Regenerating Scene ${sidx} for story ${sid} with NVIDIA AI & Llama 3.2 Vision verification...`, 'log-system');

            try {
              const selectedModel = el.configModelSelect ? el.configModelSelect.value : null;
              const reResp = await fetch(`${API_BASE}/api/v1/story/${sid}/slide/${sidx}/regenerate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_name: selectedModel }),
              });
              const reData = await reResp.json();
              if (reData.status === 'success' && reData.image_url) {
                const imgEl = document.getElementById(`slide-img-${sidx}`);
                if (imgEl) {
                  imgEl.src = `${API_BASE}${reData.image_url}?t=${Date.now()}`;
                }
                const badgeEl = document.getElementById(`slide-badge-${sidx}`);
                if (badgeEl) {
                  const mShort = (reData.model || 'FLUX').split('/').pop();
                  badgeEl.textContent = `✓ Re-rolled (${mShort})`;
                  badgeEl.style.background = '#76b900';
                  badgeEl.style.color = '#000';
                }
                btn.innerHTML = `<span>✓ Re-rolled!</span>`;
                setTimeout(() => {
                  btn.disabled = false;
                  btn.innerHTML = originalText;
                }, 2500);
                appendLog(`[RE-ROLL SUCCESS] Scene ${sidx} refreshed! Image: ${reData.image_path}`);
              } else {
                throw new Error(reData.detail || reData.message || 'Generation failed');
              }
            } catch (err) {
              btn.disabled = false;
              btn.innerHTML = originalText;
              appendLog(`[RE-ROLL ERROR] Failed on Scene ${sidx}: ${err.message}`);
              alert(`Slide Re-roll Notice:\n${err.message}`);
            }
          });
        });
      }
    } catch (e) {
      if (el.slidesGridContainer) {
        el.slidesGridContainer.innerHTML = `<div style="color: #f87171; padding: 30px; grid-column: 1/-1;">Error loading slides: ${e.message}</div>`;
      }
    }
  }

  function closeSlidesModal() {
    if (el.slidesModal) el.slidesModal.style.display = 'none';
  }

  // ============================================================================
  // High-CTR A/B Thumbnails Modal
  // ============================================================================

  async function openThumbnailsModal(story) {
    if (!el.thumbnailsModal) return;
    if (el.thumbnailsModalTitle) el.thumbnailsModalTitle.textContent = `A/B High-CTR Thumbnails: ${story.title}`;
    el.thumbnailsModal.style.display = 'block';

    try {
      const resp = await fetch(`${API_BASE}/api/v1/story/${story.id}/thumbnails`);
      if (resp.ok) {
        const data = await resp.json();
        const tNow = Date.now();
        if (el.thumbAImg && data.thumbnail_a_url) {
          el.thumbAImg.src = `${API_BASE}${data.thumbnail_a_url}?t=${tNow}`;
        }
        if (el.thumbADownload && data.thumbnail_a_url) {
          el.thumbADownload.href = `${API_BASE}${data.thumbnail_a_url}`;
        }
        if (el.thumbBImg && data.thumbnail_b_url) {
          el.thumbBImg.src = `${API_BASE}${data.thumbnail_b_url}?t=${tNow}`;
        }
        if (el.thumbBDownload && data.thumbnail_b_url) {
          el.thumbBDownload.href = `${API_BASE}${data.thumbnail_b_url}`;
        }
      }
    } catch (e) {
      appendLog(`[THUMBNAILS ERROR] Failed to fetch A/B thumbnails: ${e.message}`);
    }
  }

  function closeThumbnailsModal() {
    if (el.thumbnailsModal) el.thumbnailsModal.style.display = 'none';
  }

  // ============================================================================
  // 9:16 Vertical Video (Shorts / Reels) Modal
  // ============================================================================

  async function openVerticalVideoModal(story) {
    if (!el.verticalModal) return;
    if (el.verticalModalTitle) el.verticalModalTitle.textContent = `9:16 Shorts/Reels: ${story.title}`;
    el.verticalModal.style.display = 'block';

    const cleanTitle = (story.title || story.id)
      .replace(/[^a-zA-Z0-9\s_-]/g, '')
      .trim()
      .replace(/\s+/g, '_')
      .substring(0, 60);
    const baseName = cleanTitle || `news_${story.id}`;
    const vertFileName = `${baseName}_shorts_9x16.mp4`;

    if (el.verticalDownloadBtn) {
      el.verticalDownloadBtn.href = `${API_BASE}/api/v1/videos/${story.id}/download-vertical`;
      el.verticalDownloadBtn.download = vertFileName;
    }

    if (el.verticalVideoPlayer) {
      el.verticalVideoPlayer.src = `${API_BASE}/api/v1/videos/${story.id}/preview-vertical`;
      el.verticalVideoPlayer.load();
      el.verticalVideoPlayer.play().catch(() => {});
    }
  }

  function closeVerticalVideoModal() {
    if (!el.verticalModal) return;
    if (el.verticalVideoPlayer) {
      el.verticalVideoPlayer.pause();
      el.verticalVideoPlayer.src = '';
    }
    el.verticalModal.style.display = 'none';
  }

  // ============================================================================
  // YouTube Community Post & Pinned Comment Modal
  // ============================================================================

  async function openCommunityModal(story) {
    if (!el.communityModal) return;
    if (el.communityModalTitle) el.communityModalTitle.textContent = `Community Post & Pinned Comment: ${story.title}`;
    if (el.communityPostText) el.communityPostText.value = 'Generating YouTube Community Post with interactive audience poll...';
    if (el.pinnedCommentText) el.pinnedCommentText.value = 'Generating pinned comment with verified fact-check and timestamps...';
    el.communityModal.style.display = 'block';

    try {
      const resp = await fetch(`${API_BASE}/api/v1/story/${story.id}/community-post`);
      if (resp.ok) {
        const data = await resp.json();
        if (el.communityPostText) el.communityPostText.value = data.community_post || 'No community post available.';
        if (el.pinnedCommentText) el.pinnedCommentText.value = data.pinned_comment || 'No pinned comment available.';
      }
    } catch (e) {
      appendLog(`[COMMUNITY ERROR] Failed to fetch community post: ${e.message}`);
    }
  }

  function closeCommunityModal() {
    if (el.communityModal) el.communityModal.style.display = 'none';
  }

  // ============================================================================
  // YouTube Upload Details Modal
  // ============================================================================

  async function openYouTubeDetailsModal(story) {
    if (!el.ytDetailsModal) return;
    state.activeStoryForModal = story;

    const cleanTitle = (story.title || story.id)
      .replace(/[^a-zA-Z0-9\s_-]/g, '')
      .trim()
      .replace(/\s+/g, '_')
      .substring(0, 60);
    const baseName = cleanTitle || `news_${story.id}`;
    const metaFileName = `${baseName}.txt`;

    // Reset fields to loading state
    el.ytModalTitle.textContent = story.title;
    if (el.ytFileBlock) el.ytFileBlock.value = 'Formatting metadata file (metadata.txt)...';
    if (el.btnDownloadMetaFile) {
      el.btnDownloadMetaFile.href = `${API_BASE}/api/v1/story/${story.id}/metadata-file/download`;
      el.btnDownloadMetaFile.download = metaFileName;
      el.btnDownloadMetaFile.textContent = `⬇️ Download ${metaFileName}`;
    }
    el.ytInputTitle.value = 'Loading title...';
    el.ytTextareaDesc.value = 'Generating complete YouTube description with breakdown & verified sources...';
    el.ytInputTags.value = 'Generating tags...';
    el.ytTagsCount.textContent = '(-- tags)';
    el.ytTagChips.innerHTML = '';

    // Reset or sync modal upload progress bar
    const modalBarWrap = document.getElementById('yt-modal-upload-bar-wrap');
    const modalStatusText = document.getElementById('yt-modal-upload-status-text');
    const modalPct = document.getElementById('yt-modal-upload-pct');
    const modalProgressFill = document.getElementById('yt-modal-upload-progress-fill');
    if (modalBarWrap) modalBarWrap.style.display = 'none';

    // Check if this story is currently being uploaded or already completed
    fetch(`${API_BASE}/api/v1/story/${story.id}/upload-progress`)
      .then((r) => r.json())
      .then((prog) => {
        if (!prog || !modalBarWrap) return;
        if (prog.status === 'uploading') {
          modalBarWrap.style.display = 'block';
          if (modalPct) modalPct.textContent = `${prog.progress}%`;
          if (modalProgressFill) modalProgressFill.style.width = `${prog.progress}%`;
          if (modalStatusText) modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #ef4444;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span>${prog.message || 'Uploading to YouTube...'}</span>`;
        } else if (prog.status === 'completed') {
          modalBarWrap.style.display = 'block';
          if (modalPct) modalPct.textContent = '100%';
          if (modalProgressFill) {
            modalProgressFill.style.width = '100%';
            modalProgressFill.style.background = '#10b981';
          }
          const vidUrl = prog.video_url || (prog.video_id ? `https://youtu.be/${prog.video_id}` : null);
          const studioUrl = prog.video_id ? `https://studio.youtube.com/video/${prog.video_id}/edit` : null;
          if (modalStatusText) {
            modalStatusText.innerHTML = `
              <div style="display: flex; flex-direction: column; gap: 4px;">
                <span style="color: #34d399; font-weight: 700;">✓ Video uploaded as Private on your channel!</span>
                <span style="font-size: 0.75rem; color: #94a3b8;">
                  ${vidUrl ? `<a href="${vidUrl}" target="_blank" style="color: #38bdf8; text-decoration: underline; margin-right: 10px;">▶ Watch Video ↗</a>` : ''}
                  ${studioUrl ? `<a href="${studioUrl}" target="_blank" style="color: #f59e0b; text-decoration: underline;">🛠 Manage / Make Public in YouTube Studio ↗</a>` : ''}
                </span>
              </div>
            `;
          }
        }
      })
      .catch(() => {});

    el.ytDetailsModal.style.display = 'flex';

    try {
      const res = await fetch(`${API_BASE}/api/v1/story/${story.id}/youtube-details`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.activeYoutubeMetadata = data;

      if (el.ytFileBlock) el.ytFileBlock.value = data.metadata_file || '';

      const exactJson = {
        title: data.title || '',
        description: data.description || '',
        tags: data.tags || [],
        madeForKids: data.madeForKids !== undefined ? data.madeForKids : false,
        category: data.category || 'News & Politics',
        visibility: data.visibility || 'public',
        scheduleDate: data.scheduleDate || new Date().toISOString().split('T')[0],
        scheduleTime: data.scheduleTime || 'Immediate',
      };
      const jsonFormatted = data.json_formatted || JSON.stringify(exactJson, null, 2);

      if (el.ytJsonBlock) el.ytJsonBlock.value = jsonFormatted;
      el.ytModalTitle.textContent = data.title;
      el.ytInputTitle.value = data.title;
      el.ytTextareaDesc.value = data.description;
      el.ytInputTags.value = Array.isArray(data.tags) ? data.tags.join(', ') : (data.tags_string || '');
      el.ytTagsCount.textContent = `(${data.tags ? data.tags.length : 0} tags)`;
      el.ytTagChips.innerHTML = (data.tags || []).map(t => `<span class="yt-tag-chip">#${t}</span>`).join('');
      if (el.ytMetaKids) el.ytMetaKids.textContent = exactJson.madeForKids ? 'true' : 'false';
      if (el.ytMetaCategory) el.ytMetaCategory.textContent = exactJson.category;
      if (el.ytMetaVisibility) el.ytMetaVisibility.textContent = exactJson.visibility;
      if (el.ytMetaSchedDate) el.ytMetaSchedDate.textContent = exactJson.scheduleDate;
      if (el.ytMetaSchedTime) el.ytMetaSchedTime.textContent = exactJson.scheduleTime;
      if (el.ytMetaLanguage) el.ytMetaLanguage.textContent = data.language || 'English (United States)';
    } catch (err) {
      appendLog(`[ERROR] Failed to load YouTube details: ${err.message}`, 'log-system');
      el.ytTextareaDesc.value = `Error generating YouTube details: ${err.message}`;
    }
  }


  function closeYouTubeDetailsModal() {
    if (el.ytDetailsModal) {
      el.ytDetailsModal.style.display = 'none';
    }
  }

  function copyTextToClipboard(text, buttonElement) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        applyCopyFeedback(buttonElement);
      }).catch(() => {
        fallbackCopyText(text, buttonElement);
      });
    } else {
      fallbackCopyText(text, buttonElement);
    }
  }

  function fallbackCopyText(text, buttonElement) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
      applyCopyFeedback(buttonElement);
    } catch (e) {
      console.error('Copy fallback failed:', e);
    }
    document.body.removeChild(ta);
  }

  function applyCopyFeedback(buttonElement) {
    if (!buttonElement) return;
    const originalText = buttonElement.innerHTML;
    buttonElement.classList.add('btn-copied');
    buttonElement.innerHTML = '<span>✓ Copied!</span>';
    setTimeout(() => {
      buttonElement.classList.remove('btn-copied');
      buttonElement.innerHTML = originalText;
    }, 1800);
  }

  function copyAllYouTubeMetadata(buttonElement) {
    if (!state.activeYoutubeMetadata) return;
    const activeTab = document.querySelector('.yt-modal-tab.active');
    let textToCopy = '';

    if (activeTab && activeTab.getAttribute('data-tab') === 'tab-json') {
      textToCopy = el.ytJsonBlock ? el.ytJsonBlock.value : '';
    } else {
      textToCopy = el.ytFileBlock ? el.ytFileBlock.value : '';
    }

    if (!textToCopy && state.activeYoutubeMetadata) {
      textToCopy = state.activeYoutubeMetadata.file_content || JSON.stringify(state.activeYoutubeMetadata, null, 2);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        applyCopyAllFeedback(buttonElement);
      }).catch(() => {
        fallbackCopyText(textToCopy, buttonElement);
      });
    } else {
      fallbackCopyText(textToCopy, buttonElement);
    }
  }

  async function uploadStoryToYouTube(storyId, buttonElement, rank = 1) {
    if (!buttonElement) return;
    const originalText = buttonElement.innerHTML;
    buttonElement.disabled = true;

    // Elements in the details modal
    const modalBarWrap = document.getElementById('yt-modal-upload-bar-wrap');
    const modalStatusText = document.getElementById('yt-modal-upload-status-text');
    const modalPct = document.getElementById('yt-modal-upload-pct');
    const modalProgressFill = document.getElementById('yt-modal-upload-progress-fill');

    if (modalBarWrap) {
      modalBarWrap.style.display = 'block';
      if (modalStatusText) {
        modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #ef4444;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span>Connecting to YouTube (Rank #${rank})...</span>`;
      }
      if (modalPct) modalPct.textContent = '0%';
      if (modalProgressFill) {
        modalProgressFill.style.width = '0%';
        modalProgressFill.style.background = 'linear-gradient(90deg, #ef4444, #f59e0b, #10b981)';
      }
    }

    buttonElement.innerHTML = `<span>⏳ Uploading 0%...</span>`;
    appendLog(`[YOUTUBE] Upload initiated for story ${storyId} (Rank #${rank})...`);

    let lastReportedPct = -1;
    const pollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`${API_BASE}/api/v1/story/${storyId}/upload-progress`);
        if (!pRes.ok) return;
        const prog = await pRes.json();
        if (!prog) return;

        const pct = prog.progress || 0;
        const msg = prog.message || `Uploading: ${pct}%`;

        if (prog.status === 'authenticating') {
          buttonElement.innerHTML = `<span>🔑 Sign-in...</span>`;
          if (modalStatusText) {
            modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #f59e0b;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span style="color:#fbbf24;">Awaiting 1-time Google sign-in in browser...</span>`;
          }
          if (modalPct) modalPct.textContent = 'Auth';
        } else if (prog.status === 'uploading') {
          buttonElement.innerHTML = `<span>⏳ Uploading ${pct}%...</span>`;
          if (modalPct) modalPct.textContent = `${pct}%`;
          if (modalProgressFill) modalProgressFill.style.width = `${pct}%`;
          if (modalStatusText) {
            modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #ef4444;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span>${msg}</span>`;
          }

          if (pct >= lastReportedPct + 20) {
            lastReportedPct = pct;
            appendLog(`[YOUTUBE PROGRESS] ${msg}`);
          }
        } else if (prog.status === 'completed') {
          buttonElement.innerHTML = `<span>✓ 100%</span>`;
          if (modalPct) modalPct.textContent = '100%';
          if (modalProgressFill) {
            modalProgressFill.style.width = '100%';
            modalProgressFill.style.background = '#10b981';
          }
          if (modalStatusText) {
            modalStatusText.innerHTML = `<span style="color:#34d399;font-weight:700;">✓ Upload complete! ID: ${prog.video_id || ''}</span>`;
          }
        }
      } catch (_) {}
    }, 500);

    try {
      const res = await fetch(`${API_BASE}/api/v1/story/${storyId}/upload-youtube?rank=${rank}`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      clearInterval(pollInterval);

      const vidUrl = data.video_url || (data.video_id ? `https://youtu.be/${data.video_id}` : null);
      const studioUrl = data.video_id ? `https://studio.youtube.com/video/${data.video_id}/edit` : null;
      const isSched = data.is_scheduled;
      const schedDesc = data.schedule_description || (isSched ? `Scheduled for Public at ${data.schedule_time}` : 'Published Public Immediately');
      const badgeText = isSched ? `✓ Scheduled (${data.schedule_time})` : `✓ Public (Published)`;

      buttonElement.disabled = false;
      buttonElement.innerHTML = `<span>${badgeText} ↗</span>`;
      buttonElement.style.color = '#34d399';
      buttonElement.style.borderColor = '#34d399';
      buttonElement.onclick = (e) => {
        e.stopPropagation();
        if (vidUrl) window.open(vidUrl, '_blank');
      };

      if (modalPct) modalPct.textContent = '100%';
      if (modalProgressFill) {
        modalProgressFill.style.width = '100%';
        modalProgressFill.style.background = '#10b981';
      }
      if (modalStatusText) {
        modalStatusText.innerHTML = `
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <span style="color: #34d399; font-weight: 700;">✓ ${schedDesc}!</span>
            <span style="font-size: 0.75rem; color: #94a3b8;">
              ${vidUrl ? `<a href="${vidUrl}" target="_blank" style="color: #38bdf8; text-decoration: underline; margin-right: 10px;">▶ Watch Video ↗</a>` : ''}
              ${studioUrl ? `<a href="${studioUrl}" target="_blank" style="color: #f59e0b; text-decoration: underline;">🛠 View in YouTube Studio ↗</a>` : ''}
            </span>
          </div>
        `;
      }

      appendLog(`[YOUTUBE SUCCESS] ${schedDesc}: ${vidUrl || data.video_id}`);
      if (vidUrl) {
        window.open(vidUrl, '_blank');
      }
    } catch (err) {
      clearInterval(pollInterval);
      buttonElement.disabled = false;
      buttonElement.innerHTML = originalText;
      if (modalStatusText) {
        modalStatusText.innerHTML = `<span style="color:#ef4444;">Upload error: ${err.message}</span>`;
      }
      appendLog(`[YOUTUBE ERROR] Upload failed: ${err.message}`, 'log-system');
      alert(`YouTube Upload Notice: ${err.message}`);
    }
  }

  async function uploadStoryToFacebook(storyId, buttonElement) {
    if (!buttonElement) return;
    const originalText = buttonElement.innerHTML;
    buttonElement.disabled = true;

    const modalBarWrap = document.getElementById('yt-modal-upload-bar-wrap');
    const modalStatusText = document.getElementById('yt-modal-upload-status-text');
    const modalPct = document.getElementById('yt-modal-upload-pct');
    const modalProgressFill = document.getElementById('yt-modal-upload-progress-fill');

    if (modalBarWrap) {
      modalBarWrap.style.display = 'block';
      if (modalStatusText) {
        modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #1877f2;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span>Connecting to Facebook Graph API...</span>`;
      }
      if (modalPct) modalPct.textContent = '0%';
      if (modalProgressFill) {
        modalProgressFill.style.width = '0%';
        modalProgressFill.style.background = 'linear-gradient(90deg, #1877f2, #38bdf8)';
      }
    }

    buttonElement.innerHTML = `<span>⏳ FB 0%...</span>`;
    appendLog(`[FACEBOOK] Upload initiated for story ${storyId}...`);

    let lastReportedPct = -1;
    const pollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`${API_BASE}/api/v1/story/${storyId}/upload-facebook/status`);
        if (!pRes.ok) return;
        const prog = await pRes.json();
        if (!prog) return;

        const pct = prog.progress || 0;
        const msg = prog.message || `Uploading to Facebook: ${pct}%`;

        buttonElement.innerHTML = `<span>⏳ FB ${pct}%</span>`;
        if (modalPct) modalPct.textContent = `${pct}%`;
        if (modalProgressFill) modalProgressFill.style.width = `${pct}%`;
        if (modalStatusText) {
          modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #1877f2;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span>${msg}</span>`;
        }

        if (pct >= lastReportedPct + 25) {
          lastReportedPct = pct;
          appendLog(`[FACEBOOK PROGRESS] ${msg}`);
        }
      } catch (_) {}
    }, 600);

    try {
      const res = await fetch(`${API_BASE}/api/v1/story/${storyId}/upload-facebook`, {
        method: 'POST',
      });
      const data = await res.json();
      clearInterval(pollInterval);

      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || data.detail || `HTTP ${res.status}`);
      }

      const fbUrl = data.video_url;
      buttonElement.disabled = false;
      buttonElement.innerHTML = `<span>✓ FB Live ↗</span>`;
      buttonElement.style.color = '#60a5fa';
      buttonElement.style.borderColor = '#60a5fa';
      buttonElement.onclick = (e) => {
        e.stopPropagation();
        if (fbUrl) window.open(fbUrl, '_blank');
      };

      if (modalPct) modalPct.textContent = '100%';
      if (modalProgressFill) {
        modalProgressFill.style.width = '100%';
        modalProgressFill.style.background = '#10b981';
      }
      if (modalStatusText) {
        modalStatusText.innerHTML = `
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <span style="color: #34d399; font-weight: 700;">✓ Successfully published to Facebook Page!</span>
            <span style="font-size: 0.75rem; color: #94a3b8;">
              ${fbUrl ? `<a href="${fbUrl}" target="_blank" style="color: #60a5fa; text-decoration: underline;">▶ View Video Post on Facebook ↗</a>` : ''}
            </span>
          </div>
        `;
      }

      appendLog(`[FACEBOOK SUCCESS] Published: ${fbUrl || data.video_id}`);
      if (fbUrl) window.open(fbUrl, '_blank');
    } catch (err) {
      clearInterval(pollInterval);
      buttonElement.disabled = false;
      buttonElement.innerHTML = originalText;
      if (modalStatusText) {
        modalStatusText.innerHTML = `<span style="color:#ef4444;">Facebook error: ${err.message}</span>`;
      }
      appendLog(`[FACEBOOK ERROR] Upload failed: ${err.message}`, 'log-system');
      alert(`Facebook Upload Notice:\n${err.message}`);
    }
  }

  async function uploadStoryToInstagram(storyId, buttonElement) {
    if (!buttonElement) return;
    const originalText = buttonElement.innerHTML;
    buttonElement.disabled = true;

    const modalBarWrap = document.getElementById('yt-modal-upload-bar-wrap');
    const modalStatusText = document.getElementById('yt-modal-upload-status-text');
    const modalPct = document.getElementById('yt-modal-upload-pct');
    const modalProgressFill = document.getElementById('yt-modal-upload-progress-fill');

    if (modalBarWrap) {
      modalBarWrap.style.display = 'block';
      if (modalStatusText) {
        modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #e1306c;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span>Connecting to Instagram Graph API...</span>`;
      }
      if (modalPct) modalPct.textContent = '0%';
      if (modalProgressFill) {
        modalProgressFill.style.width = '0%';
        modalProgressFill.style.background = 'linear-gradient(90deg, #e1306c, #f59e0b)';
      }
    }

    buttonElement.innerHTML = `<span>⏳ IG 0%...</span>`;
    appendLog(`[INSTAGRAM] Upload initiated for story ${storyId}...`);

    let lastReportedPct = -1;
    const pollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`${API_BASE}/api/v1/story/${storyId}/upload-instagram/status`);
        if (!pRes.ok) return;
        const prog = await pRes.json();
        if (!prog) return;

        const pct = prog.progress || 0;
        const msg = prog.message || `Uploading to Instagram: ${pct}%`;

        buttonElement.innerHTML = `<span>⏳ IG ${pct}%</span>`;
        if (modalPct) modalPct.textContent = `${pct}%`;
        if (modalProgressFill) modalProgressFill.style.width = `${pct}%`;
        if (modalStatusText) {
          modalStatusText.innerHTML = `<span class="upload-spin" style="display:inline-block;width:12px;height:12px;border:2px solid #e1306c;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span> <span>${msg}</span>`;
        }

        if (pct >= lastReportedPct + 25) {
          lastReportedPct = pct;
          appendLog(`[INSTAGRAM PROGRESS] ${msg}`);
        }
      } catch (_) {}
    }, 800);

    try {
      const res = await fetch(`${API_BASE}/api/v1/story/${storyId}/upload-instagram`, {
        method: 'POST',
      });
      const data = await res.json();
      clearInterval(pollInterval);

      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || data.detail || `HTTP ${res.status}`);
      }

      const igUrl = data.post_url;
      buttonElement.disabled = false;
      buttonElement.innerHTML = `<span>✓ IG Live ↗</span>`;
      buttonElement.style.color = '#f472b6';
      buttonElement.style.borderColor = '#f472b6';
      buttonElement.onclick = (e) => {
        e.stopPropagation();
        if (igUrl) window.open(igUrl, '_blank');
      };

      if (modalPct) modalPct.textContent = '100%';
      if (modalProgressFill) {
        modalProgressFill.style.width = '100%';
        modalProgressFill.style.background = '#10b981';
      }
      if (modalStatusText) {
        modalStatusText.innerHTML = `
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <span style="color: #34d399; font-weight: 700;">✓ Successfully published to Instagram!</span>
            <span style="font-size: 0.75rem; color: #94a3b8;">
              ${igUrl ? `<a href="${igUrl}" target="_blank" style="color: #f472b6; text-decoration: underline;">▶ View Post on Instagram ↗</a>` : ''}
            </span>
          </div>
        `;
      }

      appendLog(`[INSTAGRAM SUCCESS] Published: ${igUrl || data.media_id}`);
      if (igUrl) window.open(igUrl, '_blank');
    } catch (err) {
      clearInterval(pollInterval);
      buttonElement.disabled = false;
      buttonElement.innerHTML = originalText;
      if (modalStatusText) {
        modalStatusText.innerHTML = `<span style="color:#ef4444;">Instagram error: ${err.message}</span>`;
      }
      appendLog(`[INSTAGRAM ERROR] Upload failed: ${err.message}`, 'log-system');
      alert(`Instagram Upload Notice:\n${err.message}`);
    }
  }

  function applyCopyAllFeedback(buttonElement) {
    if (!buttonElement) return;
    const originalHtml = buttonElement.innerHTML;
    buttonElement.classList.add('btn-copied');
    buttonElement.innerHTML = `
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>
      <span>✓ Copied!</span>
    `;
    setTimeout(() => {
      buttonElement.classList.remove('btn-copied');
      buttonElement.innerHTML = originalHtml;
    }, 1800);
  }

  // ============================================================================
  // Event Listeners
  // ============================================================================

  function setupEventListeners() {
    if (el.realGenBtn) {
      el.realGenBtn.addEventListener('click', startRealGenerationWorkflow);
    }

    if (el.startBtn) {
      el.startBtn.addEventListener('click', startWorkflow);
    }

    if (el.refreshBtn) {
      el.refreshBtn.addEventListener('click', () => {
        appendLog('[NET] Syncing status from backend...');
        fetchCurrentStatus();
      });
    }

    if (el.consoleClearBtn) {
      el.consoleClearBtn.addEventListener('click', () => {
        if (el.consoleLogOutput) el.consoleLogOutput.innerHTML = '';
      });
    }

    // Video modal listeners
    if (el.modalCloseBtn) {
      el.modalCloseBtn.addEventListener('click', closeVideoModal);
    }

    if (el.videoModal) {
      el.videoModal.addEventListener('click', (e) => {
        if (e.target === el.videoModal) closeVideoModal();
      });
    }

    // Slides inspection modal listeners
    if (el.slidesModalCloseBtn) {
      el.slidesModalCloseBtn.addEventListener('click', closeSlidesModal);
    }

    if (el.slidesModal) {
      el.slidesModal.addEventListener('click', (e) => {
        if (e.target === el.slidesModal) closeSlidesModal();
      });
    }

    // YouTube details modal listeners
    if (el.ytDetailsCloseBtn) {
      el.ytDetailsCloseBtn.addEventListener('click', closeYouTubeDetailsModal);
    }

    if (el.ytDetailsModal) {
      el.ytDetailsModal.addEventListener('click', (e) => {
        if (e.target === el.ytDetailsModal) closeYouTubeDetailsModal();

        // Delegate field copy button clicks
        const btn = e.target.closest('.btn-copy-field');
        if (btn) {
          const targetId = btn.getAttribute('data-target');
          const copyText = btn.getAttribute('data-copy-text');
          if (targetId) {
            const targetEl = document.getElementById(targetId);
            if (targetEl) copyTextToClipboard(targetEl.value, btn);
          } else if (copyText) {
            copyTextToClipboard(copyText, btn);
          }
        }
      });
    }

    if (el.btnCopyAll) {
      el.btnCopyAll.addEventListener('click', () => copyAllYouTubeMetadata(el.btnCopyAll));
    }

    if (el.btnUploadYtModal) {
      el.btnUploadYtModal.addEventListener('click', () => {
        if (state.activeStoryForModal) {
          uploadStoryToYouTube(state.activeStoryForModal.id, el.btnUploadYtModal, state.activeStoryForModal.rank || 1);
        }
      });
    }

    if (el.btnUploadFbModal) {
      el.btnUploadFbModal.addEventListener('click', () => {
        if (state.activeStoryForModal) {
          uploadStoryToFacebook(state.activeStoryForModal.id, el.btnUploadFbModal);
        }
      });
    }

    if (el.btnUploadIgModal) {
      el.btnUploadIgModal.addEventListener('click', () => {
        if (state.activeStoryForModal) {
          uploadStoryToInstagram(state.activeStoryForModal.id, el.btnUploadIgModal);
        }
      });
    }

    if (el.btnCopyFile) {
      el.btnCopyFile.addEventListener('click', () => {
        if (el.ytFileBlock) copyTextToClipboard(el.ytFileBlock.value, el.btnCopyFile);
      });
    }

    if (el.btnCopyJson) {
      el.btnCopyJson.addEventListener('click', () => {
        if (el.ytJsonBlock) copyTextToClipboard(el.ytJsonBlock.value, el.btnCopyJson);
      });
    }

    // YouTube modal sub-tabs switching (clean non-redundant views)
    document.querySelectorAll('.yt-modal-tab').forEach((tabBtn) => {
      tabBtn.addEventListener('click', () => {
        document.querySelectorAll('.yt-modal-tab').forEach((t) => t.classList.remove('active'));
        document.querySelectorAll('.yt-tab-pane').forEach((p) => p.classList.remove('active'));
        tabBtn.classList.add('active');
        const targetId = tabBtn.getAttribute('data-tab');
        const pane = document.getElementById(targetId);
        if (pane) pane.classList.add('active');
      });
    });

    if (el.btnCopySchedDate) {
      el.btnCopySchedDate.addEventListener('click', () => {
        if (el.ytMetaSchedDate) copyTextToClipboard(el.ytMetaSchedDate.textContent, el.btnCopySchedDate);
      });
    }

    if (el.btnCopySchedTime) {
      el.btnCopySchedTime.addEventListener('click', () => {
        if (el.ytMetaSchedTime) copyTextToClipboard(el.ytMetaSchedTime.textContent, el.btnCopySchedTime);
      });
    }

    // A/B Thumbnails modal listeners
    if (el.thumbnailsModalCloseBtn) {
      el.thumbnailsModalCloseBtn.addEventListener('click', closeThumbnailsModal);
    }
    if (el.thumbnailsModal) {
      el.thumbnailsModal.addEventListener('click', (e) => {
        if (e.target === el.thumbnailsModal) closeThumbnailsModal();
      });
    }

    // 9:16 Vertical Video modal listeners
    if (el.verticalModalCloseBtn) {
      el.verticalModalCloseBtn.addEventListener('click', closeVerticalVideoModal);
    }
    if (el.verticalModal) {
      el.verticalModal.addEventListener('click', (e) => {
        if (e.target === el.verticalModal) closeVerticalVideoModal();
      });
    }

    // Community post modal listeners
    if (el.communityModalCloseBtn) {
      el.communityModalCloseBtn.addEventListener('click', closeCommunityModal);
    }
    if (el.communityModal) {
      el.communityModal.addEventListener('click', (e) => {
        if (e.target === el.communityModal) closeCommunityModal();
      });
    }

    if (el.copyCommunityPostBtn && el.communityPostText) {
      el.copyCommunityPostBtn.addEventListener('click', () => {
        copyTextToClipboard(el.communityPostText.value, el.copyCommunityPostBtn);
      });
    }

    if (el.copyPinnedCommentBtn && el.pinnedCommentText) {
      el.copyPinnedCommentBtn.addEventListener('click', () => {
        copyTextToClipboard(el.pinnedCommentText.value, el.copyPinnedCommentBtn);
      });
    }

    // Config dropdown change listeners
    if (el.configModelSelect) {
      el.configModelSelect.addEventListener('change', updateConfig);
    }
    if (el.configLangSelect) {
      el.configLangSelect.addEventListener('change', updateConfig);
    }
    if (el.configFormatSelect) {
      el.configFormatSelect.addEventListener('change', updateConfig);
    }

    // Script drawer toggle in modal
    if (el.drawerToggleBtn && el.drawerScriptContent) {
      el.drawerToggleBtn.addEventListener('click', () => {
        const isHidden = el.drawerScriptContent.style.display === 'none';
        el.drawerScriptContent.style.display = isHidden ? 'flex' : 'none';
        const arrow = el.drawerToggleBtn.querySelector('.toggle-arrow');
        if (arrow) arrow.textContent = isHidden ? '▲' : '▼';
      });
    }

    // Tab filtering (All / World / India)
    el.navTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        el.navTabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.target;
        state.activeTab = target;

        if (target === 'all') {
          if (el.worldBlock) el.worldBlock.style.display = 'block';
          if (el.indiaBlock) el.indiaBlock.style.display = 'block';
        } else if (target === 'world') {
          if (el.worldBlock) el.worldBlock.style.display = 'block';
          if (el.indiaBlock) el.indiaBlock.style.display = 'none';
        } else if (target === 'india') {
          if (el.worldBlock) el.worldBlock.style.display = 'none';
          if (el.indiaBlock) el.indiaBlock.style.display = 'block';
        }
      });
    });

    // Escape key closes modals
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (el.videoModal && el.videoModal.style.display !== 'none') closeVideoModal();
        if (el.slidesModal && el.slidesModal.style.display !== 'none') closeSlidesModal();
        if (el.ytDetailsModal && el.ytDetailsModal.style.display !== 'none') closeYouTubeDetailsModal();
        if (el.thumbnailsModal && el.thumbnailsModal.style.display !== 'none') closeThumbnailsModal();
        if (el.verticalModal && el.verticalModal.style.display !== 'none') closeVerticalVideoModal();
        if (el.communityModal && el.communityModal.style.display !== 'none') closeCommunityModal();
      }
    });
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
