/**
 * SynthSpeak Dashboard Core Logic (app.js)
 * Coordinates the DOM updates, WebSocket streaming UI, chart rendering, 
 * and media processing mechanisms for the application. Integrates with 
 * the Python backend running on port 8000.
 */
'use strict';
const API_URL = '';
const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${wsProtocol}//${location.host}/ws`;
const WS_STREAM_URL = `${wsProtocol}//${location.host}/ws/stream`;
const PAGES = ['presentation', 'interview', 'dashboard', 'recordings', 'apikey', 'settings', 'analytics'];
const PAGE_TITLES = {
  'presentation': 'Presentation Practice',
  'analytics': 'Live Analytics Feed',
  'interview': 'Interview Practice',
  'dashboard': 'Progress Tracking',
  'recordings': 'Recordings',
  'apikey': 'API Key Management',
  'settings': 'Settings',
};
const state = {
  currentPage: 'presentation',
  recording: false,
  ws: null,
  wsConnected: false,
  streamWs: null,          // WebSocket for /ws/stream (camera + audio)
  clockInt: null,
  sessionInt: null,
  sessionSecs: 0,
  mediaStream: null,
  audioContext: null,      // AudioContext for PCM capture
  frameInterval: null,     // setInterval for frame capture
  topic: '',
  topicConfirmed: false,
  lastPauseDuration: 0,
  mediaRecorder: null,
  recordChunks: [],
  sessionStartEpoch: 0,
  lastWSSnap: {},        // latest WS state snapshot (for Stop-time logging)
};
function showToast(msg, type = '') {
  const c = document.getElementById('toastContainer');
  if (!c) return;
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.classList.add('show'), 10);
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 3200);
}

function setText(id, val) {
  const e = document.getElementById(id);
  if (e) e.textContent = val;
}

function setBar(id, pct, cls) {
  const e = document.getElementById(id);
  if (!e) return;
  e.style.width = Math.max(0, Math.min(100, pct)) + '%';
  if (cls) {
    e.classList.remove('green', 'yellow', 'red', 'orange');
    e.classList.add(cls);
  }
}

function renderPauseChips(pauses) {
  const c = document.getElementById('pauseChips');
  if (!c) return;
  c.innerHTML = '';
  pauses.forEach(p => {
    const s = document.createElement('span');
    s.className = 'pause-chip';
    s.textContent = p + 's';
    c.appendChild(s);
  });
}

function show(el) { el && el.classList.remove('hidden'); }
function hide(el) { el && el.classList.add('hidden'); }

function formatTime(s) {
  const m = Math.floor(s / 60);
  return m + ':' + (s % 60).toString().padStart(2, '0');
}
function startClock() {
  const el = document.getElementById('clockDisplay');
  if (!el) return;
  clearInterval(state.clockInt);
  state.clockInt = setInterval(() => {
    el.textContent = new Date().toTimeString().slice(0, 8);
  }, 1000);
  el.textContent = new Date().toTimeString().slice(0, 8);
}
const PAGE_ID_MAP = {
  'presentation': 'pagePractice',
  'analytics': 'pagePractice',    // same DOM — only the right-panel tab changes
  'interview': 'pageInterview',
  'dashboard': 'pageDashboard',
  'recordings': 'pageRecordings',
  'apikey': 'pageApikey',
  'settings': 'pageSettings',
};

function showPage(name) {
  const isAnalytics = name === 'analytics';
  if (!PAGES.includes(name)) name = 'presentation';
  state.currentPage = name;
  Object.entries(PAGE_ID_MAP).forEach(([page, domId]) => {
    if (page === 'analytics') return; // handled via 'presentation' mapping
    const el = document.getElementById(domId);
    if (!el) return;
    const isActive = page === name || (page === 'presentation' && isAnalytics);
    if (isActive) el.classList.remove('hidden');
    else el.classList.add('hidden');
  });
  setText('pageTitle', PAGE_TITLES[name] || 'SynthSpeak');
  const isPres = name === 'presentation' || isAnalytics;
  const elScreenBtn = document.getElementById('screenshotBtn');
  const elShareBtn = document.getElementById('shareBtn');
  if (elScreenBtn) elScreenBtn.classList.toggle('hidden', !isPres);
  if (elShareBtn) elShareBtn.classList.toggle('hidden', !isPres);
  const showBack = name !== 'presentation' && !isAnalytics;
  const backBtn = document.getElementById('backBtn');
  if (backBtn) backBtn.classList.toggle('hidden', !showBack);
  const tooltip = document.getElementById('startTooltip');
  if (tooltip) tooltip.style.display = (isPres && !state.recording) ? 'flex' : 'none';
  updateNavHighlight(name);
  const liveB = document.getElementById('liveBadge');
  if (liveB) liveB.style.display = (isPres && state.recording) ? 'flex' : 'none';
  if (name === 'recordings') loadRecordings();
  if (name === 'apikey') loadApiKeys();
  setTimeout(() => {
    if (isAnalytics) {
      switchPanelTab('analytics');
    } else if (name === 'presentation') {
      switchPanelTab('coaching');
    }
  }, 0);
}

function updateNavHighlight(page) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const navMap = {
    'presentation': 'nav-practice',
    'analytics': 'nav-practice',   // analytics lives inside the practice page
    'interview': 'nav-practice',
    'recordings': 'nav-recordings',
    'apikey': 'nav-apikey',
    'settings': 'nav-settings',
  };
  const navId = navMap[page];
  if (navId) document.getElementById(navId)?.classList.add('active');
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.getElementById('practiceWrapper')?.classList.remove('dropdown-open');
  });
}

function switchPanelTab(tab) {
  const isAnalytics = tab === 'analytics';

  const pCoaching = document.getElementById('panelCoaching');
  if (pCoaching) {
    pCoaching.classList.toggle('hidden', isAnalytics);
    pCoaching.style.display = isAnalytics ? 'none' : 'flex';
  }

  const pAnalytics = document.getElementById('panelAnalytics');
  if (pAnalytics) {
    pAnalytics.classList.toggle('hidden', !isAnalytics);
    pAnalytics.style.display = isAnalytics ? 'flex' : 'none';
  }

  const bCoaching = document.getElementById('ptabCoaching');
  if (bCoaching) bCoaching.classList.toggle('active', !isAnalytics);

  const bAnalytics = document.getElementById('ptabAnalytics');
  if (bAnalytics) bAnalytics.classList.toggle('active', isAnalytics);
}
function initSidebar() {
  document.getElementById('sidebarToggle')?.addEventListener('click', () => {
    document.getElementById('sidebar')?.classList.toggle('collapsed');
  });
  document.querySelectorAll('.nav-item[data-page]').forEach(link => {
    link.addEventListener('click', e => {
      if (link.id === 'nav-practice' && window.innerWidth <= 768) {
        e.preventDefault();
        document.getElementById('practiceWrapper')?.classList.toggle('dropdown-open');
        return;
      }
      e.preventDefault();
      showPage(link.dataset.page);
    });
  });
  document.querySelectorAll('.nav-drop-item').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation(); // prevent bubbling up to wrapper
      const mode = item.dataset.mode;
      document.getElementById('practiceWrapper')?.classList.remove('dropdown-open'); // close if open on mobile

      if (mode === 'presentation' || mode === 'interview' || mode === 'analytics') {
        showPage(mode);
      } else if (mode === 'upload') {
        const modal = document.getElementById('companyUploadModal');
        if (modal) modal.classList.remove('hidden');
        else showToast('Upload feature coming soon!', '');
      } else {
        showToast(`Coming soon: ${mode} mode!`, '');
      }
    });
  });
  document.addEventListener('click', e => {
    const wrap = document.getElementById('practiceWrapper');
    if (wrap && wrap.classList.contains('dropdown-open') && !wrap.contains(e.target)) {
      wrap.classList.remove('dropdown-open');
    }
  });

  document.getElementById('backBtn')?.addEventListener('click', () => showPage('presentation'));
}
function initPracticeCards() {
  document.querySelectorAll('.practice-mode-card').forEach(card => {
    const mode = card.dataset.mode;
    const handler = (e) => {
      if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
        e.stopPropagation();
      }
      if (mode === 'presentation') showPage('presentation');
      else if (mode === 'interview') showPage('interview');
      else showToast('Coming soon: ' + mode + ' mode!', '');
    };
    card.addEventListener('click', handler);
    card.querySelector('.pmode-btn')?.addEventListener('click', e => {
      e.stopPropagation();
      if (mode === 'presentation') showPage('presentation');
      else if (mode === 'interview') showPage('interview');
      else showToast('Coming soon!', '');
    });
  });
}
function connectWS(onReady) {
  state.lastTranscription = ''; // reset on connect
  try {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      if (onReady) onReady();
      return;
    }
    if (state.ws && state.ws.readyState === WebSocket.CONNECTING) {
      const oldOpen = state.ws.onopen;
      state.ws.onopen = (e) => { if (oldOpen) oldOpen(e); if (onReady) onReady(); };
      return;
    }
    state.ws = new WebSocket(WS_URL);
    state.ws.onopen = () => {
      state.wsConnected = true;
      console.log('[SynthSpeak] Connected to backend ' + WS_URL);
      if (onReady) onReady();
    };
    state.ws.onmessage = e => {
      try { handleWSMessage(JSON.parse(e.data)); } catch { }
    };
    state.ws.onerror = () => { state.wsConnected = false; console.warn('[SynthSpeak] Backend not reachable - demo mode'); };
    state.ws.onclose = () => { state.wsConnected = false; };
  } catch { state.wsConnected = false; }
}

function sendWS(data) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(data));
  }
}

function handleWSMessage(data) {
  if (!data.type || data.type !== 'ack') state.lastWSSnap = data;
  if (data.type === 'ack') {
    // When backend confirms start, send the manual topic (pipelines are now ready)
    if (data.cmd === 'start' && data.ok && state.topicConfirmed && state.topic) {
      sendWS({ cmd: 'manual', topic: state.topic });
    }
    return;
  }
  if (data.type === 'snapshot') {
    const snap = data.data || data;
    const v = Math.round((snap.similarity || 0) * 100);
    setBar('relevanceBar', v, v > 60 ? 'green' : v > 30 ? 'yellow' : 'red');
    setText('relevancePercent', v + '%');
    const badge = document.getElementById('relevanceBadge');
    if (badge) {
      badge.textContent = v + '%';
      badge.className = 'card-badge ' + (snap.is_on_topic ? 'on-topic' : 'off-topic');
    }
    const rStatus = document.getElementById('relevanceStatus');
    if (rStatus) rStatus.innerHTML = snap.is_on_topic
      ? '<span style="color:var(--green)">✓ On Topic</span>'
      : '<span style="color:var(--red)">✗ Off Topic</span>';
    const fc = snap.filler_word_count || 0;
    setText('fillerValue', fc + ' total');
    const pc = snap.long_pause_count || 0;
    setText('pauseValue', pc + ' pauses');
    const fBreakdown = document.getElementById('posFillerBreakdown');
    if (fBreakdown && fc > 0) fBreakdown.innerHTML = '<span class="pos-filler-empty" style="color:var(--text-primary);font-style:normal;">' + fc + ' filler words detected.</span>';
    
    const pChips = document.getElementById('pauseChips');
    if (pChips && pc > 0) pChips.innerHTML = '<span style="font-size:12px;color:var(--text-primary);">' + pc + ' long pauses during speech.</span>';
    const tw = snap.total_word_count || 0;
    setText('wordCount', tw + ' words');
    if (snap.wpm) setText('paceValue', Math.round(snap.wpm) + ' WPM');
    const wpmVal = snap.wpm ? Math.round(snap.wpm) : '—';
    setText('statWords', tw);
    setText('statFillers', fc);
    setText('statPauses', pc);
    setText('statWPM', wpmVal);
    const feedEl = document.getElementById('annotFeedContent');
    if (feedEl) {
      const transcriptHTML = snap.highlighted_transcript || '';
      const plainText = snap.annotated_transcript || snap.transcription || '';
      if (transcriptHTML || plainText) {
        const entry = document.createElement('div');
        entry.className = 'annot-transcript-result';
        entry.style.cssText = 'padding:10px 12px;background:var(--bg-input);border-radius:8px;margin-top:8px;line-height:1.8;font-size:13px;color:var(--text-primary);word-break:break-word;';
        if (transcriptHTML) { entry.innerHTML = transcriptHTML; }
        else { entry.textContent = plainText; }
        feedEl.innerHTML = '';
        feedEl.appendChild(entry);
      }
    }
    const transcript = snap.transcription || snap.annotated_transcript || '';
    
    if (typeof iv2 !== 'undefined' && iv2.waitingForFeedback) {
      iv2.waitingForFeedback = false;
      const finalTranscript = iv2.fullTranscript && iv2.fullTranscript.trim().length > transcript.trim().length 
        ? iv2.fullTranscript.trim() 
        : transcript.trim();
        
      const avg = iv2.scores.length ? Math.round(iv2.scores.reduce((a, b) => a + b, 0) / iv2.scores.length) : Math.round((snap.similarity || 0) * 100);
      const fc = snap.filler_word_count || 0;
      const tw = Math.max(1, snap.total_word_count || 1);
      const fPct = (fc / tw) * 100;
      const sp = Math.round((Math.max(0, 100 - (fPct * 2)) + (snap.wpm && snap.wpm > 100 && snap.wpm < 200 ? 100 - (Math.abs(snap.wpm - 150) / 2) : 50)) / 2) || 75;
      const eyeScore = snap.eye_contact_percentage || 70;
      const postureScore = snap.posture_score || 70;
      const bd = Math.round((eyeScore + postureScore) / 2) || 75;
      const ov = Math.round((avg + sp + bd) / 3);

      fetch(API_URL + '/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_type: 'Interview', overall_score: ov, relevance_score: avg,
          speech_quality: sp, body_language: bd, duration: iv2.timeLeft !== undefined ? 120 - iv2.timeLeft : 60
        })
      }).catch(e => console.error(e));

      const ct = document.getElementById('iv2ReportContent');
      if (ct) {
        const col = ov >= 75 ? 'var(--green)' : ov >= 55 ? 'var(--yellow)' : 'var(--red)';
        ct.innerHTML = '<div class="iv-report-row"><span class="iv-report-label">Overall Score</span><span class="iv-report-score" style="color:' + col + ';font-size:22px;">' + ov + '%</span></div>'
          + '<div class="iv-report-row"><span class="iv-report-label">Answer Relevance</span><span class="iv-report-score" style="color:var(--accent)">' + avg + '%</span></div>'
          + '<div class="iv-report-row"><span class="iv-report-label">Speech Quality</span><span class="iv-report-score" style="color:#6366f1">' + sp + '%</span></div>'
          + '<div class="iv-report-row"><span class="iv-report-label">Body Language</span><span class="iv-report-score" style="color:var(--green)">' + bd + '%</span></div>'
          + '<div class="iv-report-row"><span class="iv-report-label">Questions Answered</span><span class="iv-report-score">' + iv2.scores.length + ' / ' + IV2_QS.length + '</span></div>'
          + '<div id="iv2AiFeedbackSection"><div class="iv2-feedback-loading"><span class="iv2-spinner"></span> Generating AI coaching feedback…</div></div>';
      }

      const question = IV2_QS[iv2.qIdx] || 'Tell me about yourself.';
      const iType = document.getElementById('iv2InterviewType')?.value || 'general';
      if (finalTranscript.length > 10) {
        iv2FetchAIFeedback(question, finalTranscript, iType);
      } else {
        const section = document.getElementById('iv2AiFeedbackSection');
        if (section) section.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">Transcript too short for AI feedback. Please provide an answer next time!</div>';
      }
    }
    
    const topic = snap.confirmed_topic || snap.slide_topic || '';
    const concEl = document.getElementById('concisenessContent');
    if (concEl && transcript.length > 20) {
      concEl.innerHTML = '<div class="iv2-feedback-loading"><span class="iv2-spinner"></span> Generating conciseness feedback…</div>';
      fetch(API_URL + '/practice/conciseness', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript, topic })
      })
      .then(r => r.json())
      .then(d => {
        if (d.ok && d.feedback) {
          const fb = d.feedback;
          concEl.innerHTML =
            '<div class="conciseness-critique">' +
              '<div class="iv2-fb-card-title" style="margin:0 0 6px;"><span>🔍</span> What to Improve</div>' +
              '<p style="color:var(--text-primary);font-size:13px;line-height:1.6;margin:0 0 10px;">' + (fb.critique || '—') + '</p>' +
            '</div>' +
            '<div class="iv2-fb-card iv2-better" style="margin:0;">' +
              '<div class="iv2-fb-card-title"><span>📝</span> You could have said</div>' +
              '<p class="iv2-fb-card-body iv2-better-text">' + (fb.ideal_version || '—') + '</p>' +
            '</div>';
        } else {
          concEl.innerHTML = '<p style="color:var(--text-muted);font-size:12px;">Could not generate feedback.</p>';
        }
      })
      .catch(() => {
        concEl.innerHTML = '<p style="color:var(--text-muted);font-size:12px;">Feedback unavailable.</p>';
      });
    }
    try {
      const log = {
        id: Date.now(), timestamp: Date.now(),
        name: 'Live Session (' + new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) + ')',
        topic: topic || 'Practice',
        duration_s: snap.duration_s || 60,
        relevanceScore: Math.round((snap.similarity || 0) * 100), 
        fillerCount: fc,
        totalWords: tw, wpm: snap.wpm || 0,
        transcript: transcript, filename: null, source: 'live'
      };
      let sessions = JSON.parse(localStorage.getItem('ss_sessions') || '[]');
      sessions.unshift(log);
      localStorage.setItem('ss_sessions', JSON.stringify(sessions.slice(0, 200)));
    } catch(e) { console.error('Error saving session locally:', e); }
    state.lastWSSnap = snap;
    return;
  }
  if (data.similarity !== undefined) {
    if (!data.topic_confirmed) {
      setBar('relevanceBar', 0, '');
      setText('relevancePercent', '0%');
      const badge = document.getElementById('relevanceBadge');
      if (badge) {
        badge.textContent = '—';
        badge.className = 'card-badge';
      }
      const status = document.getElementById('relevanceStatus');
      if (status) status.innerHTML = '<span class="relevance-waiting"><span class="pulsing-dot"></span> Waiting for topic…</span>';
      setText('iv2Relevance', '—');
      setBar('iv2RelevanceBar', 0, '');
    } else {
      const v = Math.round(data.similarity * 100);
      setBar('relevanceBar', v, v > 60 ? 'green' : v > 30 ? 'yellow' : 'red');
      setText('relevancePercent', v + '%');
      const badge = document.getElementById('relevanceBadge');
      if (badge) {
        badge.textContent = v + '%';
        badge.className = 'card-badge ' + (data.is_on_topic ? 'on-topic' : 'off-topic');
      }
      const status = document.getElementById('relevanceStatus');
      if (status) status.innerHTML = data.is_on_topic
        ? '<span style="color:var(--green)">✓ On Topic</span>'
        : '<span style="color:var(--red)">✗ Off Topic</span>';
      setText('iv2Relevance', v + '%');
      setBar('iv2RelevanceBar', v, v > 60 ? 'green' : v > 30 ? 'yellow' : 'red');
    }
  }
  if (data.speech_summary) {
    renderSpeechSummary(data.speech_summary, data.off_topic_spans || [], data.warn_spans || []);
  }
  if (data.latest_transcription && data.latest_transcription !== state.lastTranscription) {
    state.lastTranscription = data.latest_transcription;
    appendAnnotFeed(data.latest_transcription, false);
    if (window.iv2 && window.iv2.active) iv2AppendTranscript(data.latest_transcription);
  }
  if (data.pending_confirmation && data.detected_topic) {
    showTopicDetected(data.detected_topic);
  }
  let derivedSpeechQuality = 0;
  let derivedConfidence = 0;
  if (data.filler_word_count !== undefined) {
    setText('fillerValue', data.filler_word_count + ' total');
    setText('statFillers', data.filler_word_count);
    setText('statWords', data.total_word_count || 0);
    renderPOSFillerBreakdown(data.pos_filler_breakdown || null, data.filler_word_count);

    const fillerPct = Math.min(100, (data.filler_word_count / Math.max(data.total_word_count || 1, 1)) * 100);
    derivedSpeechQuality = Math.max(0, 100 - (fillerPct * 2));
  }
  if (data.long_pause_count !== undefined) {
    setText('pauseValue', data.long_pause_count + ' pauses');
    setText('statPauses', data.long_pause_count);
  }
  if (data.last_pause_duration !== undefined && data.last_pause_duration > 0) {
    renderPauseChips([data.last_pause_duration]);
    if (data.last_pause_duration !== state.lastPauseDuration) {
      state.lastPauseDuration = data.last_pause_duration;
      appendAnnotFeed(null, data.last_pause_duration);
    }
  }
  if (data.pause_preceding_pos) {
    const posRow = document.getElementById('pausePosRow');
    const posChip = document.getElementById('pausePosChip');
    if (posRow) posRow.style.display = 'flex';
    if (posChip) posChip.textContent = humanPOS(data.pause_preceding_pos);
  }
  if (data.wpm !== undefined) {
    setText('paceValue', data.wpm + ' WPM');
    const badge = document.getElementById('paceBadge');
    if (badge) { badge.textContent = data.wpm < 120 ? 'SLOW' : data.wpm > 180 ? 'FAST' : 'GOOD'; }
    const pacePct = Math.min(100, Math.max(0, (data.wpm / 200) * 100));
    setBar('paceBar', pacePct, data.wpm < 120 ? 'yellow' : data.wpm > 180 ? 'red' : 'green');
    const wpmScore = data.wpm < 100 || data.wpm > 200 ? 50 : 100 - (Math.abs(data.wpm - 150) / 2); // 150 = 100, 100 = 75
    derivedSpeechQuality = Math.round((derivedSpeechQuality + wpmScore) / 2);
    setText('iv2Speech', derivedSpeechQuality + '%');
    setBar('iv2SpeechBar', derivedSpeechQuality, derivedSpeechQuality > 70 ? 'green' : 'yellow');
  }
  if (data.eye_contact_percentage !== undefined) {
    const v = Math.round(data.eye_contact_percentage);
    setBar('eyeBar', v, v > 70 ? 'green' : 'yellow');
    setText('eyeValue', v + '%');
    const dot = document.getElementById('eyeDot');
    if (dot) dot.className = 'bm-dot ' + (data.has_eye_contact ? 'green' : 'red');
    const iDot = document.getElementById('iv2EyeDot'), iVal = document.getElementById('iv2EyeVal');
    if (iDot) iDot.className = 'bm-dot ' + (data.has_eye_contact ? 'green' : 'red');
    if (iVal) iVal.textContent = data.has_eye_contact ? 'Good' : 'Poor';

    derivedConfidence = Math.max(0, Math.min(100, v)); // Base confidence on eye contact
  }
  if (data.posture_score !== undefined) {
    const v = Math.round(data.posture_score);
    setBar('postureBar', v, v > 70 ? 'green' : 'yellow');
    setText('postureValue', v + '%');
    const dot = document.getElementById('postureDot');
    if (dot) dot.className = 'bm-dot ' + (data.good_posture ? 'green' : 'yellow');
    const iDot = document.getElementById('iv2PostureDot'), iVal = document.getElementById('iv2PostureVal');
    if (iDot) iDot.className = 'bm-dot ' + (data.good_posture ? 'green' : 'yellow');
    if (iVal) iVal.textContent = data.good_posture ? 'Upright' : 'Slouching';
    derivedConfidence = Math.round((derivedConfidence + v) / 2);
    setText('iv2Confidence', derivedConfidence + '%');
    setBar('iv2ConfidenceBar', derivedConfidence, derivedConfidence > 70 ? 'green' : 'yellow');
  }
  if (data.face_orientation) {
    setText('headValue', data.face_orientation);
    const dot = document.getElementById('headDot');
    if (dot) dot.className = 'bm-dot ' + (data.face_orientation.includes('Good') ? 'green' : 'yellow');
  }
  if (data.hand_gesture) setText('handValue', data.hand_gesture);
  if (data.audio_level !== undefined) {
    updateAudioViz(data.audio_level);
  }
}


function initPresentation() {
  document.getElementById('ptabCoaching')?.addEventListener('click', () => switchPanelTab('coaching'));
  document.getElementById('ptabAnalytics')?.addEventListener('click', () => switchPanelTab('analytics'));

  document.getElementById('startBtn')?.addEventListener('click', togglePresentation);
  document.getElementById('settingsCtrlBtn')?.addEventListener('click', () => showPage('settings'));
  document.getElementById('helpCtrlBtn')?.addEventListener('click', () =>
    showToast('Click ✎ to enter your topic, then click Start', ''));

  // ✎ Topic button — focuses / scrolls to the always-visible manual input
  document.getElementById('topicCtrlBtn')?.addEventListener('click', () => {
    const inp = document.getElementById('manualTopicInput');
    if (inp) { inp.focus(); inp.select(); }
  });

  document.getElementById('applyManualBtn')?.addEventListener('click', applyManualTopic);

  // Also apply topic when user presses Enter in the input box
  document.getElementById('manualTopicInput')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') applyManualTopic();
  });

  document.getElementById('copyTranscriptBtn')?.addEventListener('click', copyTranscript);
  document.getElementById('copyAnnotFeedBtn')?.addEventListener('click', () => {
    const lines = document.querySelectorAll('#annotFeedContent .af-line-text, #annotFeedContent .af-pause-tag');
    navigator.clipboard.writeText(Array.from(lines).map(l => l.textContent).join(' '))
      .then(() => showToast('Feed copied!', 'success'));
  });
  document.getElementById('screenshotBtn')?.addEventListener('click', takeScreenshot);
  document.getElementById('shareBtn')?.addEventListener('click', () => showToast('Link copied!', 'success'));
  document.getElementById('videoMenuBtn')?.addEventListener('click', () => showToast('Video options coming soon', ''));
  document.addEventListener('keydown', handleKeyDown);
}


async function togglePresentation() {
  if (!state.recording) await startPresentation();
  else stopPresentation();
}

async function startPresentation() {
  // 1. Enforce topic selection before starting session (so recordings ONLY happen with a topic)
  const inputEl = document.getElementById('manualTopicInput');
  const typedTopic = inputEl?.value.trim();
  if (typedTopic && !state.topicConfirmed) {
    state.topic = typedTopic;
    state.topicConfirmed = true;
    setText('topicStatusText', 'Topic Locked: ' + state.topic);
    setText('confirmedTopicDisplay', state.topic);
    const dot = document.getElementById('topicStatusDot');
    if (dot) dot.className = 'topic-status-dot green';
  }

  if (!state.topicConfirmed || !state.topic) {
    showToast('Please enter a topic before starting the session.', 'warn');
    inputEl?.focus();
    return;
  }

  hide(document.getElementById('noCamPlaceholder'));

  state.recording = true;
  state.lastTranscription = '';
  state.lastPauseDuration = 0;
  state.sessionSecs = 0;
  state.recordChunks = [];
  state.sessionStartEpoch = Date.now();
  clearInterval(state.sessionInt);
  state.sessionInt = setInterval(() => {
    state.sessionSecs++;
    setText('statDuration', formatTime(state.sessionSecs));
  }, 1000);

  const btn = document.getElementById('startBtn');
  if (btn) { btn.innerHTML = '<span class="start-btn-dot recording"></span> Stop'; btn.classList.add('recording'); }
  const lb = document.getElementById('liveBadge');
  if (lb) lb.style.display = 'flex';
  const tt = document.getElementById('startTooltip');
  if (tt) tt.style.display = 'none';
  setStatusChip('LIVE', 'live');
  const feed = document.getElementById('annotFeedContent');
  if (feed) feed.innerHTML = '';
  appendAnnotFeed('▶ Session started — speak and your words will appear here.', false, true);

  // --- 1. Get camera + mic stream ---
  let stream = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    state.mediaStream = stream;
    // Show live preview in the video element
    const vid = document.getElementById('localVideo');
    if (vid) {
      vid.srcObject = stream;
      vid.style.display = 'block';
    }
  } catch (err) {
    console.warn('[SynthSpeak] getUserMedia failed:', err.message);
    showToast('Camera/mic permission denied — running without video feed', '');
  }

  // --- 2. Connect command WS and tell backend to start ---

  connectWS(() => {
    sendWS({ cmd: 'start' });
    // NOTE: cmd: manual is sent upon receiving the 'start' ack in handleWSMessage,
    // ensuring pipelines are fully initialised before the topic is applied.
  });


  // --- 3. Open /ws/stream and start sending frames + audio ---
  if (stream) {
    try {
      const streamWs = new WebSocket(WS_STREAM_URL);
      state.streamWs = streamWs;
      streamWs.binaryType = 'arraybuffer';

      streamWs.onopen = () => {
        console.log('[SynthSpeak] /ws/stream connected');

        // 3a. Frame capture — draw video to offscreen canvas every 200ms (5fps), send JPEG
        const vid = document.getElementById('localVideo');
        const canvas = document.createElement('canvas');
        canvas.width = 640; canvas.height = 360;
        const ctx = canvas.getContext('2d');

        state.frameInterval = setInterval(async () => {
          if (!vid || vid.readyState < 2) return;
          if (!state.streamWs || state.streamWs.readyState !== WebSocket.OPEN) return;
          try {
            ctx.drawImage(vid, 0, 0, canvas.width, canvas.height);
            const blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.7));
            if (!blob) return;
            const ab = await blob.arrayBuffer();
            const header = new TextEncoder().encode('{"type":"frame"}\n');
            const merged = new Uint8Array(header.byteLength + ab.byteLength);
            merged.set(header, 0);
            merged.set(new Uint8Array(ab), header.byteLength);
            state.streamWs.send(merged.buffer);
          } catch (e) { /* ignore single-frame errors */ }
        }, 200); // 5fps — server drops frames it can't keep up with

        // 3b. Audio capture — ScriptProcessorNode → PCM float32 → /ws/stream
        try {
          const audioCtx = new AudioContext({ sampleRate: 16000 });
          state.audioContext = audioCtx;
          const micSource = audioCtx.createMediaStreamSource(stream);
          const processor = audioCtx.createScriptProcessor(4096, 1, 1);
          processor.onaudioprocess = (e) => {
            if (!state.streamWs || state.streamWs.readyState !== WebSocket.OPEN) return;
            const pcm = e.inputBuffer.getChannelData(0); // Float32Array
            const header = new TextEncoder().encode('{"type":"audio"}\n');
            const pcmBytes = new Uint8Array(pcm.buffer);
            const merged = new Uint8Array(header.byteLength + pcmBytes.byteLength);
            merged.set(header, 0);
            merged.set(pcmBytes, header.byteLength);
            state.streamWs.send(merged.buffer);
          };
          micSource.connect(processor);
          processor.connect(audioCtx.destination);
        } catch (ae) {
          console.warn('[SynthSpeak] Audio worklet unavailable:', ae.message);
        }
      };

      streamWs.onerror = (e) => console.warn('[SynthSpeak] /ws/stream error', e);
    } catch (e) {
      console.warn('[SynthSpeak] Could not open /ws/stream:', e);
    }
  }

  // --- 4. MediaRecorder for session archive (audio only blob upload) ---
  try {
    const audioOnly = stream
      ? new MediaStream(stream.getAudioTracks())
      : await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    const mr = new MediaRecorder(audioOnly, { mimeType: 'audio/webm' });
    mr.ondataavailable = e => { if (e.data && e.data.size > 0) state.recordChunks.push(e.data); };
    mr.start(1000);
    state.mediaRecorder = mr;
  } catch (err) {
    console.warn('[SynthSpeak] MediaRecorder unavailable:', err.message);
    state.mediaRecorder = null;
  }

  showToast('Recording started!', 'success');
}

function stopPresentation() {
  const snap = state.lastWSSnap || {};   // capture metrics before resetting

  state.recording = false;
  clearInterval(state.sessionInt);
  clearInterval(state.frameInterval);
  state.frameInterval = null;

  // Stop /ws/stream
  if (state.streamWs) {
    try { state.streamWs.close(); } catch(e) {}
    state.streamWs = null;
  }

  // Stop AudioContext
  if (state.audioContext) {
    try { state.audioContext.close(); } catch(e) {}
    state.audioContext = null;
  }

  // Stop camera/mic tracks
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach(t => t.stop());
    state.mediaStream = null;
  }
  const vid = document.getElementById('localVideo');
  if (vid) { vid.srcObject = null; }
  show(document.getElementById('noCamPlaceholder'));
  const btn = document.getElementById('startBtn');
  if (btn) { btn.innerHTML = '<span class="start-btn-dot"></span> Start'; btn.classList.remove('recording'); }
  const lb = document.getElementById('liveBadge');
  if (lb) lb.style.display = 'none';
  const tt = document.getElementById('startTooltip');
  if (tt && state.currentPage === 'presentation') tt.style.display = 'flex';
  setStatusChip('IDLE', '');
  sendWS({ cmd: 'stop' });
  appendAnnotFeed('⏹ Session stopped.', false, true);
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.onstop = async () => {
      const blob = new Blob(state.recordChunks, { type: 'audio/webm' });
      state.recordChunks = [];
      let filename = null;
      try {
        const fd = new FormData();
        fd.append('file', blob, `session_${Date.now()}.webm`);
        const r = await fetch(API_URL + '/recordings/upload', { method: 'POST', body: fd });
        const d = await r.json();
        filename = d.filename || null;
      } catch (err) {
        console.warn('[SynthSpeak] Upload failed:', err.message);
      }
      saveSessionLog(snap, filename);
    };
    state.mediaRecorder.stop();
    state.mediaRecorder.stream?.getTracks().forEach(t => t.stop());
    state.mediaRecorder = null;
  } else {
    saveSessionLog(snap, null);
  }

  showToast('Session saved!', 'success');
}
function saveSessionLog(snap, filename) {
  const durationMins = Math.round(state.sessionSecs / 60 * 10) / 10;
  const log = {
    id: Date.now(),
    date: new Date(state.sessionStartEpoch).toLocaleString(),
    topic: state.topic || (snap.confirmed_topic) || 'Unknown',
    type: 'Presentation',
    durationSecs: state.sessionSecs,
    durationLabel: formatTime(state.sessionSecs),
    relevanceScore: snap.similarity != null ? Math.round(snap.similarity * 100) : null,
    fillerCount: snap.filler_word_count || 0,
    totalWords: snap.total_word_count || 0,
    wpm: snap.wpm || 0,
    pauseCount: snap.long_pause_count || 0,
    transcript: snap.transcription || '',
    filename: filename,
    source: 'live',
  };
  try {
    const sessions = JSON.parse(localStorage.getItem('ss_sessions') || '[]');
    sessions.unshift(log);           // newest first
    if (sessions.length > 200) sessions.length = 200;   // cap history
    localStorage.setItem('ss_sessions', JSON.stringify(sessions));
  } catch (e) {
    console.warn('[SynthSpeak] Could not save session log:', e);
  }
  if (state.currentPage === 'recordings') loadRecordings();
}

function setStatusChip(label, cls) {
  const dot = document.getElementById('statusDot');
  const lbl = document.getElementById('statusLabel');
  const chip = document.getElementById('statusChip');
  if (lbl) lbl.textContent = label;
  if (dot) dot.className = 'status-dot' + (cls ? ' ' + cls : '');
  if (chip) chip.className = 'status-chip' + (cls ? ' ' + cls : '');
}

function appendTranscript(text, type) {
  if (type === 'system') return; // system messages shown only in annot feed
}

function switchTranscriptTab(tab) {
}

function copyTranscript() {
  const lines = document.querySelectorAll('#annotFeedContent .af-line-text');
  navigator.clipboard.writeText(Array.from(lines).map(l => l.textContent).join('\n'))
    .then(() => showToast('Transcript copied!', 'success'));
}
const _avbBars = () => Array.from(document.querySelectorAll('#audioVizBars .avb'));
let _vizParticles = Array(12).fill(4); // heights for each bar (px)

function updateAudioViz(level) {
  const bars = _avbBars();
  if (!bars.length) return;

  const BAR_MAX = 22; // max height (matches .audio-viz-bars height)
  _vizParticles = _vizParticles.map((h, i) => {
    const target = Math.max(3, Math.round(level * BAR_MAX * (0.5 + Math.random() * 0.8)));
    return Math.round(h * 0.6 + target * 0.4);
  });
  bars.forEach((bar, i) => {
    const h = _vizParticles[i] || 4;
    bar.style.height = h + 'px';
    bar.className = 'avb ' + (level > 0.75 ? 'peak' : level > 0.3 ? 'medium' : 'low');
  });

  const pct = Math.round(level * 100);
  const lvlEl = document.getElementById('audioVizLevel');
  if (lvlEl) {
    lvlEl.textContent = pct + '%';
    lvlEl.style.color = level > 0.75 ? '#ef4444' : level > 0.3 ? '#f97316' : '#22c55e';
  }
}
/**
 * Levenshtein distance for fuzzy matching (pure JS, no deps).
 * Returns edit distance between two strings.
 */
function _levenshtein(a, b) {
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, (_, i) =>
    Array.from({ length: n + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0))
  );
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
  return dp[m][n];
}

/**
 * Given a word and the confirmed topic keywords, return
 * { lowConf: bool, suggestion: string|null }
 *  - lowConf: word is phonetically close to a topic keyword but doesn't match
 *  - suggestion: the matching topic keyword (for the correction pill)
 */
function _checkLowConf(word, topicKeywords) {
  const w = word.toLowerCase().replace(/[^a-z]/g, '');
  if (w.length < 3) return { lowConf: false, suggestion: null };
  if (FILLER_WORDS.has(w)) return { lowConf: false, suggestion: null };

  for (const kw of topicKeywords) {
    const k = kw.toLowerCase();
    if (k.length < 3) continue;
    if (w === k) return { lowConf: false, suggestion: null }; // exact match → fine
    const dist = _levenshtein(w, k);
    const threshold = Math.max(1, Math.floor(k.length * 0.35)); // 35% of keyword length
    if (dist <= threshold && dist > 0) {
      return { lowConf: true, suggestion: kw };
    }
  }
  return { lowConf: false, suggestion: null };
}

/**
 * Get topic keywords from the current confirmed topic text.
 * Cached per topic string.
 */
const _topicKwCache = { topic: '', kws: [] };
function _getTopicKeywords() {
  const topic = (state.topic || '').trim();
  if (!topic) return [];
  if (_topicKwCache.topic === topic) return _topicKwCache.kws;
  const stops = new Set(['the', 'a', 'an', 'in', 'of', 'for', 'to', 'and', 'or', 'is', 'are', 'was', 'were', 'with', 'by', 'on', 'at', 'from']);
  const kws = topic.split(/\s+/).map(w => w.replace(/[^a-zA-Z]/g, '')).filter(w => w.length >= 3 && !stops.has(w.toLowerCase()));
  _topicKwCache.topic = topic;
  _topicKwCache.kws = kws;
  return kws;
}
const FILLER_WORDS = new Set([
  'uh', 'um', 'uhh', 'umm', 'like', 'you know', 'basically', 'literally',
  'actually', 'right', 'okay', 'so', 'well', 'i mean', 'kind of', 'sort of',
  'anyway', 'honestly', 'seriously', 'you see', 'obviously'
]);

/**
 * Append an entry to the Live Annotated Feed.
 * @param {string|null} text        Spoken text (null if this is a pause-only event)
 * @param {number|false} pauseSecs  Pause duration in seconds (or false/0 for none)
 * @param {boolean}      isSystem   If true, renders as a muted system line
 */
function appendAnnotFeed(text, pauseSecs, isSystem = false) {
  const feed = document.getElementById('annotFeedContent');
  if (!feed) return;

  const now = new Date().toTimeString().slice(0, 5);
  if (pauseSecs && pauseSecs > 0 && !text) {
    const tag = document.createElement('span');
    tag.className = 'af-pause-tag';
    tag.textContent = '(' + pauseSecs + 's pause)';
    const lastLine = feed.querySelector('.af-line:last-of-type .af-line-body');
    if (lastLine) {
      lastLine.appendChild(document.createTextNode(' '));
      lastLine.appendChild(tag);
    } else {
      const wrap = document.createElement('div');
      wrap.className = 'af-line af-pause-line';
      wrap.appendChild(tag);
      feed.appendChild(wrap);
    }
    feed.scrollTop = feed.scrollHeight;
    return;
  }

  if (!text) return;
  const hasFiller = Array.from(FILLER_WORDS).some(w => {
    const re = new RegExp('\\b' + w.replace(/\s+/g, '\\s+') + '\\b', 'i');
    return re.test(text);
  });
  const topicKws = _getTopicKeywords();
  const words = text.split(/(\s+)/);
  let htmlBody = '';
  let sortedFillers = Array.from(FILLER_WORDS).sort((a, b) => b.length - a.length);
  let processedText = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  if (hasFiller) {
    sortedFillers.forEach(w => {
      const re = new RegExp('\\b(' + w.replace(/\s+/g, '\\s+') + ')\\b', 'gi');
      processedText = processedText.replace(re, '<mark class="af-filler">$1</mark>');
    });
  }
  if (topicKws.length > 0 && !isSystem) {
    processedText = processedText.replace(/(?<![<\w])([A-Za-z]{3,})(?![^<]*>)/g, (match) => {
      const { lowConf, suggestion } = _checkLowConf(match, topicKws);
      if (lowConf && suggestion) {
        return `<mark class="af-lowconf" title="Possible ASR error — did you mean '${suggestion}'?">${match}</mark><mark class="af-correction" title="Suggested: ${suggestion}">→ ${suggestion}</mark>`;
      }
      return match;
    });
  }
  const line = document.createElement('div');
  line.className = 'af-line' + (isSystem ? ' af-system' : '') + (hasFiller ? ' af-has-filler' : '');

  line.innerHTML =
    '<span class="af-time">' + now + '</span>' +
    '<span class="af-line-body">' +
    '<span class="af-line-text">' + processedText + '</span>' +
    '</span>';

  feed.appendChild(line);
  while (feed.children.length > 300) feed.removeChild(feed.firstChild);
  feed.scrollTop = feed.scrollHeight;
}




function scanSlide() {
  sendWS({ cmd: 'scan' });
  setText('topicStatusText', 'Scanning...');
  showToast('Scanning slide...', '');
}

function showTopicDetected(topic) {
  setText('detectedTopicText', topic);
  show(document.getElementById('topicConfirmBar'));
  hide(document.getElementById('manualEntryBar'));
}

function confirmTopic() {
  const txt = document.getElementById('detectedTopicText')?.textContent || '';
  if (!txt || txt === '—') return;
  state.topic = txt; state.topicConfirmed = true;
  hide(document.getElementById('topicConfirmBar'));
  sendWS({ cmd: 'confirm' });
  setText('topicStatusText', 'Topic Locked: ' + txt);
  setText('confirmedTopicDisplay', txt);
  const dot = document.getElementById('topicStatusDot');
  if (dot) dot.className = 'topic-status-dot green';
  showToast('Topic locked: ' + txt, 'success');
}

function applyManualTopic() {
  const input = document.getElementById('manualTopicInput');
  const topic = input?.value.trim();
  if (!topic) { showToast('Please enter a topic first.', 'warn'); input?.focus(); return; }
  // Keep the input value visible so the user can see what topic is active
  state.topic = topic; state.topicConfirmed = true;
  sendWS({ cmd: 'manual', topic });
  setText('topicStatusText', 'Topic Locked: ' + topic);
  setText('confirmedTopicDisplay', topic);
  const dot = document.getElementById('topicStatusDot');
  if (dot) dot.className = 'topic-status-dot green';
  // Highlight the input briefly to confirm
  if (input) { input.style.outline = '2px solid var(--green)'; setTimeout(() => { input.style.outline = ''; }, 1200); }
  showToast('Topic set: ' + topic, 'success');
}

function renderTips(tips) {
  const list = document.getElementById('tipsList');
  if (!list) return;
  list.innerHTML = tips.slice(0, 5).map(t =>
    '<div class="tip-item"><span class="tip-icon">💡</span><span class="tip-text">' + t + '</span></div>'
  ).join('');
}

function renderPauseChips(pauses) {
  const chips = document.getElementById('pauseChips');
  if (!chips) return;
  chips.innerHTML = pauses.slice(0, 5).map(p => '<span class="pause-chip">' + p + 's</span>').join('');
}
const POS_LABELS = {
  CC: 'Conjunction', CD: 'Numeral', DT: 'Determiner',
  EX: 'Existential', FW: 'Foreign Word', IN: 'Preposition',
  JJ: 'Adjective', JJR: 'Adj (comp)', JJS: 'Adj (super)',
  MD: 'Modal', NN: 'Noun', NNS: 'Noun (pl)',
  NNP: 'Proper Noun', NNPS: 'Proper Noun (pl)',
  PDT: 'Pre-determiner', POS: 'Possessive',
  PRP: 'Pronoun', 'PRP$': 'Poss. Pronoun',
  RB: 'Adverb', RBR: 'Adverb (comp)', RBS: 'Adverb (super)',
  RP: 'Particle', SYM: 'Symbol', TO: 'to',
  UH: 'Interjection', VB: 'Verb', VBD: 'Verb (past)',
  VBG: 'Verb (gerund)', VBN: 'Verb (part)', VBP: 'Verb (pres)',
  VBZ: 'Verb (3sg)', WDT: 'Wh-Det', WP: 'Wh-Pronoun',
  'WP$': 'Wh-Poss', WRB: 'Wh-Adverb',
  VERB: 'Verb', NOUN: 'Noun', PROPN: 'Proper Noun',
  ADJ: 'Adjective', ADV: 'Adverb', ADP: 'Preposition',
  CONJ: 'Conjunction', CCONJ: 'Coord. Conj', SCONJ: 'Sub. Conj',
  DET: 'Determiner', INTJ: 'Interjection', NUM: 'Numeral',
  PART: 'Particle', PRON: 'Pronoun', PUNCT: 'Punctuation',
  SPACE: 'Space', SYM: 'Symbol', X: 'Other',
};

function humanPOS(tag) {
  return POS_LABELS[tag] || tag;
}

/**
 * Render the POS filler breakdown list.
 * @param {Object|null} breakdown  e.g. { UH: 10, CC: 4 }
 * @param {number}      total      fallback total count
 */
function renderPOSFillerBreakdown(breakdown, total) {
  const el = document.getElementById('posFillerBreakdown');
  if (!el) return;

  if (!breakdown || Object.keys(breakdown).length === 0) {
    if (total > 0) {
      el.innerHTML = `<span class="pos-filler-item">All types <span class="pos-filler-item-count">${total}</span></span>`;
    } else {
      el.innerHTML = '<span class="pos-filler-empty">No fillers detected yet</span>';
    }
    return;
  }
  const entries = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);
  el.innerHTML = entries.map(([tag, count]) =>
    `<span class="pos-filler-item">${humanPOS(tag)} <span class="pos-filler-item-count">${count}</span></span>`
  ).join('');
}

/**
 * Render the dynamic speech summary with heatmap highlights.
 * @param {string}   summary        Plain-text summary sentence(s)
 * @param {string[]} offTopicSpans  Substrings to mark red
 * @param {string[]} warnSpans      Substrings to mark yellow
 */
function renderSpeechSummary(summary, offTopicSpans, warnSpans) {
  const box = document.getElementById('speechSummaryBox');
  if (!box) return;
  if (!summary) {
    box.innerHTML = '<span class="summary-placeholder">Start speaking to generate a live summary…</span>';
    return;
  }
  let html = summary
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const sortedOff = [...(offTopicSpans || [])].sort((a, b) => b.length - a.length);
  sortedOff.forEach(span => {
    if (!span) return;
    const escaped = span.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    html = html.replace(new RegExp(escaped, 'gi'),
      m => `<mark class="sum-off-topic">${m}</mark>`);
  });
  const sortedWarn = [...(warnSpans || [])].sort((a, b) => b.length - a.length);
  sortedWarn.forEach(span => {
    if (!span) return;
    const escaped = span.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    html = html.replace(new RegExp(escaped, 'gi'),
      m => `<mark class="sum-warn">${m}</mark>`);
  });

  box.innerHTML = html;
  box.scrollTop = box.scrollHeight;
}

function setMode(mode) {
  document.getElementById('modeAuto')?.classList.toggle('active', mode === 'auto');
  document.getElementById('modeManual')?.classList.toggle('active', mode === 'manual');
  sendWS({ cmd: 'mode', mode });
}

function takeScreenshot() {
  const vid = document.getElementById('webcamFeed');
  if (!vid || !vid.srcObject) { showToast('No active camera.', 'warn'); return; }
  const c = document.createElement('canvas');
  c.width = vid.videoWidth; c.height = vid.videoHeight;
  c.getContext('2d').drawImage(vid, 0, 0);
  const a = document.createElement('a');
  a.href = c.toDataURL('image/png');
  a.download = 'synthspeak_' + Date.now() + '.png';
  a.click();
  showToast('Screenshot saved!', 'success');
}

function handleKeyDown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (state.currentPage !== 'presentation') return;
  switch (e.key.toUpperCase()) {
    case ' ': case 'S': e.preventDefault(); togglePresentation(); break;
    case 'O': scanSlide(); break;
    case 'C': confirmTopic(); break;
    case 'R': scanSlide(); break;
    case 'M': document.getElementById('manualEntryBar')?.classList.toggle('hidden'); break;
    case 'H': showToast('Space/S=Start  O=Scan  C=Confirm  M=Manual  R=Rescan', ''); break;
  }
}
let recordingsData = [];
let activeRecFilter = 'all';
function _mergeRecordings(serverList, sessions) {
  const byFile = {};
  sessions.forEach(s => { if (s.filename) byFile[s.filename] = s; });
  const enriched = serverList.map(rec => {
    const log = byFile[rec.filename];
    if (log) return { ...rec, ...log, _hasLog: true };
    return rec;
  });
  sessions.forEach(s => {
    if (!s.filename || !serverList.find(r => r.filename === s.filename)) {
      enriched.unshift({ ...s, _hasLog: true, _localOnly: true });
    }
  });
  return enriched;
}

async function loadRecordings() {
  let serverFiles = [];
  try {
    const r = await fetch(API_URL + '/recordings');
    const d = await r.json();
    serverFiles = d.recordings || [];
  } catch { serverFiles = []; }

  let sessions = [];
  try { sessions = JSON.parse(localStorage.getItem('ss_sessions') || '[]'); } catch { sessions = []; }

  recordingsData = _mergeRecordings(serverFiles, sessions);
  renderRecordings(recordingsData);
  updateRecStats(recordingsData);
}

function renderRecordings(list) {
  const cont = document.getElementById('recordingsList');
  const empty = document.getElementById('recordingsEmpty');
  if (!cont) return;
  cont.querySelectorAll('.recording-card').forEach(c => c.remove());
  const filtered = activeRecFilter === 'all' ? list
    : list.filter(r => (r.type || '').toLowerCase() === activeRecFilter);
  if (!filtered.length) { show(empty); return; }
  hide(empty);

  filtered.forEach(rec => {
    const card = document.createElement('div');
    card.className = 'recording-card' + (rec._hasLog ? ' rich' : '');

    const name = rec.topic || rec.filename || rec.name || 'Recording';
    const date = rec.date || rec.created_at || '';
    const dur = rec.durationLabel || (rec.duration_s ? formatTime(Math.round(rec.duration_s)) : '');
    const score = rec.relevanceScore != null ? rec.relevanceScore : null;
    const scoreBadge = score != null
      ? `<span class="rec-score-badge ${score >= 70 ? 'good' : score >= 40 ? 'warn' : 'bad'}">${score}% Relevance</span>`
      : '';
    const qualityChips = rec._hasLog ? `
      <div class="rec-quality-chips">
        ${rec.fillerCount > 0 ? `<span class="rec-chip">💬 ${rec.fillerCount} fillers</span>` : ''}
        ${rec.wpm ? `<span class="rec-chip">⚡ ${Math.round(rec.wpm)} WPM</span>` : ''}
        ${rec.pauseCount ? `<span class="rec-chip">⏸ ${rec.pauseCount} pauses</span>` : ''}
        ${rec.totalWords ? `<span class="rec-chip">📝 ${rec.totalWords} words</span>` : ''}
      </div>` : '';

    const hasAudio = !rec._localOnly && rec.url;
    const transcriptSection = (rec.transcript && rec.transcript.length > 0) ? `
      <details class="rec-transcript-details">
        <summary>📄 Transcript</summary>
        <div class="rec-transcript-text">${rec.transcript.replace(/</g, '&lt;')}</div>
      </details>` : '';

    card.innerHTML = `
      <div class="rec-thumb">${rec._hasLog ? '📊' : '🎙'}</div>
      <div class="rec-info">
        <div class="rec-name">${name}</div>
        <div class="rec-meta">
          <span class="rec-tag">${rec.type || 'Presentation'}</span>
          <span>${date}</span>
          ${dur ? `<span>⏱ ${dur}</span>` : ''}
          ${scoreBadge}
        </div>
        ${qualityChips}
        ${transcriptSection}
      </div>
      <div class="rec-actions">
        ${hasAudio ? '<button title="Play" class="icon-btn">▶</button>' : ''}
        ${hasAudio ? '<button title="Download" class="icon-btn">⬇</button>' : ''}
        <button title="Delete" class="icon-btn">🗑</button>
      </div>`;

    if (hasAudio) {
      card.querySelector('[title="Play"]')?.addEventListener('click', () => {
        new Audio(API_URL + rec.url).play(); showToast('Playing...', '');
      });
      card.querySelector('[title="Download"]')?.addEventListener('click', () => {
        const a = document.createElement('a'); a.href = API_URL + rec.url;
        a.download = rec.filename || 'rec.webm'; a.click();
      });
    }
    card.querySelector('[title="Delete"]')?.addEventListener('click', async () => {
      if (!confirm('Delete this recording?')) return;
      try {
        const sessions = JSON.parse(localStorage.getItem('ss_sessions') || '[]');
        const updated = sessions.filter(s => s.id !== rec.id && s.filename !== rec.filename);
        localStorage.setItem('ss_sessions', JSON.stringify(updated));
      } catch { }
      if (hasAudio) {
        try { await fetch(API_URL + '/recordings/' + rec.filename, { method: 'DELETE' }); } catch { }
      }
      await loadRecordings();
      showToast('Deleted.', 'success');
    });
    cont.appendChild(card);
  });
}

function updateRecStats(list) {
  setText('recStatCount', list.length);
  const totalSecs = list.reduce((s, r) => s + (r.durationSecs || parseFloat(r.duration_s) || 0), 0);
  setText('recStatDuration', totalSecs >= 60 ? Math.round(totalSecs / 60) + 'm' : Math.round(totalSecs) + 's');
  const scored = list.filter(r => r.relevanceScore != null);
  setText('recStatAvgScore', scored.length
    ? Math.round(scored.reduce((s, r) => s + r.relevanceScore, 0) / scored.length) + '%'
    : '--');
  setText('recStatType', list.length ? (list[0].type || '--') : '--');
}

function initRecordingsPage() {
  document.getElementById('recSearchInput')?.addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    renderRecordings(recordingsData.filter(r =>
      (r.topic || r.filename || r.name || '').toLowerCase().includes(q)
    ));
  });
  document.getElementById('refreshRecordingsBtn')?.addEventListener('click', loadRecordings);
  document.getElementById('recFilterTabs')?.addEventListener('click', e => {
    const btn = e.target.closest('.rec-ftab');
    if (!btn) return;
    document.querySelectorAll('.rec-ftab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeRecFilter = btn.dataset.filter || 'all';
    renderRecordings(recordingsData);
  });
  initUploadZone();
}
function initUploadZone() {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('uploadFileInput');
  const topicI = document.getElementById('uploadTopicInput');
  const btn = document.getElementById('analyzeUploadBtn');
  const result = document.getElementById('uploadResult');
  if (!zone || !input || !btn) return;
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) { input.files = e.dataTransfer.files; updateZoneLabel(input.files[0].name); }
  });
  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', () => { if (input.files[0]) updateZoneLabel(input.files[0].name); });

  function updateZoneLabel(name) {
    const lbl = document.getElementById('uploadZoneLabel');
    if (lbl) lbl.textContent = '📎 ' + name;
  }

  btn.addEventListener('click', async () => {
    const file = input.files[0];
    const topic = topicI?.value.trim() || '';
    if (!file) { showToast('Please select a .wav or .mp3 file.', 'warn'); return; }
    if (!topic) { showToast('Please enter a topic name.', 'warn'); return; }

    btn.disabled = true;
    btn.textContent = '⏳ Analyzing…';
    if (result) result.innerHTML = '<div class="upload-result-loading"><div class="spinner"></div><span>Running Whisper + Relevance engine…</span></div>';

    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('topic', topic);
      const r = await fetch(API_URL + '/analyze-upload', { method: 'POST', body: fd });
      const d = await r.json();

      if (!d.ok) throw new Error(d.error || 'Analysis failed');

      const pct = Math.round((d.similarity || 0) * 100);
      const scoreClass = pct >= 70 ? 'good' : pct >= 40 ? 'warn' : 'bad';
      const fillerPct = d.filler_pct || 0;
      const speechClass = fillerPct < 5 ? 'good' : fillerPct < 15 ? 'warn' : 'bad';

      if (result) result.innerHTML = `
        <div class="upload-result-card">
          <div class="urc-header">
            <span class="urc-title">📊 Post-Session Report</span>
            <span class="urc-topic">Topic: ${topic}</span>
          </div>
          <div class="urc-metrics">
            <div class="urc-metric">
              <div class="urc-metric-val ${scoreClass}">${pct}%</div>
              <div class="urc-metric-lbl">Relevance Score</div>
            </div>
            <div class="urc-metric">
              <div class="urc-metric-val">${d.total_words || 0}</div>
              <div class="urc-metric-lbl">Total Words</div>
            </div>
            <div class="urc-metric">
              <div class="urc-metric-val ${speechClass}">${d.filler_count || 0}</div>
              <div class="urc-metric-lbl">Filler Words</div>
            </div>
            <div class="urc-metric">
              <div class="urc-metric-val">${d.wpm || 0}</div>
              <div class="urc-metric-lbl">Est. WPM</div>
            </div>
          </div>
          ${d.transcript ? `
          <details class="urc-transcript">
            <summary>📄 Full Transcript</summary>
            <div class="urc-transcript-text">${d.transcript.replace(/</g, '&lt;')}</div>
          </details>` : ''}
          <div class="urc-on-topic ${d.is_on_topic ? 'good' : 'bad'}">
            ${d.is_on_topic ? '✅ ON TOPIC' : '⚠️ OFF TOPIC — refocus on "' + topic + '"'}
          </div>
        </div>`;
      const log = {
        id: Date.now(), date: new Date().toLocaleString(), topic,
        type: 'Uploaded', durationSecs: d.duration_s,
        durationLabel: formatTime(Math.round(d.duration_s || 0)),
        relevanceScore: pct, fillerCount: d.filler_count || 0,
        totalWords: d.total_words || 0, wpm: d.wpm || 0,
        transcript: d.transcript || '', filename: null, source: 'upload',
      };
      const sessions = JSON.parse(localStorage.getItem('ss_sessions') || '[]');
      sessions.unshift(log);
      localStorage.setItem('ss_sessions', JSON.stringify(sessions.slice(0, 200)));
      loadRecordings();

    } catch (err) {
      if (result) result.innerHTML = `<div class="upload-result-error">❌ ${err.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = '🔍 Analyze';
    }
  });
}
let apiKeysData = [];

async function loadApiKeys() {
  try {
    const r = await fetch(API_URL + '/api/keys');
    const d = await r.json();
    apiKeysData = d.keys || [];
  } catch { apiKeysData = []; }
  renderApiKeys(apiKeysData);
  updateApiStats(apiKeysData);
}

function renderApiKeys(keys) {
  const table = document.getElementById('apiKeysTable');
  if (!table) return;
  if (!keys.length) { table.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:20px;">No API keys yet</td></tr>'; return; }
  table.innerHTML = keys.map(k =>
    '<tr><td style="font-family:monospace;font-size:11px;">' + (k.key || '').slice(0, 16) + '...</td>'
    + '<td>' + (k.use_case || '--') + '</td><td>' + (k.company || '--') + '</td>'
    + '<td>' + (k.created || '--') + '</td>'
    + '<td><span class="api-status-badge">' + (k.status || 'Active') + '</span></td></tr>'
  ).join('');
}

function updateApiStats(keys) {
  setText('apiStatKeys', keys.length);
  setText('apiStatCalls', keys.reduce((s, k) => s + (parseInt(k.calls) || 0), 0));
  setText('apiStatCompanies', new Set(keys.map(k => k.company).filter(Boolean)).size);
}

function initApiKeyPage() {
  document.getElementById('generateApiKeyBtn')?.addEventListener('click', async () => {
    const uc = document.getElementById('apiUseCaseInput')?.value.trim();
    const co = document.getElementById('apiCompanyInput')?.value.trim();
    const em = document.getElementById('apiEmailInput')?.value.trim();
    if (!co) { showToast('Enter a company name.', 'warn'); return; }
    let key;
    try {
      const r = await fetch(API_URL + '/api/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_case: uc, company: co, email: em }),
      });
      const d = await r.json();
      key = d.api_key || d.key;
    } catch {
      key = 'SS-' + Math.random().toString(36).slice(2, 18).toUpperCase();
    }
    setText('generatedApiKey', key);
    show(document.getElementById('apiKeyResult'));
    showToast('API key generated!', 'success');
    loadApiKeys();
  });

  document.getElementById('copyApiKeyBtn')?.addEventListener('click', () => {
    const key = document.getElementById('generatedApiKey')?.textContent;
    if (key) navigator.clipboard.writeText(key).then(() => showToast('Key copied!', 'success'));
  });
}
function initSettingsPage() {
  document.getElementById('saveSettingsBtn')?.addEventListener('click', () => {
    const settings = {};
    document.querySelectorAll('#pageSettings input,#pageSettings select').forEach(el => {
      if (el.id) settings[el.id] = el.type === 'checkbox' ? el.checked : el.value;
    });
    localStorage.setItem('synthspeak_settings', JSON.stringify(settings));
    showToast('Settings saved!', 'success');
  });
  try {
    const saved = JSON.parse(localStorage.getItem('synthspeak_settings') || '{}');
    Object.entries(saved).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (el.type === 'checkbox') el.checked = val; else el.value = val;
    });
  } catch { }
}
const iv2 = {
  active: false, qIdx: 0, scores: [], timeLeft: 120,
  timerInt: null, simInt: null, stream: null,
};
const IV2_QS = [
  'Tell me about yourself and your background.',
  'What are your greatest strengths?',
  'Describe a challenging project and how you handled it.',
  'Why do you want to work at this company?',
  'Where do you see yourself in 5 years?',
];
const IV2_DESC = {
  general: 'Interview evaluating communication, teamwork, and cultural fit.',
  technical: 'Technical evaluation covering algorithms, system design, and domain knowledge.',
  behavioral: 'STAR-format questions assessing past behaviour and real scenarios.',
  hr: 'HR round assessing career goals, culture fit, and compensation expectations.',
  case: 'Case study interview: analyse a business problem and propose a solution.',
};
const IV2_RUBRIC = {
  general: [['Actively listen', 'Respond thoughtfully and acknowledge key points.'], ['Use the STAR method', 'Situation, Task, Action, Result.'], ['Clear articulation', 'Speak clearly with minimal filler words.']],
  technical: [['Problem breakdown', 'Break into tractable parts.'], ['Complexity awareness', 'Discuss Big-O tradeoffs.'], ['Code clarity', 'Write readable, efficient code.']],
  behavioral: [['STAR structure', 'Use STAR for every answer.'], ['Specific examples', 'Use real examples.'], ['Outcome focus', 'State the result of your actions.']],
  hr: [['Honesty', 'Be authentic.'], ['Company alignment', 'Show interest in the mission.'], ['Confidence', 'Speak with confidence.']],
  case: [['Structured thinking', 'Lay out a framework first.'], ['Data-driven reasoning', 'Back with data.'], ['Clear recommendation', 'Close with a recommendation.']],
};

function initInterview() {
  document.getElementById('iv2TabSetup')?.addEventListener('click', () => {
    document.getElementById('iv2TabSetup')?.classList.add('active');
    document.getElementById('iv2TabQuestions')?.classList.remove('active');
    show(document.getElementById('iv2SetupContent'));
    hide(document.getElementById('iv2QuestionsContent'));
  });
  document.getElementById('iv2TabQuestions')?.addEventListener('click', () => {
    document.getElementById('iv2TabQuestions')?.classList.add('active');
    document.getElementById('iv2TabSetup')?.classList.remove('active');
    show(document.getElementById('iv2QuestionsContent'));
    hide(document.getElementById('iv2SetupContent'));
  });
  document.getElementById('iv2ToneSelect')?.addEventListener('change', e => {
    const b = document.getElementById('iv2ToneBadge');
    if (b) { b.className = 'iv2-tone-badge ' + e.target.value; b.textContent = e.target.value.toUpperCase(); }
  });
  document.getElementById('iv2InterviewType')?.addEventListener('change', e => {
    const t = e.target.value;
    const d = document.getElementById('iv2Description');
    if (d) d.textContent = IV2_DESC[t] || IV2_DESC.general;
    const r = document.getElementById('iv2RubricList');
    if (r) r.innerHTML = (IV2_RUBRIC[t] || []).map(([ti, h]) =>
      '<div class="iv2-rubric-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>'
      + '<div><div class="iv2-rubric-title">' + ti + '</div><div class="iv2-rubric-hint">' + h + '</div></div></div>'
    ).join('');
  });
  document.getElementById('iv2AllowBtn')?.addEventListener('click', async () => {
    try {
      iv2.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      const vid = document.getElementById('iv2VideoEl');
      if (vid) vid.srcObject = iv2.stream;
      document.getElementById('iv2CamIcon')?.classList.replace('denied', 'granted');
      document.getElementById('iv2MicIcon')?.classList.replace('denied', 'granted');
      hide(document.getElementById('iv2CamCard'));
      show(document.getElementById('iv2CamPreview'));
      showToast('Camera and microphone access granted!', 'success');
    } catch { showToast('Camera/mic denied.', 'warn'); }
  });
  document.getElementById('iv2StartSessionBtn')?.addEventListener('click', () => {
    if (!iv2.active) iv2Start(); else iv2Stop();
  });
  document.getElementById('iv2SkipBtn')?.addEventListener('click', () => { if (iv2.active) { showToast('Skipped.', 'warn'); iv2NextQ(); } });
  document.getElementById('iv2NextBtn')?.addEventListener('click', () => { if (iv2.active) iv2NextQ(); });
  document.getElementById('iv2SendReportBtn')?.addEventListener('click', () => showToast('Report sent to company!', 'success'));
  document.getElementById('iv2DownloadBtn')?.addEventListener('click', () => showToast('Downloading...', ''));
  document.getElementById('iv2JDBtn')?.addEventListener('click', () => {
    const modal = document.getElementById('resumeUploadModal');
    if (modal) modal.classList.remove('hidden');
  });

  document.getElementById('closeResumeModal')?.addEventListener('click', () => {
    document.getElementById('resumeUploadModal')?.classList.add('hidden');
  });

  document.getElementById('modalCancelResumeBtn')?.addEventListener('click', () => {
    document.getElementById('resumeUploadModal')?.classList.add('hidden');
  });

  document.getElementById('modalGenerateQsBtn')?.addEventListener('click', async () => {
    const fileInput = document.getElementById('resumeFileInput');
    const textInput = document.getElementById('modalResumeText');
    const btn = document.getElementById('modalGenerateQsBtn');

    if ((!fileInput.files || fileInput.files.length === 0) && !textInput.value.trim()) {
      showToast('Please upload a file or paste your resume text.', 'warn');
      return;
    }

    const formData = new FormData();
    if (fileInput.files && fileInput.files.length > 0) {
      formData.append('file', fileInput.files[0]);
    }
    if (textInput.value.trim()) {
      formData.append('text', textInput.value.trim());
    }

    btn.innerHTML = '✨ Generating...';
    btn.disabled = true;

    try {
      const resp = await fetch('http://localhost:8000/api/generate-questions-from-resume', {
        method: 'POST',
        body: formData
      });
      const data = await resp.json();

      if (resp.ok && data.ok && data.questions) {
        if (typeof IV2_QS !== 'undefined') {
          IV2_QS.splice(0, IV2_QS.length, ...data.questions);
        } else {
          window.IV2_QS = data.questions;
        }
        const list = document.getElementById('iv2SetupQList');
        if (list) {
          list.innerHTML = '';
          data.questions.forEach((q, idx) => {
            const item = document.createElement('div');
            item.className = 'iv2-sq-item';
            item.innerHTML = `<span class="iv2-sq-num">${idx + 1}</span><span>${q}</span>`;
            list.appendChild(item);
          });
        }

        showToast('Generated tailored questions!', 'success');
        document.getElementById('resumeUploadModal')?.classList.add('hidden');
        document.getElementById('iv2TabSetup')?.classList.remove('active');
        document.getElementById('iv2TabQuestions')?.classList.add('active');
        document.getElementById('iv2SetupContent')?.classList.add('hidden');
        document.getElementById('iv2QuestionsContent')?.classList.remove('hidden');

      } else {
        showToast(data.error || 'Generation failed.', 'red');
      }
    } catch (err) {
      showToast('API Error.', 'red');
    } finally {
      btn.innerHTML = '✨ Generate Questions';
      btn.disabled = false;
      if (fileInput.files) fileInput.value = '';
    }
  });

  document.getElementById('iv2AddQBtn')?.addEventListener('click', () => showToast('Custom questions coming soon!', ''));
  document.getElementById('iv2CtrlSettings')?.addEventListener('click', () => showPage('settings'));
  document.getElementById('iv2CtrlScreen')?.addEventListener('click', () => showToast('Screen share coming soon.', ''));
  document.getElementById('iv2CtrlFullscreen')?.addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.getElementById('pageInterview')?.requestFullscreen();
  });
}

function iv2Start() {
  iv2.active = true; iv2.qIdx = 0; iv2.scores = []; iv2.timeLeft = 120;
  iv2.fullTranscript = '';  // accumulate all spoken words
  state.lastTranscription = '';
  const b = document.getElementById('iv2StartSessionBtn');
  if (b) { b.innerHTML = '<span class="start-btn-dot"></span> Stop'; b.classList.add('recording'); }
  show(document.getElementById('iv2LivePanel'));
  const badge = document.getElementById('iv2LiveBadge');
  if (badge) badge.style.display = 'flex';
  if (iv2.stream) { hide(document.getElementById('iv2CamCard')); show(document.getElementById('iv2CamPreview')); }
  const defaultTopic = document.getElementById('iv2InterviewType')?.value || "Interview";
  const defaultPrompt = IV2_DESC[defaultTopic] || "General Interview";
  connectWS(() => {
    sendWS({ cmd: 'start' });
    setTimeout(() => {
      sendWS({ cmd: 'manual', topic: defaultPrompt });
    }, 200);
  });
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    iv2.recognition = new SpeechRecognition();
    iv2.recognition.continuous = true;
    iv2.recognition.interimResults = true;
    iv2.recognition.lang = 'en-US';
    const tc = document.getElementById('iv2TranscriptContent');
    if (tc) {
      tc.innerHTML = '';
      const liveDiv = document.createElement('div');
      liveDiv.className = 'transcript-line user';
      liveDiv.id = 'iv2LiveTranscriptLine';
      const t = new Date().toTimeString().slice(0, 5);
      liveDiv.innerHTML = '<span class="tl-time">' + t + '</span><span class="tl-text" id="iv2LiveTranscriptText"><span class="iv2-interim">Listening…</span></span>';
      tc.appendChild(liveDiv);
    }

    iv2.recognition.onresult = (event) => {
      let interimText = '';
      let finalText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalText += t;
          iv2.fullTranscript += ' ' + t;
        } else {
          interimText += t;
        }
      }
      const liveText = document.getElementById('iv2LiveTranscriptText');
      if (liveText) {
        const existing = liveText.querySelector('.iv2-final-text');
        const cur = existing ? existing.textContent : '';
        const newFinal = cur + finalText;
        liveText.innerHTML = (newFinal ? '<span class="iv2-final-text">' + newFinal + '</span>' : '') +
          (interimText ? '<span class="iv2-interim"> ' + interimText + '</span>' : '');
      }
      if (tc) tc.scrollTop = tc.scrollHeight;
    };

    iv2.recognition.onerror = (e) => {
      if (e.error !== 'aborted') console.warn('Speech recognition error:', e.error);
    };

    iv2.recognition.onend = () => {
      if (iv2.active) { try { iv2.recognition.start(); } catch(e) {} }
    };

    try { iv2.recognition.start(); } catch(e) { console.warn('SpeechRecognition start failed:', e); }
  } else {
    showToast('Live transcript requires Chrome — words will appear after session.', 'warn');
  }

  iv2UpdateQ(); iv2StartTimer();
  showToast('Interview started! Answer naturally.', 'success');
}

function iv2Stop() {
  iv2.active = false; clearInterval(iv2.timerInt);
  const b = document.getElementById('iv2StartSessionBtn');
  if (b) { b.innerHTML = '<span class="start-btn-dot"></span> Start'; b.classList.remove('recording'); }
  const badge = document.getElementById('iv2LiveBadge');
  if (badge) badge.style.display = 'none';
  if (iv2.recognition) {
    try { iv2.recognition.stop(); } catch(e) {}
    iv2.recognition = null;
  }
  sendWS({ cmd: 'stop' });
  iv2GenReport();
  iv2.waitingForFeedback = true;
  showToast('Interview complete! Generating AI feedback…', 'success');
}

function iv2UpdateQ() {
  setText('iv2CurQText', IV2_QS[iv2.qIdx] || 'Interview complete.');
  setText('iv2CurBadge', 'Q ' + (iv2.qIdx + 1) + ' / ' + IV2_QS.length);
  const f = document.getElementById('iv2QFill');
  if (f) f.style.width = (iv2.qIdx / IV2_QS.length * 100) + '%';
}

function iv2StartTimer() {
  iv2.timeLeft = 120; iv2UpdTimer(); clearInterval(iv2.timerInt);
  iv2.timerInt = setInterval(() => { iv2.timeLeft--; iv2UpdTimer(); if (iv2.timeLeft <= 0) iv2NextQ(); }, 1000);
}

function iv2UpdTimer() {
  const e = document.getElementById('iv2QTimer');
  if (!e) return;
  e.textContent = Math.floor(iv2.timeLeft / 60) + ':' + (iv2.timeLeft % 60).toString().padStart(2, '0');
  e.style.color = iv2.timeLeft < 30 ? '#dc2626' : 'var(--text-primary)';
}

function iv2NextQ() {
  const r = document.getElementById('iv2Relevance');
  iv2.scores.push(parseFloat(r?.textContent) || Math.round(60 + Math.random() * 35));
  if (iv2.qIdx < IV2_QS.length - 1) { iv2.qIdx++; iv2.timeLeft = 120; iv2UpdateQ(); iv2UpdTimer(); }
  else iv2Stop();
}

function iv2AppendTranscript(text) {
  const c = document.getElementById('iv2TranscriptContent');
  if (c) {
    const l = document.createElement('div');
    l.className = 'transcript-line user';
    const t = new Date().toTimeString().slice(0, 5);
    l.innerHTML = '<span class="tl-time">' + t + '</span><span class="tl-text">' + text + '</span>';
    c.appendChild(l);
    c.scrollTop = c.scrollHeight;
  }
}

function iv2GenReport() {
  const rc = document.getElementById('iv2ReportCard'), ct = document.getElementById('iv2ReportContent');
  if (!rc || !ct) return;
  ct.innerHTML = '<div id="iv2AiFeedbackSection" style="margin-top:0;"><div class="iv2-feedback-loading"><span class="iv2-spinner"></span> Generating session report based on your performance…</div></div>';
  show(rc);
}
async function iv2FetchAIFeedback(question, transcript, iType) {
  try {
    const res = await fetch(API_URL + '/interview/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, transcript, interview_type: iType })
    });
    const data = await res.json();
    const section = document.getElementById('iv2AiFeedbackSection');
    if (!section) return;

    if (!data.ok || !data.feedback) {
      section.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">Could not generate feedback. Check API key.</div>';
      return;
    }
    const fb = data.feedback;
    const followups = (fb.followup_questions || []).map((q, i) =>
      `<div class="iv2-followup-item ${i === 0 ? 'active' : ''}" data-idx="${i}">${q}</div>`
    ).join('');
    const fqNav = fb.followup_questions && fb.followup_questions.length > 1
      ? `<div class="iv2-fq-nav"><button id="iv2FqPrev">←</button><span id="iv2FqCounter">1 / ${fb.followup_questions.length}</span><button id="iv2FqNext">→</button></div>`
      : '';
    const missing = (fb.missing_points || []).map(p => `<li>${p}</li>`).join('');

    section.innerHTML = `
      <div class="iv2-divider"></div>
      <div class="iv2-fb-card iv2-growth">
        <div class="iv2-fb-card-title"><span>🚩</span> Growth Area</div>
        <p class="iv2-fb-card-body">${fb.growth_area || '—'}</p>
      </div>
      <div class="iv2-fb-card iv2-missing">
        <div class="iv2-fb-card-title"><span>💡</span> You could have mentioned</div>
        <ul class="iv2-missing-list">${missing || '<li>Nothing major missed.</li>'}</ul>
      </div>
      <div class="iv2-fb-card iv2-better">
        <div class="iv2-fb-card-title"><span>📝</span> Ideal Answer</div>
        <p class="iv2-fb-card-body iv2-better-text">${fb.better_version || '—'}</p>
      </div>
      ${ fb.followup_questions && fb.followup_questions.length ? `
      <div class="iv2-fb-card iv2-followup">
        <div class="iv2-fb-card-title"><span>❓</span> Follow-up Questions</div>
        <div class="iv2-followup-carousel">${followups}</div>
        ${fqNav}
      </div>` : '' }
    `;
    let fqIdx = 0;
    const items = section.querySelectorAll('.iv2-followup-item');
    const counter = section.querySelector('#iv2FqCounter');
    const showFq = (i) => {
      items.forEach(el => el.classList.remove('active'));
      if (items[i]) items[i].classList.add('active');
      if (counter) counter.textContent = (i + 1) + ' / ' + items.length;
    };
    section.querySelector('#iv2FqPrev')?.addEventListener('click', () => { fqIdx = (fqIdx - 1 + items.length) % items.length; showFq(fqIdx); });
    section.querySelector('#iv2FqNext')?.addEventListener('click', () => { fqIdx = (fqIdx + 1) % items.length; showFq(fqIdx); });

  } catch (e) {
    console.error('AI feedback error:', e);
  }
}
let progressChartInstance = null;

async function loadAnalyticsDashboard() {
  try {
    const res = await fetch(API_URL + '/api/sessions');
    const sessions = await res.json();

    document.getElementById('dashTotalSessions').textContent = sessions.length;
    let avgOv = 0;
    if (sessions.length > 0) {
      avgOv = Math.round(sessions.reduce((acc, s) => acc + s.overall_score, 0) / sessions.length);
    }
    document.getElementById('dashAvgOverall').textContent = avgOv + '%';

    const tbody = document.getElementById('sessionHistoryTableBody');
    tbody.innerHTML = '';
    sessions.forEach(s => {
      const tr = document.createElement('tr');
      tr.style.borderBottom = '1px solid var(--border-color)';
      const dt = new Date(s.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
      tr.innerHTML = `
        <td style="padding:10px;">${dt}</td>
        <td style="padding:10px;text-transform:capitalize;">${s.session_type}</td>
        <td style="padding:10px;font-weight:bold;color:var(--accent);">${s.overall_score}%</td>
        <td style="padding:10px;">${s.relevance_score}%</td>
        <td style="padding:10px;">${s.speech_quality}%</td>
        <td style="padding:10px;">${s.body_language}%</td>
        <td style="padding:10px;">${formatTime(s.duration)}</td>
      `;
      tbody.appendChild(tr);
    });

    const reversed = [...sessions].reverse();
    const labels = reversed.map(s => new Date(s.timestamp).toLocaleDateString());
    const scores = reversed.map(s => s.overall_score);

    const ctx = document.getElementById('progressChart').getContext('2d');
    if (progressChartInstance) progressChartInstance.destroy();
    if (typeof Chart !== 'undefined') {
      progressChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: 'Overall Score',
            data: scores,
            borderColor: '#f97316',
            backgroundColor: 'rgba(249,115,22,0.1)',
            borderWidth: 2,
            fill: true,
            tension: 0.3
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { min: 0, max: 100 } }
        }
      });
    }
  } catch (err) {
    console.error("Dashboard load error", err);
  }
}
document.addEventListener('click', (e) => {
  const nav = e.target.closest('.nav-item');
  if (nav && nav.dataset.page === 'dashboard') {
    loadAnalyticsDashboard();
  }
});
function initThemeToggle() {
  const btn = document.getElementById('themeToggleBtn');
  const sun = btn?.querySelector('.sun-icon');
  const moon = btn?.querySelector('.moon-icon');
  const savedTheme = localStorage.getItem('synthspeak-theme');
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.setAttribute('data-theme', 'dark');
    if (sun) sun.classList.remove('hidden');
    if (moon) moon.classList.add('hidden');
  } else {
    document.documentElement.removeAttribute('data-theme');
    if (sun) sun.classList.add('hidden');
    if (moon) moon.classList.remove('hidden');
  }

  if (btn) {
    btn.addEventListener('click', () => {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      if (isDark) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('synthspeak-theme', 'light');
        if (sun) sun.classList.add('hidden');
        if (moon) moon.classList.remove('hidden');
      } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('synthspeak-theme', 'dark');
        if (sun) sun.classList.remove('hidden');
        if (moon) moon.classList.add('hidden');
      }
    });
  }
}
document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  startClock();
  initSidebar();
  initPracticeCards();
  initPresentation();
  initInterview();
  initRecordingsPage();
  initApiKeyPage();
  initSettingsPage();
  showPage('practice-select');
  connectWS();
  document.getElementById('ptabCoaching')?.addEventListener('click', () => switchPanelTab('coaching'));
  document.getElementById('ptabAnalytics')?.addEventListener('click', () => switchPanelTab('analytics'));

  console.log(
    '%c SynthSpeak Ready ',
    'background:#f97316;color:#fff;font-weight:bold;padding:4px 8px;border-radius:4px;'
  );
  console.log('Served by FastAPI at http://localhost:8000');
  console.log('Backend WebSocket: ws://localhost:8000/ws');
  console.log('Backend REST API:  http://localhost:8000');
  console.log('Hotkeys: Space/S=Start  O=Scan  C=Confirm  M=Manual  H=Help');
});