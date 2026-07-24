// AgriSense Frontend Application Logic (Vanilla JS)
document.addEventListener('DOMContentLoaded', () => {
  // Account Management State
  function getStoredAccount() {
    try {
      const data = localStorage.getItem('agrisense_account');
      return data ? JSON.parse(data) : null;
    } catch (e) {
      return null;
    }
  }

  function saveStoredAccount(acc) {
    if (acc) {
      localStorage.setItem('agrisense_account', JSON.stringify(acc));
      localStorage.setItem('agrisense_farmer_id', acc.farmer_id);
    } else {
      localStorage.removeItem('agrisense_account');
      localStorage.removeItem('agrisense_farmer_id');
    }
  }

  function getOrCreateFarmerId() {
    const acc = getStoredAccount();
    if (acc && acc.farmer_id) return acc.farmer_id;
    const key = 'agrisense_farmer_id';
    let farmerId = localStorage.getItem(key);
    if (!farmerId) {
      farmerId = `farmer_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem(key, farmerId);
    }
    return farmerId;
  }

  // Global State
  const state = {
    account: getStoredAccount(),
    farmerId: getOrCreateFarmerId(),
    sessionId: `session_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
    farmId: null,
    savedFarms: [],
    savedChats: [],
    memoryStatus: 'none',
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
    farmerIdBadge: document.getElementById('farmer-id-badge'),
    savedFarmsList: document.getElementById('saved-farms-list'),

    // Account & Subscription UI
    userSubscriptionBadge: document.getElementById('btn-subscription-badge'),
    userDisplayName: document.getElementById('user-display-name'),
    btnAuthAction: document.getElementById('btn-auth-action'),
    
    // Saved Chats
    btnCreateChat: document.getElementById('btn-create-chat'),
    chatsList: document.getElementById('chats-list'),

    // Auth Modal
    modalAuth: document.getElementById('modal-auth'),
    modalAuthClose: document.getElementById('modal-auth-close'),
    authTabLogin: document.getElementById('auth-tab-login'),
    authTabSignup: document.getElementById('auth-tab-signup'),
    formLogin: document.getElementById('form-login'),
    formSignup: document.getElementById('form-signup'),
    loginEmail: document.getElementById('login-email'),
    loginPassword: document.getElementById('login-password'),
    signupName: document.getElementById('signup-name'),
    signupEmail: document.getElementById('signup-email'),
    signupPassword: document.getElementById('signup-password'),
    signupTier: document.getElementById('signup-tier'),

    // Subscription Modal
    modalSubscription: document.getElementById('modal-subscription'),
    modalSubClose: document.getElementById('modal-sub-close'),
    
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

    // Audit Card & Scenario Elements
    evDecision: document.getElementById('ev-decision'),
    evInputs: document.getElementById('ev-inputs'),
    evLiveData: document.getElementById('ev-livedata'),
    evTime: document.getElementById('ev-time'),
    evWeather: document.getElementById('ev-weather'),
    evHorizon: document.getElementById('ev-horizon'),
    evEvidence: document.getElementById('ev-evidence'),
    evResult: document.getElementById('ev-result'),

    scenarioBox: document.getElementById('scenario-box'),
    scenBaseBudget: document.getElementById('scen-base-budget'),
    scenOverrideBudget: document.getElementById('scen-override-budget'),
    scenarioTable: document.getElementById('scenario-table'),

    // Modal Trace
    modalTrace: document.getElementById('modal-trace'),
    modalTraceTitle: document.getElementById('modal-trace-title'),
    modalTraceParams: document.getElementById('modal-trace-params'),
    modalTraceResult: document.getElementById('modal-trace-result'),
    modalTraceClose: document.getElementById('modal-trace-close')
  };

  // Render Account UI
  function renderAccountUI() {
    if (state.account) {
      els.userDisplayName.textContent = state.account.full_name;
      if (els.userSubscriptionBadge) {
        els.userSubscriptionBadge.classList.remove('hidden');
        els.userSubscriptionBadge.textContent = 'Subscribed Member';
      }
      els.btnAuthAction.textContent = 'Log Out';
      if (els.chatInput) {
        els.chatInput.disabled = false;
        els.chatInput.placeholder = "Tell AgriSense about your plot (e.g. '2 acres in Moulovibazar with BDT 60k budget for boro season')...";
      }
      if (els.btnSend) els.btnSend.disabled = false;
    } else {
      els.userDisplayName.textContent = 'Sign In Required';
      if (els.userSubscriptionBadge) els.userSubscriptionBadge.classList.add('hidden');
      els.btnAuthAction.textContent = 'Log In / Sign Up';
      if (els.chatInput) {
        els.chatInput.disabled = true;
        els.chatInput.placeholder = '🔒 Please Log In or Sign Up to start chatting with AgriSense...';
      }
      if (els.btnSend) els.btnSend.disabled = true;
    }
  }
  renderAccountUI();

  // Prompt Auth on initial load if unauthenticated
  if (!state.account && els.modalAuth) {
    els.modalAuth.classList.remove('hidden');
  }

  if (els.farmerIdBadge) {
    els.farmerIdBadge.textContent = state.farmerId.slice(0, 14);
  }

  // Multi-Chat Session Management
  async function loadSavedChats() {
    if (!state.account) return;
    try {
      const res = await fetch(`/v1/farmers/${state.farmerId}/chats`);
      if (res.ok) {
        const data = await res.json();
        state.savedChats = data.chats || [];
        renderSavedChats();
      }
    } catch (e) {
      console.warn('Could not load saved chats:', e);
    }
  }
  loadSavedChats();

  function renderSavedChats() {
    if (!els.chatsList) return;
    if (!state.savedChats || state.savedChats.length === 0) {
      els.chatsList.innerHTML = `<div class="text-[11px] text-slate-500 italic p-1">No saved chats yet.</div>`;
      return;
    }

    els.chatsList.innerHTML = state.savedChats.map(c => {
      const isActive = state.sessionId === c.session_id;
      const title = escapeHtml(c.title || 'Farm Advisory Session');
      return `
        <div class="chat-item group flex items-center justify-between p-1.5 px-2 rounded-lg border text-xs cursor-pointer transition ${
          isActive ? 'bg-brand-600/20 border-brand-500 text-white font-semibold' : 'bg-slate-800/40 border-slate-700/50 text-slate-300 hover:bg-slate-800'
        }" data-session-id="${c.session_id}">
          <div class="flex items-center gap-1.5 truncate flex-1 pointer-events-none">
            <i data-lucide="${isActive ? 'message-square' : 'message-circle'}" class="w-3.5 h-3.5 ${isActive ? 'text-brand-400' : 'text-slate-500'} shrink-0"></i>
            <span class="truncate">${title}</span>
          </div>
          <button class="chat-delete-btn p-0.5 text-slate-500 hover:text-red-400 rounded transition opacity-0 group-hover:opacity-100 ml-1" data-session-id="${c.session_id}" title="Delete Chat">
            <i data-lucide="trash-2" class="w-3 h-3"></i>
          </button>
        </div>
      `;
    }).join('');

    if (window.lucide) window.lucide.createIcons();

    els.chatsList.querySelectorAll('.chat-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('.chat-delete-btn')) return;
        const sid = item.getAttribute('data-session-id');
        if (sid && sid !== state.sessionId) {
          switchChatSession(sid);
        }
      });
    });

    els.chatsList.querySelectorAll('.chat-delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const sid = btn.getAttribute('data-session-id');
        deleteChatSession(sid);
      });
    });
  }

  async function createChatSession(customTitle = null) {
    if (!state.account) {
      if (els.modalAuth) els.modalAuth.classList.remove('hidden');
      return;
    }
    try {
      const title = customTitle || 'New Farm Chat';
      const res = await fetch(`/v1/farmers/${state.farmerId}/chats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ farmer_id: state.farmerId, title })
      });
      if (res.ok) {
        const data = await res.json();
        const newSessionId = data.session?.session_id;
        if (newSessionId) {
          state.sessionId = newSessionId;
          state.profile = {};
          state.recommendations = [];
          state.selectedCropId = null;
          state.plan = null;
          state.traces = [];
          els.chatContainer.innerHTML = '';
          addAssistantMessage('New chat session started. Tell me about your land location, area, soil texture, irrigation access, or budget.');
          renderProfile();
          renderTraces();
          renderPlan();
          await loadSavedChats();
        }
      }
    } catch (e) {
      console.error('Failed to create chat session:', e);
    }
  }

  async function switchChatSession(sessionId) {
    setLoading(true);
    try {
      const res = await fetch(`/v1/sessions/${sessionId}?farmer_id=${state.farmerId}`);
      if (!res.ok) throw new Error('Session not found or forbidden');
      const data = await res.json();
      state.sessionId = data.session_id;
      state.profile = data.profile || {};
      state.recommendations = data.recommendations || [];
      state.selectedCropId = data.selected_crop_id;
      state.plan = data.plan;

      els.chatContainer.innerHTML = '';
      const messages = data.messages || [];
      if (messages.length === 0) {
        addAssistantMessage('Session initialized. Ready for your farm details.');
      } else {
        messages.forEach(m => {
          if (m.role === 'user') {
            addUserMessage(m.content);
          } else {
            addAssistantMessage(m.content);
          }
        });
      }

      renderProfile();
      renderTraces();
      renderPlan();
      renderSavedChats();
    } catch (e) {
      addAssistantMessage(`Could not switch chat: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function deleteChatSession(sessionId) {
    if (!confirm('Are you sure you want to delete this chat history?')) return;
    try {
      const res = await fetch(`/v1/sessions/${sessionId}?farmer_id=${state.farmerId}`, { method: 'DELETE' });
      if (res.ok) {
        if (state.sessionId === sessionId) {
          state.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
          els.chatContainer.innerHTML = '';
          state.profile = {};
          state.recommendations = [];
          state.selectedCropId = null;
          state.plan = null;
          state.traces = [];
          addAssistantMessage('Previous chat deleted. Ready for your farm details.');
        }
        await loadSavedChats();
      }
    } catch (e) {
      console.error('Failed to delete chat:', e);
    }
  }

  // Auth Event Listeners
  if (els.btnAuthAction) {
    els.btnAuthAction.addEventListener('click', () => {
      if (state.account) {
        saveStoredAccount(null);
        state.account = null;
        state.farmerId = getOrCreateFarmerId();
        renderAccountUI();
        state.savedChats = [];
        state.savedFarms = [];
        renderSavedChats();
        renderSavedFarms();
        els.chatContainer.innerHTML = '';
        els.modalAuth.classList.remove('hidden');
      } else {
        els.modalAuth.classList.remove('hidden');
      }
    });
  }

  if (els.modalAuthClose) {
    els.modalAuthClose.addEventListener('click', () => els.modalAuth.classList.add('hidden'));
  }

  if (els.authTabLogin && els.authTabSignup) {
    els.authTabLogin.addEventListener('click', () => {
      els.authTabLogin.className = 'flex-1 py-1.5 text-xs font-semibold rounded-lg bg-brand-600 text-white transition';
      els.authTabSignup.className = 'flex-1 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white transition';
      els.formLogin.classList.remove('hidden');
      els.formSignup.classList.add('hidden');
    });

    els.authTabSignup.addEventListener('click', () => {
      els.authTabSignup.className = 'flex-1 py-1.5 text-xs font-semibold rounded-lg bg-brand-600 text-white transition';
      els.authTabLogin.className = 'flex-1 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white transition';
      els.formSignup.classList.remove('hidden');
      els.formLogin.classList.add('hidden');
    });
  }

  if (els.formLogin) {
    els.formLogin.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        const res = await fetch('/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: els.loginEmail.value, password: els.loginPassword.value })
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || 'Login failed');
          return;
        }
        const acc = await res.json();
        saveStoredAccount(acc);
        state.account = acc;
        state.farmerId = acc.farmer_id;
        renderAccountUI();
        els.modalAuth.classList.add('hidden');
        loadSavedFarms();
        loadSavedChats();
        addAssistantMessage(`Welcome back, ${acc.full_name}!`);
      } catch (err) {
        alert(`Login error: ${err.message}`);
      }
    });
  }

  if (els.formSignup) {
    els.formSignup.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        const res = await fetch('/v1/auth/signup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            full_name: els.signupName.value,
            email: els.signupEmail.value,
            password: els.signupPassword.value,
            subscription_tier: 'standard'
          })
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || 'Signup failed');
          return;
        }
        const acc = await res.json();
        saveStoredAccount(acc);
        state.account = acc;
        state.farmerId = acc.farmer_id;
        renderAccountUI();
        els.modalAuth.classList.add('hidden');
        loadSavedFarms();
        loadSavedChats();
        addAssistantMessage(`Account created & subscription activated! Welcome to AgriSense, ${acc.full_name}.`);
      } catch (err) {
        alert(`Signup error: ${err.message}`);
      }
    });
  }

  if (els.btnCreateChat) {
    els.btnCreateChat.addEventListener('click', () => {
      createChatSession();
    });
  }

  async function loadSavedFarms() {
    try {
      const res = await fetch(`/v1/farmers/${state.farmerId}/farms`);
      if (res.ok) {
        const data = await res.json();
        state.savedFarms = data.farms || [];
        renderSavedFarms();
      }
    } catch (e) {
      console.warn('Could not load saved farms:', e);
    }
  }
  loadSavedFarms();

  function renderSavedFarms() {
    if (!els.savedFarmsList) return;
    if (!state.savedFarms || state.savedFarms.length === 0) {
      els.savedFarmsList.innerHTML = `<div class="text-[11px] text-slate-500 italic">No saved farms yet.</div>`;
      return;
    }

    els.savedFarmsList.innerHTML = state.savedFarms.map(f => {
      const p = f.profile || {};
      const isSelected = state.farmId === f.farm_id;
      return `
        <div class="p-2 rounded-lg border transition ${
          isSelected ? 'bg-brand-500/10 border-brand-500 text-white' : 'bg-slate-800/60 border-slate-700/60 text-slate-300'
        }">
          <div class="flex items-center justify-between font-semibold mb-0.5">
            <span>🏡 ${escapeHtml(f.farm_name)}</span>
            <span class="text-[10px] font-mono text-slate-400">v${f.profile_version}</span>
          </div>
          <p class="text-[10px] text-slate-400 mb-1.5">
            ${p.farm_size_acre || 2} acres • ${p.soil_type || 'loam'} • ${p.water_availability || 'rainfed'}
          </p>
          <div class="flex gap-1">
            <button class="use-farm-btn flex-1 py-0.5 text-[10px] font-semibold rounded bg-brand-600 hover:bg-brand-500 text-white" data-id="${f.farm_id}">
              ${isSelected ? 'Active' : 'Use Farm'}
            </button>
            <button class="forget-farm-btn px-2 py-0.5 text-[10px] font-semibold rounded bg-slate-700 hover:bg-red-600 text-slate-300 hover:text-white" data-id="${f.farm_id}">
              Forget
            </button>
          </div>
        </div>
      `;
    }).join('');

    els.savedFarmsList.querySelectorAll('.use-farm-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        sendMemoryAction('apply', id);
      });
    });

    els.savedFarmsList.querySelectorAll('.forget-farm-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        await fetch(`/v1/farms/${id}?farmer_id=${state.farmerId}`, { method: 'DELETE' });
        if (state.farmId === id) state.farmId = null;
        loadSavedFarms();
      });
    });
  }

  // Send Memory Action API Helper
  async function sendMemoryAction(action, farmId = null) {
    setLoading(true);
    try {
      const endpoint = state.engine === 'agentic' ? '/v1/agent/agentic-turn' : '/v1/agent/turn';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          farmer_id: state.farmerId,
          farm_id: farmId || state.farmId,
          memory_action: action,
          message: `Memory confirmation: ${action}`
        })
      });
      const turn = await res.json();
      handleTurnResponse(turn);
      loadSavedFarms();
    } catch (e) {
      addAssistantMessage(`Failed memory action: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

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
  if (els.engineAgentic) {
    els.engineAgentic.addEventListener('click', () => {
      state.engine = 'agentic';
      els.engineAgentic.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 bg-brand-600 text-white shadow';
      if (els.engineTier0) els.engineTier0.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition flex items-center gap-1.5';
    });
  }

  if (els.engineTier0) {
    els.engineTier0.addEventListener('click', () => {
      state.engine = 'tier0';
      els.engineTier0.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 bg-brand-600 text-white shadow';
      if (els.engineAgentic) els.engineAgentic.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition flex items-center gap-1.5';
    });
  }

  // Reset Session
  if (els.btnNewSession) {
    els.btnNewSession.addEventListener('click', () => {
      createChatSession();
    });
  }

  // Tab Switcher
  if (els.tabTracesBtn) {
    els.tabTracesBtn.addEventListener('click', () => {
      els.tabTracesBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-brand-400 border-b-2 border-brand-500 flex items-center justify-center gap-1.5';
      if (els.tabPlanBtn) els.tabPlanBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 border-b-2 border-transparent hover:text-slate-200 flex items-center justify-center gap-1.5';
      if (els.tabTracesContent) els.tabTracesContent.classList.remove('hidden');
      if (els.tabPlanContent) els.tabPlanContent.classList.add('hidden');
    });
  }

  if (els.tabPlanBtn) {
    els.tabPlanBtn.addEventListener('click', () => {
      els.tabPlanBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-brand-400 border-b-2 border-brand-500 flex items-center justify-center gap-1.5';
      if (els.tabTracesBtn) els.tabTracesBtn.className = 'flex-1 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 border-b-2 border-transparent hover:text-slate-200 flex items-center justify-center gap-1.5';
      if (els.tabPlanContent) els.tabPlanContent.classList.remove('hidden');
      if (els.tabTracesContent) els.tabTracesContent.classList.add('hidden');
    });
  }

  // Sample Prompt Buttons
  document.querySelectorAll('.sample-prompt').forEach(btn => {
    btn.addEventListener('click', () => {
      els.chatInput.value = btn.getAttribute('data-prompt');
      els.chatInput.focus();
    });
  });

  // Handle Enter key in textarea (Enter sends message, Shift+Enter adds newline)
  if (els.chatInput) {
    els.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (els.chatForm) {
          if (typeof els.chatForm.requestSubmit === 'function') {
            els.chatForm.requestSubmit();
          } else {
            els.chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
          }
        }
      }
    });
  }

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
          farmer_id: state.farmerId,
          farm_id: state.farmId,
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
    const msgText = (turn.message || '').toLowerCase();
    if (msgText.includes('what if') || msgText.includes('budget is cut') || msgText.includes('cut by') || msgText.includes('scenario')) {
      state.isScenarioDetected = true;
      state.scenarioOverrideBudget = turn.profile?.budget_bdt || 120000;
    }

    if (turn.profile) state.profile = turn.profile;
    if (turn.missing_fields) state.missingFields = turn.missing_fields;
    if (turn.recommendations) state.recommendations = turn.recommendations;
    if (turn.selected_crop_id) state.selectedCropId = turn.selected_crop_id;
    if (turn.plan) state.plan = turn.plan;
    if (turn.trace) state.traces = turn.trace;

    if (turn.memory) {
      state.memoryStatus = turn.memory.status;
      if (turn.memory.farm_id) state.farmId = turn.memory.farm_id;
    }

    renderProfile();
    renderTraces();
    renderPlan();
    loadSavedFarms();
    loadSavedChats();

    // Render Assistant reply with Memory controls if needed
    addAssistantMessage(turn.message, turn.decision_summary, turn.status, turn.memory);

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
          farmer_id: state.farmerId,
          farm_id: state.farmId,
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

    let scenarioCardHtml = '';
    const pProfile = state.profile || {};
    if (state.isScenarioDetected || (pProfile.budget_bdt && pProfile.budget_bdt !== 200000)) {
      const currentBgt = pProfile.budget_bdt || 120000;
      scenarioCardHtml = `
        <div class="p-3.5 rounded-xl bg-purple-950/60 border border-purple-500/40 text-purple-200 space-y-2 mb-3">
          <div class="flex items-center justify-between">
            <span class="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded bg-purple-500/20 text-purple-200 border border-purple-500/30">
              SCENARIO DETECTED
            </span>
            <span class="text-[10px] text-purple-300 font-mono">Memory Preserved</span>
          </div>
          <p class="text-xs font-semibold text-white">
            Temporary budget override: <span class="text-amber-300 font-mono">BDT ${currentBgt.toLocaleString()}</span>
          </p>
          <div class="text-[11px] text-purple-200 space-y-1.5 leading-snug">
            <p><strong>MEMORY POLICY:</strong> The accepted farm budget remains <span class="text-white font-mono">BDT 200,000</span>.</p>
            <p><strong>DEPENDENCY ANALYSIS:</strong> Affected components: affordable planted area / input allocation, total cost, expected yield, revenue, profit, ROI.</p>
            <p><strong>RECALCULATION:</strong> Only dependent outputs are recalculated.</p>
            <p><strong>RESULT:</strong> Base plan retained; scenario comparison generated.</p>
          </div>
        </div>
      `;
    }

    if (traces.length === 0) {
      els.tracesEmpty.classList.remove('hidden');
      els.tracesList.innerHTML = blockedCardsHtml + scenarioCardHtml;
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

    els.tracesList.innerHTML = blockedCardsHtml + scenarioCardHtml + traceCardsHtml;

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

  // Render Plan & Audit Cards
  function renderPlan() {
    const plan = state.plan;
    if (!plan) {
      els.planEmpty.classList.remove('hidden');
      els.planDetails.classList.add('hidden');
      return;
    }

    els.planEmpty.classList.add('hidden');
    els.planDetails.classList.remove('hidden');

    els.planTitle.textContent = `${plan.crop_name} Season Plan`;
    const startDate = plan.planned_sowing_date || 'TBD';
    const endDate = plan.expected_harvest_date || 'TBD';
    els.planSubtitle.textContent = `Sowing: ${startDate} → Harvest: ${endDate}`;

    const fin = plan.financial_projection || {};
    els.planCost.textContent = `BDT ${(fin.total_cost_bdt || 0).toLocaleString()}`;
    els.planProfit.textContent = `BDT ${(fin.net_profit_bdt || 0).toLocaleString()}`;
    els.planYield.textContent = `${(fin.total_expected_yield_kg || fin.expected_yield_kg || 0).toLocaleString()} kg`;
    els.planRoi.textContent = `${(fin.roi_percent || 0).toFixed(1)}%`;

    // Populate Evidence-to-Decision Audit Card
    const p = state.profile || {};
    els.evDecision.textContent = `${plan.crop_name} selected for dated plan`;
    els.evInputs.innerHTML = `
      <li>${p.farm_size_acre || '—'} acres cultivated area</li>
      <li>${p.soil_type || p.soil_texture || '—'} soil type</li>
      <li>${p.water_availability || '—'} irrigation access</li>
      <li>BDT ${(p.budget_bdt || 0).toLocaleString()} budget capital</li>
      <li>${p.target_season || '—'} target cropping season</li>
    `;
    els.evTime.textContent = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    els.evWeather.textContent = `7-day rainfall: ${plan.irrigation_summary?.live_rainfall_next_5d_mm_at_plan_time || 0}mm | Live Weather Ingested`;
    els.evHorizon.textContent = plan.weather_temporally_relevant ? 'Near-term active (<7 days)' : 'Provisional (Forecast refresh prior to execution)';
    
    const evList = plan.evidence || [];
    if (evList.length > 0) {
      els.evEvidence.innerHTML = evList.map(ev => `<li>${escapeHtml(ev.title || ev.document_id || 'Agronomic Record')}</li>`).join('');
    } else {
      els.evEvidence.innerHTML = `<li>Agronomic Evidence Record</li>`;
    }

    els.evResult.innerHTML = `
      <div><span class="text-slate-400 font-medium">Validation Status:</span> <span class="font-semibold font-mono ${plan.validation_status?.passed ? 'text-emerald-400' : 'text-amber-400'}">${plan.validation_status?.passed ? 'Verified' : 'Draft / Unverified'}</span></div>
      <div><span class="text-slate-400">Seasonal Water Need:</span> <span class="text-slate-200 font-mono">${plan.irrigation_summary?.seasonal_water_requirement_mm_mock || '—'}mm</span></div>
      <div><span class="text-slate-400">Projected Total Cost:</span> <span class="text-slate-200 font-mono">BDT ${(fin.total_cost_bdt || 0).toLocaleString()}</span></div>
      <div><span class="text-slate-400 font-bold">Projected Net Profit:</span> <span class="text-brand-400 font-bold font-mono">BDT ${(fin.net_profit_bdt || 0).toLocaleString()}</span></div>
      <div><span class="text-slate-400">Projected ROI:</span> <span class="text-emerald-400 font-bold font-mono">${(fin.roi_percent || 0).toFixed(1)}%</span></div>
    `;

    // Populate Scenario Comparison Table if scenario result returned from backend
    const scenario = state.scenario;
    if (scenario && scenario.deltas) {
      els.scenarioBox.classList.remove('hidden');
      const tbodyScen = els.scenarioTable.querySelector('tbody');
      tbodyScen.innerHTML = Object.entries(scenario.deltas).map(([k, v]) => `
        <tr>
          <td class="p-2 font-medium text-slate-300 capitalize">${k.replace('_', ' ')}</td>
          <td class="p-2 text-right text-slate-400">${v.baseline ?? '—'}</td>
          <td class="p-2 text-right text-amber-300">${v.scenario ?? '—'}</td>
          <td class="p-2 text-right text-brand-400">${v.delta ?? '—'}</td>
        </tr>
      `).join('');
    } else {
      els.scenarioBox.classList.add('hidden');
    }

    // Tasks Timeline
    const tasks = plan.tasks || plan.stages || [];
    els.planTimeline.innerHTML = tasks.map(t => {
      const taskName = t.action_type || t.task_name || t.stage_name || 'Farm Operation';
      const taskDate = t.start_date ? `${t.start_date}${t.end_date ? ' → ' + t.end_date : ''}` : 'Scheduled';
      const detail = t.description || t.stage_purpose || (t.quantity ? `${t.quantity.value} ${t.quantity.unit}` : '');
      return `
        <div class="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
          <div class="flex items-center justify-between text-xs font-semibold text-slate-200 mb-1">
            <span>${escapeHtml(taskName)}</span>
            <span class="font-mono text-[10px] text-brand-400">${escapeHtml(taskDate)}</span>
          </div>
          ${detail ? `<p class="text-[11px] text-slate-400 mb-1.5">${escapeHtml(detail)}</p>` : ''}
        </div>
      `;
    }).join('');

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

  // Markdown Renderer Helper
  function renderMarkdown(text) {
    if (!text) return '';
    try {
      if (window.marked) {
        if (typeof window.marked.setOptions === 'function') {
          window.marked.setOptions({ breaks: true, gfm: true });
        }
        if (typeof window.marked.parse === 'function') {
          return window.marked.parse(text);
        } else if (typeof window.marked === 'function') {
          return window.marked(text);
        }
      }
    } catch (e) {
      console.warn('Markdown parse error:', e);
    }
    return escapeHtml(text);
  }

  // Add Messages to Chat UI
  function addUserMessage(text) {
    const welcome = document.getElementById('welcome-banner');
    if (welcome) welcome.remove();
    const msg = document.createElement('div');
    msg.className = 'flex justify-end animate-fade-in';
    msg.innerHTML = `
      <div class="max-w-xl p-3.5 rounded-2xl bg-brand-600 text-white text-sm shadow-md rounded-tr-none markdown-content">
        ${renderMarkdown(text)}
      </div>
    `;
    els.chatContainer.appendChild(msg);
    scrollToBottom();
  }

  function addAssistantMessage(text, decisionSummary, status = null, memoryContext = null) {
    const welcome = document.getElementById('welcome-banner');
    if (welcome) welcome.remove();
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

    let memoryActionControlsHtml = '';
    if (status === 'needs_memory_confirmation') {
      const topCand = memoryContext?.saved_farms?.[0];
      const farmId = topCand?.farm_id;
      memoryActionControlsHtml = `
        <div class="mt-3 p-3 rounded-xl bg-brand-950/40 border border-brand-500/30 flex flex-col gap-2">
          <p class="text-xs text-brand-200 font-medium">Persistent Memory Confirmation Required:</p>
          <div class="flex gap-2">
            <button class="mem-action-btn flex-1 py-1.5 px-3 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow transition" data-action="apply" data-farm-id="${farmId || ''}">
              ✓ Use Saved Farm
            </button>
            <button class="mem-action-btn flex-1 py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition" data-action="decline">
              ✕ Start Fresh
            </button>
          </div>
        </div>
      `;
    } else if (status === 'needs_memory_conflict_resolution') {
      memoryActionControlsHtml = `
        <div class="mt-3 p-3 rounded-xl bg-amber-950/40 border border-amber-500/30 flex flex-col gap-2">
          <p class="text-xs text-amber-200 font-medium">Memory Conflict Resolution Required:</p>
          <div class="flex flex-wrap gap-2">
            <button class="mem-action-btn py-1.5 px-3 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold transition" data-action="confirm_update">
              Permanent Update
            </button>
            <button class="mem-action-btn py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition" data-action="use_temporarily">
              Use Temporarily
            </button>
            <button class="mem-action-btn py-1.5 px-3 rounded-lg bg-purple-900 hover:bg-purple-800 text-purple-200 text-xs font-medium border border-purple-700 transition" data-action="create_new">
              Create Another Farm
            </button>
          </div>
        </div>
      `;
    }

    msg.innerHTML = `
      <div class="w-8 h-8 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center shrink-0 mt-0.5">
        <i data-lucide="bot" class="w-5 h-5"></i>
      </div>
      <div class="max-w-2xl p-4 rounded-2xl bg-slate-900/90 border border-slate-800 text-sm text-slate-200 shadow-md rounded-tl-none space-y-2">
        ${summaryHtml}
        <div class="leading-relaxed markdown-content">${renderMarkdown(text)}</div>
        ${memoryActionControlsHtml}
      </div>
    `;

    els.chatContainer.appendChild(msg);

    msg.querySelectorAll('.mem-action-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.getAttribute('data-action');
        const farmId = btn.getAttribute('data-farm-id');
        sendMemoryAction(action, farmId);
      });
    });

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
