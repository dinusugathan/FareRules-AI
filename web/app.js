document.addEventListener('DOMContentLoaded', () => {
  // Tabs
  const navTabs = document.querySelectorAll('.nav-tab');
  const viewPanels = document.querySelectorAll('.view-panel');
  
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      navTabs.forEach(t => t.classList.remove('active'));
      viewPanels.forEach(p => p.classList.remove('active-panel'));
      
      tab.classList.add('active');
      const target = document.getElementById(tab.dataset.tab);
      if (target) target.classList.add('active-panel');
    });
  });

  // Channel Toggle (B2C vs B2B)
  const b2cBtn = document.getElementById('channel-b2c-btn');
  const b2bBtn = document.getElementById('channel-b2b-btn');
  const channelDesc = document.getElementById('channel-desc');
  let currentChannel = 'B2C';

  b2cBtn.addEventListener('click', () => {
    currentChannel = 'B2C';
    b2cBtn.classList.add('active');
    b2bBtn.classList.remove('active');
    channelDesc.textContent = 'B2C Retail Customer Website (Standard ₹350 Fee)';
  });

  b2bBtn.addEventListener('click', () => {
    currentChannel = 'B2B';
    b2bBtn.classList.add('active');
    b2cBtn.classList.remove('active');
    channelDesc.textContent = 'B2B Travel Agent Portal (Subsidized ₹200 Fee)';
  });

  // Chat Elements
  const chatMessages = document.getElementById('chat-messages');
  const chatForm = document.getElementById('chat-form');
  const queryInput = document.getElementById('query-input');
  const quickChips = document.querySelectorAll('.quick-chip');

  // Quick Chips
  quickChips.forEach(chip => {
    chip.addEventListener('click', () => {
      let q = chip.dataset.query;
      // Adjust channel keyword if B2B is active
      if (currentChannel === 'B2B' && !q.toLowerCase().includes('b2b')) {
        q += ' (I am booking via B2B Agent Portal)';
      }
      queryInput.value = q;
      handleSubmitQuery(q);
    });
  });

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    let q = queryInput.value.trim();
    if (!q) return;
    if (currentChannel === 'B2B' && !q.toLowerCase().includes('b2b')) {
      q += ' (Channel: B2B Agent Portal)';
    }
    handleSubmitQuery(q);
  });

  async function handleSubmitQuery(query) {
    appendUserBubble(query);
    queryInput.value = '';

    const loadingId = 'loading-' + Date.now();
    appendLoadingBubble(loadingId);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      const data = await res.json();
      removeLoadingBubble(loadingId);
      appendAssistantBubble(data);
    } catch (err) {
      removeLoadingBubble(loadingId);
      appendErrorBubble(err.message);
    }
  }

  function appendUserBubble(text) {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble user-bubble';
    bubble.innerHTML = `<div class="bubble-body">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendLoadingBubble(id) {
    const bubble = document.createElement('div');
    bubble.id = id;
    bubble.className = 'chat-bubble assistant-bubble';
    bubble.innerHTML = `
      <div class="bubble-header">
        <span class="bubble-avatar">✈️</span>
        <span class="bubble-name">Akbar Travels Fare Desk</span>
        <span class="bubble-badge">Reranking ATPCO rules...</span>
      </div>
      <div class="bubble-body" style="color: var(--text-muted); font-style: italic;">
        Querying carrier fare tariff, evaluating time-window slabs, and executing fee calculation tool...
      </div>
    `;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeLoadingBubble(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function appendErrorBubble(errText) {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble assistant-bubble';
    bubble.innerHTML = `
      <div class="bubble-body" style="background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); color: #fca5a5;">
        ⚠️ Error: ${escapeHtml(errText)}
      </div>
    `;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendAssistantBubble(data) {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble assistant-bubble';

    let quoteHtml = '';
    if (data.quote) {
      const q = data.quote;
      quoteHtml = `
        <div class="quote-card">
          <div class="quote-header">
            <span class="quote-title">🧾 Deterministic Refund Calculation Ledger</span>
            <span class="quote-citation-badge">${escapeHtml(q.citation)}</span>
          </div>
          <div class="quote-ledger">
            <div class="ledger-row">
              <span>Gross Ticket Fare:</span>
              <span style="font-weight: 600; color: white;">₹${q.ticket_fare.toFixed(2)}</span>
            </div>
            <div class="ledger-row">
              <span>Carrier Penalty (ATPCO Cat 16):</span>
              <span style="color: #fca5a5;">-₹${q.airline_penalty.toFixed(2)}</span>
            </div>
            <div class="ledger-row">
              <span>Akbar Portal Fee (${currentChannel}):</span>
              <span style="color: #fca5a5;">-₹${q.agency_fee.toFixed(2)}</span>
            </div>
            <div class="ledger-total ${q.is_noshow ? 'ledger-noshow' : ''}">
              <span>${q.is_noshow ? '⚠️ Non-Refundable / No-Show' : 'Net Refund Payable:'}</span>
              <span>₹${q.net_refund.toFixed(2)}</span>
            </div>
          </div>
        </div>
      `;
    }

    bubble.innerHTML = `
      <div class="bubble-header">
        <span class="bubble-avatar">✈️</span>
        <span class="bubble-name">Akbar Travels Fare Desk</span>
        <span class="bubble-badge">Latency: ${data.latency_ms.toFixed(1)}ms</span>
        ${data.policy_citations.map(c => `<span class="bubble-badge" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc;">${escapeHtml(c)}</span>`).join('')}
      </div>
      <div class="bubble-body">
        <div style="white-space: pre-line; line-height: 1.55;">${formatMarkdown(data.answer)}</div>
        ${quoteHtml}
      </div>
    `;

    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Load Tariffs Grid
  async function loadTariffs() {
    try {
      const res = await fetch('/api/rules');
      const rules = await res.json();
      renderTariffs(rules);
    } catch (err) {
      console.error('Failed to load rules', err);
    }
  }

  function renderTariffs(rules) {
    const grid = document.getElementById('tariffs-grid');
    grid.innerHTML = rules.map(r => `
      <div class="tariff-card">
        <div class="tariff-card-header">
          <div>
            <span class="carrier-tag">${escapeHtml(r.carrier_name)} (${escapeHtml(r.carrier_code)})</span>
            <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(r.fare_class)} &bull; ${escapeHtml(r.service_type)}</div>
          </div>
          <span class="sector-badge">${escapeHtml(r.sector)}</span>
        </div>

        <div style="font-size: 0.82rem; color: var(--text-secondary);">
          <strong>Baggage:</strong> Check-in: ${escapeHtml(r.baggage_allowance.checkin || 'N/A')} &bull; Cabin: ${escapeHtml(r.baggage_allowance.cabin || 'N/A')}
        </div>

        <table class="slabs-table">
          <thead>
            <tr>
              <th>Departure Time Window</th>
              <th>Cancellation Penalty</th>
            </tr>
          </thead>
          <tbody>
            ${r.cancellation_slabs.map(s => `
              <tr>
                <td>${escapeHtml(s.time_window)}</td>
                <td style="font-weight: 700; color: ${s.airline_penalty === -1 ? '#f87171' : '#fbbf24'};">
                  ${s.airline_penalty === -1 ? 'No-Show (₹0)' : (s.airline_penalty < 1 ? (s.airline_penalty * 100) + '%' : '₹' + s.airline_penalty.toFixed(0))}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `).join('');
  }

  // Load Evals
  async function loadEvals() {
    try {
      const res = await fetch('/api/evals');
      const data = await res.json();
      renderEvals(data);
    } catch (err) {
      console.error('Failed to load evals', err);
    }
  }

  function renderEvals(data) {
    document.getElementById('kpi-pass-rate').textContent = `${data.pass_rate_percentage}%`;
    document.getElementById('kpi-accuracy').textContent = `${data.zero_hallucination_rate.toFixed(1)}%`;

    const tbody = document.getElementById('evals-table-body');
    tbody.innerHTML = data.results.map(r => `
      <tr>
        <td style="font-weight: 700; color: white;">${escapeHtml(r.test_id)}</td>
        <td><span class="${r.passed ? 'badge-pass' : 'badge-fail'}">${r.passed ? 'PASS' : 'FAIL'}</span></td>
        <td>${r.correct_penalty ? '✅ Verified' : '❌ Error'}</td>
        <td>${r.correct_agency_fee ? '✅ Verified' : '❌ Error'}</td>
        <td>${r.correct_refund ? '✅ Exact' : '❌ Mismatch'}</td>
        <td>${r.citation_matched ? '✅ Matched' : '—'}</td>
        <td style="font-family: var(--font-mono);">${r.latency_ms.toFixed(1)}ms</td>
      </tr>
    `).join('');
  }

  // Run Evals Live
  const runEvalsBtn = document.getElementById('run-evals-btn');
  runEvalsBtn.addEventListener('click', async () => {
    runEvalsBtn.disabled = true;
    runEvalsBtn.textContent = '⚡ Running Benchmark...';
    try {
      const res = await fetch('/api/evals/run', { method: 'POST' });
      const fresh = await res.json();
      renderEvals(fresh);
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      runEvalsBtn.disabled = false;
      runEvalsBtn.textContent = '⚡ Run Quality Benchmark';
    }
  });

  // Helpers
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag));
  }

  function formatMarkdown(text) {
    if (!text) return '';
    return escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code style="background: rgba(99,102,241,0.2); padding: 1px 6px; border-radius: 4px; font-family: monospace;">$1</code>');
  }

  // Initial Loads
  loadTariffs();
  loadEvals();
});
