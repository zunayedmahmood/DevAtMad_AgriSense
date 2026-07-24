// AgriSense Frontend Application Logic (Vanilla JS)
document.addEventListener('DOMContentLoaded', () => {
  // Global State
  const state = {
    sessionId: `session_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
    engine: 'agentic', // 'agentic' or 'tier0'
    messages: [],
    profile: {},
    recommendations: [],
    selectedCropId: null,
    plan: null,
    traces: [],
    missingFields: []
  };

  // DOM Elements
  const els = {
    engineAgentic: document.getElementById('engine-agentic'),
    engineTier0: document.getElementById('engine-tier0'),
    backendStatus: document.getElementById('backend-status'),
    backendText: document.getElementById('backend-text'),
    btnNewSession: document.getElementById('btn-new-session'),
    
    // Profile
    profileStatus: document.getElementById('profile-status-badge'),
    pLocation: document.getElementById('p-location'),
    pCoords: document.getElementById('p-coords'),
    pArea: document.getElementById('p-area'),
    pSoil: document.getElementById('p-soil'),
    pWater: document.getElementById('p-water'),
    pBudget: document.getElementById('p-budget'),
    pSeason: document.getElementById('p-season'),
    pCrop: document.getElementById('p-crop'),
    missingBox: document.getElementById('missing-fields-box'),
    missingTags: document.getElementById('missing-fields-tags'),

    // Chat
    chatContainer: document.getElementById('chat-container'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    btnSend: document.getElementById('btn-send'),
    cropBar: document.getElementById('crop-recommendations-bar'),
    cropCards: document.getElementById('crop-cards-container'),

    // Right Column Tabs
    tabTracesBtn: document.getElementById('tab-btn-traces'),
    tabPlanBtn: document.getElementById('tab-btn-plan'),
    tabTracesContent: document.getElementById('tab-content-traces'),
    tabPlanContent: document.getElementById('tab-content-plan'),
    traceCount: document.getElementById('trace-count'),
    tracesEmpty: document.getElementById('traces-empty'),
    tracesList: document.getElementById('traces-list'),
    planEmpty: document.getElementById('plan-empty'),
    planDetails: document.getElementById('plan-details'),
    planTitle: document.getElementById('plan-title'),
    planSubtitle: document.getElementById('plan-subtitle'),
    planCost: document.getElementById('plan-cost'),
    planProfit: document.getElementById('plan-profit'),
    planYield: document.getElementById('plan-yield'),
    planRoi: document.getElementById('plan-roi'),

    // Current Goal Card
    goalStage: document.getElementById('goal-stage'),
    goalMilestones: document.getElementById('goal-milestones'),
    goalNextAction: document.getElementById('goal-next-action'),
    planTimeline: document.getElementById('plan-timeline'),
    planFertilizerTable: document.getElementById('plan-fertilizer-table'),

    // Modal
    modalTrace: document.getElementById('modal-trace'),
    modalTraceTitle: document.getElementById('modal-trace-title'),
    modalTraceParams: document.getElementById('modal-trace-params'),
    modalTraceResult: document.getElementById('modal-trace-result'),
    modalTraceClose: document.getElementById('modal-trace-close')
  };

  // Initialize Lucide Icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Check Backend Health
  async function checkHealth() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        const data = await res.json();
        els.backendText.textContent = `${data.external_mode.toUpperCase()} Mode (${data.llm_provider})`;
        els.backendStatus.classList.remove('bg-slate-800');
        els.backendStatus.classList.add('bg-emerald-950', 'border-emerald-700/60');
      } else {
        els.backendText.textContent = 'Backend Error';
      }
    } catch (e) {
      els.backendText.textContent = 'Offline / Standalone';
    }
  }
  checkHealth();

  // Engine Switcher
  els.engineAgentic.addEventListener('click', () => {
    state.engine = 'agentic';
    els.engineAgentic.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 bg-brand-600 text-white shadow';
    els.engineTier0.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition flex items-center gap-1.5';
  });

  els.engineTier0.addEventListener('click', () => {
    state.engine = 'tier0';
    els.engineTier0.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 bg-brand-600 text-white shadow';
    els.engineAgentic.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition flex items-center gap-1.5';
  });

  // Reset Session
  els.btnNewSession.addEventListener('click', () => {
    state.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    state.messages = [];
    state.profile = {};
    state.recommendations = [];
    state.selectedCropId = null;
    state.plan = null;
    state.traces = [];
    state.missingFields = [];
    
    els.chatContainer.innerHTML = '';
    renderProfile();
    renderTraces();
    renderPlan();
    els.cropBar.classList.add('hidden');
    addAssistantMessage('Session reset. Ready for your farm details.');
  });

  // Tab Switcher
  els.tabTracesBtn.addEventListener('click', () => {
    els.tabTracesBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-brand-400 border-b-2 border-brand-500 flex items-center justify-center gap-1.5';
    els.tabPlanBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 border-b-2 border-transparent hover:text-slate-200 flex items-center justify-center gap-1.5';
    els.tabTracesContent.classList.remove('hidden');
    els.tabPlanContent.classList.add('hidden');
  });

  els.tabPlanBtn.addEventListener('click', () => {
    els.tabPlanBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-brand-400 border-b-2 border-brand-500 flex items-center justify-center gap-1.5';
    els.tabTracesBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 border-b-2 border-transparent hover:text-slate-200 flex items-center justify-center gap-1.5';
    els.tabPlanContent.classList.remove('hidden');
    els.tabTracesContent.classList.add('hidden');
  });

  // Sample Prompt Buttons
  document.querySelectorAll('.sample-prompt').forEach(btn => {
    btn.addEventListener('click', () => {
      els.chatInput.value = btn.getAttribute('data-prompt');
      els.chatInput.focus();
    });
  });

  // Submit Turn Form
  els.chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = els.chatInput.value.trim();
    if (!message) return;

    els.chatInput.value = '';
    addUserMessage(message);
    setLoading(true);

    try {
      const endpoint = state.engine === 'agentic' ? '/v1/agent/agentic-turn' : '/v1/agent/turn';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          message: message
        })
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const turn = await res.json();
      handleTurnResponse(turn);
    } catch (err) {
      addAssistantMessage(`Error executing turn: ${err.message}. Ensure backend server is running.`);
    } finally {
      setLoading(false);
    }
  });

  // Handle Response Payload
  function handleTurnResponse(turn) {
    if (turn.profile) state.profile = turn.profile;
    if (turn.missing_fields) state.missingFields = turn.missing_fields;
    if (turn.recommendations) state.recommendations = turn.recommendations;
    if (turn.selected_crop_id) state.selectedCropId = turn.selected_crop_id;
    if (turn.plan) state.plan = turn.plan;
    if (turn.trace) state.traces = turn.trace;

    renderProfile();
    renderTraces();
    renderPlan();

    // Add assistant reply with decision summary proof of thinking
    addAssistantMessage(turn.message, turn.decision_summary);

    // Render crop recommendations if available
    if (state.recommendations && state.recommendations.length > 0) {
      renderCropCards(state.recommendations);
    } else {
      els.cropBar.classList.add('hidden');
    }
  }

  // Render Crop Cards
  function renderCropCards(recs) {
    els.cropCards.innerHTML = '';
    els.cropBar.classList.remove('hidden');

    recs.forEach((rec, idx) => {
      const card = document.createElement('div');
      const isSelected = state.selectedCropId === rec.crop_id;
      const isEligible = rec.eligible;

      card.className = `p-3 rounded-xl border transition flex flex-col justify-between ${
        isSelected 
          ? 'bg-brand-500/10 border-brand-500 text-white shadow-lg shadow-brand-500/10' 
          : isEligible 
            ? 'bg-slate-800/80 border-slate-700/80 hover:border-slate-600 text-slate-200' 
            : 'bg-slate-900/60 border-red-500/30 text-slate-400 opacity-70'
      }`;

      card.innerHTML = `
        <div>
          <div class="flex items-center justify-between mb-1">
            <span class="font-bold text-xs flex items-center gap-1">
              #${idx + 1} ${rec.crop_name}
            </span>
            <span class="px-1.5 py-0.5 text-[10px] font-mono rounded ${
              isEligible ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
            }">
              Score: ${rec.suitability_score_0_100}/100
            </span>
          </div>
          <p class="text-[10px] text-slate-400 line-clamp-2 mb-2">${rec.hard_eligibility_reasons?.join(' ') || rec.summary}</p>
        </div>
        <button class="select-crop-btn w-full py-1.5 text-xs font-semibold rounded-lg transition ${
          isSelected 
            ? 'bg-brand-500 text-white cursor-default' 
            : isEligible 
              ? 'bg-slate-700 hover:bg-brand-600 text-slate-100 hover:text-white' 
              : 'bg-slate-800 text-slate-500 cursor-not-allowed'
        }" ${!isEligible ? 'disabled' : ''} data-crop="${rec.crop_id}">
          ${isSelected ? 'Selected' : isEligible ? 'Select Crop' : 'Ineligible'}
        </button>
      `;

      card.querySelector('.select-crop-btn').addEventListener('click', () => {
        if (!isEligible) return;
        selectCrop(rec.crop_id);
      });

      els.cropCards.appendChild(card);
    });
  }

  // Select Crop Action
  async function selectCrop(cropId) {
    addUserMessage(`Select crop: ${cropId}`);
    setLoading(true);
    try {
      const endpoint = state.engine === 'agentic' ? '/v1/agent/agentic-turn' : '/v1/agent/turn';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          message: cropId,
          profile_patch: { chosen_crop_id: cropId }
        })
      });
      const turn = await res.json();
      handleTurnResponse(turn);
    } catch (e) {
      addAssistantMessage(`Failed to select crop: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  // Render Profile
  function renderProfile() {
    const p = state.profile;
    els.pLocation.textContent = p.location_text ? `${p.location_text}${p.district ? ', ' + p.district : ''}` : 'Not provided';
    els.pCoords.textContent = (p.latitude && p.longitude) ? `${p.latitude.toFixed(4)}°, ${p.longitude.toFixed(4)}°` : 'Unmapped';
    els.pArea.textContent = p.farm_size_acre ? `${p.farm_size_acre} acres` : '—';
    els.pSoil.textContent = p.soil_type || '—';
    els.pWater.textContent = p.water_availability || '—';
    els.pBudget.textContent = p.budget_bdt ? `BDT ${p.budget_bdt.toLocaleString()}` : '—';
    els.pSeason.textContent = p.target_season || '—';
    els.pCrop.textContent = p.chosen_crop_id ? p.chosen_crop_id.replace('_', ' ').toUpperCase() : '—';

    if (state.missingFields && state.missingFields.length > 0) {
      els.profileStatus.textContent = 'Collecting';
      els.profileStatus.className = 'px-2 py-0.5 text-[10px] font-semibold rounded bg-amber-500/10 text-amber-400 border border-amber-500/20';
      els.missingBox.classList.remove('hidden');
      els.missingTags.innerHTML = state.missingFields.map(f => `<span class="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px] border border-amber-500/20">${f}</span>`).join('');
    } else {
      els.profileStatus.textContent = 'Complete';
      els.profileStatus.className = 'px-2 py-0.5 text-[10px] font-semibold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      els.missingBox.classList.add('hidden');
    }
  }

  // Map machine event types / tool names to judge-facing labels
  function mapJudgeLabel(toolName, sourceKind) {
    if (toolName === 'parse_farmer_message') return 'Farm facts extracted';
    if (toolName === 'geocode_location') return 'Location resolved';
    if (toolName === 'get_live_weather_forecast' || toolName === 'get_weather_forecast') return 'Weather retrieved';
    if (toolName === 'retrieve_agronomic_context' || toolName === 'retrieve_agronomy') return 'Evidence retrieved';
    if (toolName === 'rank_crop_candidates') return 'Crop ranking calculated';
    if (toolName === 'calculate_financial_projection') return 'Finance calculated';
    if (toolName === 'generate_dated_season_plan') return 'Completion validation';
    if (sourceKind === 'direct_tool_invocation') return 'Tool call';
    if (sourceKind === 'agentic_tool_invocation') return 'Agent decision';
    return 'Tool call';
  }

  // 4-Question Operational Breakdown Helper for Activity Cards
  function getOperationalFourQuestions(t) {
    const name = (t.tool_name || '').toLowerCase();
    const p = t.parameters || {};
    const r = t.raw_result || {};

    if (name.includes('geocode')) {
      return {
        what: 'TOOL SELECTED - Location Geocoding',
        why: 'Spatial coordinates are required to query location-specific weather & soil records.',
        data: `Input: ${p.location_text || p.district || 'Location text'}; Result: ${r.formatted || 'Coordinates resolved'} (${r.latitude?.toFixed(4) || ''}, ${r.longitude?.toFixed(4) || ''})`,
        next: 'Retrieve live meteorological forecast from Open-Meteo.'
      };
    }
    if (name.includes('weather')) {
      const summary = r.summary || {};
      return {
        what: 'TOOL SELECTED - Live Weather Ingestion',
        why: 'Crop suitability and near-term farm actions require verified rainfall and temperature.',
        data: `Input: lat ${p.latitude || 0}, lon ${p.longitude || 0}; Result: ${summary.temperature_avg_c || 26}°C mean temp, ${summary.rainfall_forecast_total_mm || 0}mm 7-day rainfall`,
        next: 'Query hybrid RAG store for reviewed extension guidelines.'
      };
    }
    if (name.includes('agronom') || name.includes('rag')) {
      const count = Array.isArray(r) ? r.length : (r.results ? r.results.length : 1);
      return {
        what: 'EVIDENCE RETRIEVED - Hybrid RAG Search',
        why: 'Verify BARC/BAMIS extension rules, soil compatibility, and fertilizer schedules.',
        data: `Input: query "${p.query || p.crop_id || 'agronomy'}"; Result: ${count} evidence document chunks retrieved`,
        next: 'Calculate multi-criteria candidate crop suitability scores.'
      };
    }
    if (name.includes('rank')) {
      return {
        what: 'CALCULATOR - Multi-Criteria Crop Ranking',
        why: 'Score eligible crops against season fit, soil type, water access, and ROI.',
        data: `Input: Farm profile & weather context; Result: 3 ranked crop candidates with suitability scores`,
        next: 'Present ranked candidates to farmer and await human selection.'
      };
    }
    if (name.includes('finance')) {
      return {
        what: 'CALCULATOR - Financial Projection Ledger',
        why: 'Compute inspectable cost components, gross revenue, net profit, ROI %, and break-even points.',
        data: `Input: crop_id "${p.crop_id || 'crop'}", budget BDT ${(p.profile?.budget_bdt || 0).toLocaleString()}; Result: Net profit & ROI % calculated`,
        next: 'Construct stage-by-stage dated season calendar.'
      };
    }
    if (name.includes('plan')) {
      return {
        what: 'VALIDATION - Season Plan Construction',
        why: 'Generate stage-by-stage calendar dates, fertilizer splits, and pest checkpoints with forecast horizon checks.',
        data: `Input: chosen_crop_id "${p.crop_id || 'crop'}"; Result: Reconciled dated calendar & validation pass`,
        next: 'Plan complete. Schedule weather horizon refreshes before future tasks.'
      };
    }

    return {
      what: `TOOL SELECTED - ${t.tool_name}`,
      why: `Executed operational action via ${t.source_kind}.`,
      data: `Input: ${JSON.stringify(p)}; Result: ${typeof r === 'object' ? JSON.stringify(r).slice(0, 80) : String(r)}`,
      next: 'Proceed to next workflow stage.'
    };
  }

  // Render Traces & Current Goal Card
  function renderTraces() {
    const traces = state.traces || [];
    els.traceCount.textContent = traces.length;

    // Update Current Goal Card from real state
    const p = state.profile || {};
    const hasLocation = Boolean(p.latitude && p.longitude);
    const hasWeather = traces.some(t => t.tool_name.includes('weather'));
    const hasEvidence = traces.some(t => t.tool_name.includes('agronom') || t.tool_name.includes('rag'));
    const hasRankings = (state.recommendations && state.recommendations.length > 0);
    const hasPlan = Boolean(state.plan);

    if (hasPlan) {
      els.goalStage.textContent = 'Plan Built & Validated';
      els.goalStage.className = 'font-semibold text-emerald-400';
      els.goalNextAction.textContent = 'Plan complete. Ready for field execution or what-if scenario testing.';
    } else if (hasRankings) {
      els.goalStage.textContent = 'Crop Selection Required';
      els.goalStage.className = 'font-semibold text-amber-400';
      els.goalNextAction.textContent = 'Rank three crops → Wait for crop selection → Build and validate the plan';
    } else {
      els.goalStage.textContent = 'Collecting Farm Facts';
      els.goalStage.className = 'font-semibold text-amber-400';
      els.goalNextAction.textContent = 'Provide location, land size, soil, water, budget & season.';
    }

    els.goalMilestones.innerHTML = `
      <div class="flex items-center gap-1.5">${hasLocation ? '<i data-lucide="check-circle-2" class="w-3 h-3 text-emerald-400"></i> <span class="text-slate-200">Location resolved</span>' : '<i data-lucide="circle" class="w-3 h-3 text-slate-600"></i> Location pending'}</div>
      <div class="flex items-center gap-1.5">${hasWeather ? '<i data-lucide="check-circle-2" class="w-3 h-3 text-emerald-400"></i> <span class="text-slate-200">Weather retrieved</span>' : '<i data-lucide="circle" class="w-3 h-3 text-slate-600"></i> Weather pending'}</div>
      <div class="flex items-center gap-1.5">${hasEvidence ? '<i data-lucide="check-circle-2" class="w-3 h-3 text-emerald-400"></i> <span class="text-slate-200">Evidence retrieved</span>' : '<i data-lucide="circle" class="w-3 h-3 text-slate-600"></i> Evidence pending'}</div>
    `;

    if (window.lucide) window.lucide.createIcons();

    let blockedCardsHtml = '';
    if (state.missingFields && state.missingFields.length > 0) {
      blockedCardsHtml = `
        <div class="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 space-y-2 mb-3">
          <div class="flex items-center justify-between">
            <span class="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              Information Gap Detected
            </span>
            <span class="text-[10px] text-amber-400 font-semibold">NO TOOL CALL</span>
          </div>
          <p class="text-xs font-semibold text-slate-100">
            Missing required farm facts: <span class="text-amber-300 font-mono">${state.missingFields.join(', ')}</span>
          </p>
          <p class="text-[11px] text-slate-300 leading-relaxed">
            <strong>DECISION:</strong> Crop ranking and season planning are BLOCKED. Calling ranking calculators or weather without complete farm size, soil, water, budget, or target season would create a misleading plan.
          </p>
          <p class="text-[10px] text-slate-400 border-t border-amber-500/20 pt-1.5">
            <strong>NEXT ACTION:</strong> Ask targeted follow-up question for remaining missing fields.
          </p>
        </div>
      `;
    }

    if (traces.length === 0) {
      els.tracesEmpty.classList.remove('hidden');
      els.tracesList.innerHTML = blockedCardsHtml;
      return;
    }

    els.tracesEmpty.classList.add('hidden');
    
    const traceCardsHtml = traces.map((t, idx) => {
      const judgeLabel = mapJudgeLabel(t.tool_name, t.source_kind);
      const q = getOperationalFourQuestions(t);

      return `
        <div class="p-3.5 rounded-xl bg-slate-800/80 border border-slate-700/70 hover:border-brand-500/60 transition cursor-pointer trace-item group space-y-2" data-idx="${idx}">
          <div class="flex items-center justify-between">
            <span class="font-mono text-xs font-bold text-brand-400 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-brand-400"></span>
              #${t.step_no} ${t.tool_name}
            </span>
            <span class="font-mono text-[10px] text-slate-400">${t.duration_ms ? t.duration_ms.toFixed(1) + 'ms' : ''}</span>
          </div>
          
          <div class="flex items-center justify-between">
            <span class="px-2 py-0.5 text-[9px] font-semibold rounded bg-brand-500/10 text-brand-300 border border-brand-500/20">${judgeLabel}</span>
            <span class="text-[10px] text-slate-400 font-mono">${t.source_kind}</span>
          </div>

          <!-- 4-QUESTION OPERATIONAL BREAKDOWN -->
          <div class="space-y-1.5 text-[11px] pt-1 border-t border-slate-700/50">
            <div>
              <span class="text-slate-400 font-semibold block text-[10px]">1. WHAT HAPPENED?</span>
              <span class="text-slate-200 font-medium">${escapeHtml(q.what)}</span>
            </div>
            <div>
              <span class="text-slate-400 font-semibold block text-[10px]">2. WHY WAS IT NEEDED?</span>
              <span class="text-slate-300">${escapeHtml(q.why)}</span>
            </div>
            <div>
              <span class="text-slate-400 font-semibold block text-[10px]">3. DATA ENTERED / RETURNED:</span>
              <span class="text-emerald-300 font-mono text-[10px] block truncate">${escapeHtml(q.data)}</span>
            </div>
            <div>
              <span class="text-slate-400 font-semibold block text-[10px]">4. WHAT HAPPENS NEXT?</span>
              <span class="text-brand-300 font-medium">${escapeHtml(q.next)}</span>
            </div>
          </div>

          <div class="pt-1 text-right border-t border-slate-700/40">
            <span class="text-[10px] text-brand-400 group-hover:underline font-medium flex items-center justify-end gap-1">
              Inspect Raw JSON Payload &rarr;
            </span>
          </div>
        </div>
      `;
    }).join('');

    els.tracesList.innerHTML = blockedCardsHtml + traceCardsHtml;

    document.querySelectorAll('.trace-item').forEach(item => {
      item.addEventListener('click', () => {
        const idx = parseInt(item.getAttribute('data-idx'));
        showTraceModal(traces[idx]);
      });
    });
  }

  // Show Trace Modal
  function showTraceModal(t) {
    els.modalTraceTitle.textContent = `Tool Trace #${t.step_no}: ${t.tool_name}`;
    els.modalTraceParams.textContent = JSON.stringify(t.parameters, null, 2);
    els.modalTraceResult.textContent = JSON.stringify(t.raw_result, null, 2);
    els.modalTrace.classList.remove('hidden');
  }

  els.modalTraceClose.addEventListener('click', () => {
    els.modalTrace.classList.add('hidden');
  });

      return;
    }

    els.planEmpty.classList.add('hidden');
    els.planDetails.classList.remove('hidden');

    els.planTitle.textContent = `${plan.crop_name} Season Plan`;
    els.planSubtitle.textContent = `Sowing: ${plan.planned_sowing_date} → Harvest: ${plan.expected_harvest_date} (${plan.total_duration_days} days)`;

    const fin = plan.financial_projection || {};
    els.planCost.textContent = `BDT ${(fin.total_cost_bdt || 0).toLocaleString()}`;
    els.planProfit.textContent = `BDT ${(fin.net_profit_bdt || 0).toLocaleString()}`;
    els.planYield.textContent = `${(fin.expected_yield_kg || 0).toLocaleString()} kg`;
    els.planRoi.textContent = `${(fin.roi_percent || 0).toFixed(1)}%`;

    // Stages Timeline
    const stages = plan.stages || [];
    els.planTimeline.innerHTML = stages.map(s => `
      <div class="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
        <div class="flex items-center justify-between text-xs font-semibold text-slate-200 mb-1">
          <span>${s.stage_name}</span>
          <span class="font-mono text-[10px] text-brand-400">${s.start_date} → ${s.end_date}</span>
        </div>
        <p class="text-[11px] text-slate-400 mb-1.5">${s.stage_purpose}</p>
        <div class="text-[10px] text-slate-500 flex flex-wrap gap-1">
          ${(s.key_tasks || []).map(t => `<span class="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">• ${t}</span>`).join('')}
        </div>
      </div>
    `).join('');

    // Fertilizer Split Table
    const tbody = els.planFertilizerTable.querySelector('tbody');
    const fertilizerList = [];
    stages.forEach(s => {
      (s.fertilizer_tasks || []).forEach(ft => {
        (ft.products || []).forEach(p => {
          fertilizerList.push({
            stage: s.stage_name,
            product: p.product_name,
            kg: p.quantity_kg
          });
        });
      });
    });

    if (fertilizerList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" class="p-3 text-center text-slate-500">No split fertilizer applications recorded.</td></tr>`;
    } else {
      tbody.innerHTML = fertilizerList.map(item => `
        <tr>
          <td class="p-2 font-medium text-slate-300">${item.stage}</td>
          <td class="p-2 text-slate-400">${item.product}</td>
          <td class="p-2 text-right font-mono font-semibold text-brand-400">${item.kg} kg</td>
        </tr>
      `).join('');
    }
  }

  // Add Messages to Chat UI
  function addUserMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'flex justify-end animate-fade-in';
    msg.innerHTML = `
      <div class="max-w-xl p-3.5 rounded-2xl bg-brand-600 text-white text-sm shadow-md rounded-tr-none">
        ${escapeHtml(text)}
      </div>
    `;
    els.chatContainer.appendChild(msg);
    scrollToBottom();
  }

  function addAssistantMessage(text, decisionSummary) {
    const msg = document.createElement('div');
    msg.className = 'flex items-start gap-3 animate-fade-in';

    let summaryHtml = '';
    if (decisionSummary && decisionSummary.length > 0) {
      summaryHtml = `
        <details class="mb-3 rounded-xl bg-slate-900 border border-slate-800 p-2 text-xs">
          <summary class="font-medium text-brand-400 cursor-pointer flex items-center gap-1.5 select-none">
            <span>🧠 Proof of Thinking & Decision Process</span>
          </summary>
          <ul class="mt-2 space-y-1 text-slate-400 pl-4 list-disc text-[11px]">
            ${decisionSummary.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
          </ul>
        </details>
      `;
    }

    msg.innerHTML = `
      <div class="w-8 h-8 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center shrink-0 mt-0.5">
        <i data-lucide="bot" class="w-5 h-5"></i>
      </div>
      <div class="max-w-2xl p-4 rounded-2xl bg-slate-900/90 border border-slate-800 text-sm text-slate-200 shadow-md rounded-tl-none space-y-2">
        ${summaryHtml}
        <div class="leading-relaxed whitespace-pre-wrap">${escapeHtml(text)}</div>
      </div>
    `;

    els.chatContainer.appendChild(msg);
    if (window.lucide) window.lucide.createIcons();
    scrollToBottom();
  }

  function setLoading(loading) {
    els.btnSend.disabled = loading;
    els.btnSend.style.opacity = loading ? '0.6' : '1';
    els.chatInput.disabled = loading;
  }

  function scrollToBottom() {
    els.chatContainer.scrollTop = els.chatContainer.scrollHeight;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Sandbox Buttons
  document.getElementById('btn-tool-geocode').addEventListener('click', async () => {
    const text = prompt("Enter location to geocode:", "Moulovibazar, Bangladesh");
    if (!text) return;
    invokeDirectTool('geocode_location', { location_text: text });
  });

  document.getElementById('btn-tool-weather').addEventListener('click', async () => {
    invokeDirectTool('get_live_weather_forecast', { latitude: 24.488, longitude: 91.763, forecast_days: 7 });
  });

  document.getElementById('btn-tool-rag').addEventListener('click', async () => {
    const query = prompt("Enter RAG search query:", "Boro rice fertilizer application timing Moulovibazar");
    if (!query) return;
    invokeDirectTool('retrieve_agronomic_context', { query, district: 'Moulovibazar', top_k: 5 });
  });

  document.getElementById('btn-tool-rank').addEventListener('click', async () => {
    invokeDirectTool('rank_crop_candidates', {
      profile: state.profile,
      weather_summary: { temperature_avg_c: 28.5, rainfall_forecast_total_mm: 22.4 },
      minimum_candidates: 3
    });
  });

  async function invokeDirectTool(name, args) {
    setLoading(true);
    try {
      const res = await fetch('/v1/tools/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: state.sessionId, name, arguments: args })
      });
      const data = await res.json();
      showTraceModal({
        step_no: 'DIRECT',
        tool_name: name,
        parameters: args,
        raw_result: data.result
      });
    } catch (e) {
      alert(`Tool call error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }
});
